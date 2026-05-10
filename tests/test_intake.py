"""
Unit tests for the intake node.
The LLM is mocked so no Claude API calls are made.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from sqlmodel import Session

from app.graph.nodes.intake import run, _build_log_context
from app.graph.state import default_state, DeterministicStats
from app.models.log_entry import LogEntry


def _make_entry(**kwargs) -> LogEntry:
    defaults = {
        "id": 1,
        "entry_date": date(2026, 4, 27),
        "migraine_occurred": True,
        "pain_level": 7,
        "foods": ["coffee", "cheese"],
        "sleep_hours": 5.5,
        "stress_level": 8,
        "stress_source": "deadline",
        "notes": "rough morning",
    }
    return LogEntry(**{**defaults, **kwargs})


def _make_state(log_id: int = 1, **kwargs) -> dict:
    state = default_state()
    state["current_log_id"] = log_id
    state["deterministic_stats"] = DeterministicStats(
        migraine_free_streak_days=3,
        migraine_days_last_30d=5,
        avg_pain_level_last_30d=6.8,
        pain_trend_direction="stable",
        top_5_triggers_last_30d=["coffee", "poor_sleep"],
    ).model_dump()
    state.update(kwargs)
    return state


# ── _build_log_context ────────────────────────────────────────────────────────

def test_context_contains_entry_date(test_engine):
    entry = _make_entry()
    ctx = _build_log_context(entry, {}, default_state())
    assert "2026-04-27" in ctx


def test_context_contains_pain_level(test_engine):
    entry = _make_entry(pain_level=8)
    ctx = _build_log_context(entry, {}, default_state())
    assert "8/10" in ctx


def test_context_flags_missing_pain_location(test_engine):
    entry = _make_entry(pain_location=None)
    ctx = _build_log_context(entry, {}, default_state())
    assert "pain location" in ctx


def test_context_flags_missing_prodrome(test_engine):
    entry = _make_entry(prodrome_symptoms=None)
    ctx = _build_log_context(entry, {}, default_state())
    assert "prodrome symptoms" in ctx


def test_context_no_missing_fields_when_complete(test_engine):
    entry = _make_entry(
        pain_location="left temporal",
        prodrome_symptoms=["visual aura"],
        chemical_exposure=[],
        fragrance_exposure=False,
        menstrual_cycle_day=14,
    )
    ctx = _build_log_context(entry, {}, default_state())
    assert "MISSING HIGH-SIGNAL FIELDS" not in ctx


def test_context_includes_confirmed_triggers(test_engine):
    state = default_state()
    state["confirmed_triggers"] = ["MSG", "tyramine"]
    entry = _make_entry()
    ctx = _build_log_context(entry, {}, state)
    assert "MSG" in ctx
    assert "tyramine" in ctx


def test_context_includes_stats(test_engine):
    entry = _make_entry()
    stats = DeterministicStats(migraine_days_last_30d=6).model_dump()
    ctx = _build_log_context(entry, stats, default_state())
    assert "Migraines last 30d:    6" in ctx


# ── run() ─────────────────────────────────────────────────────────────────────

def test_run_returns_ai_message(test_engine, session):
    entry = _make_entry()
    session.add(entry)
    session.commit()
    session.refresh(entry)

    fake_response = AIMessage(content="Logged — pain 7.\n\n1. What time did the pain start?")

    with patch("app.graph.nodes.intake._llm") as mock_llm:
        mock_llm.invoke.return_value = fake_response
        result = run(_make_state(log_id=entry.id))

    assert "messages" in result
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)


def test_run_sets_current_agent(test_engine, session):
    entry = _make_entry()
    session.add(entry)
    session.commit()
    session.refresh(entry)

    with patch("app.graph.nodes.intake._llm") as mock_llm:
        mock_llm.invoke.return_value = AIMessage(content="Logged.")
        result = run(_make_state(log_id=entry.id))

    assert result["current_agent"] == "intake"


def test_run_returns_empty_when_no_log_id(test_engine):
    state = default_state()  # current_log_id is None
    result = run(state)
    assert result == {"current_agent": "intake"}


def test_run_returns_empty_when_log_not_found(test_engine):
    state = _make_state(log_id=9999)  # ID that doesn't exist in DB
    result = run(state)
    assert result == {"current_agent": "intake"}
