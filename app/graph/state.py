import operator
from typing import Annotated, Optional
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


class DeterministicStats(BaseModel):
    migraine_free_streak_days: int = 0
    migraine_days_last_30d: int = 0
    avg_pain_level_last_30d: float = 0.0
    pain_trend_direction: str = "stable"       # improving | worsening | stable
    triptan_days_last_30d: int = 0
    nsaid_days_last_30d: int = 0
    moh_alert_active: bool = False
    top_5_triggers_last_30d: list[str] = Field(default_factory=list)
    total_events_logged: int = 0


class WeatherSnapshot(BaseModel):
    timestamp: str = ""
    barometric_pressure_hpa: float = 0.0
    pressure_delta_24h: float = 0.0
    temperature_f: float = 0.0
    humidity_pct: float = 0.0
    aqi: int = 0
    dominant_pollutant: str = ""


class ProtocolItem(BaseModel):
    intervention: str
    tier: int
    dose_or_detail: str
    rationale: str
    what_to_log: str
    assessment_weeks: int


class Protocol(BaseModel):
    version: int = 0
    date: str = ""
    active_tier: int = 1
    active_items: list[ProtocolItem] = Field(default_factory=list)
    on_deck: list[ProtocolItem] = Field(default_factory=list)


# ── LangGraph state ──────────────────────────────────────────────────────────
# Annotated[list, operator.add] → LangGraph appends items rather than replacing
# Annotated[list, add_messages] → LangGraph manages message deduplication
# Plain fields           → LangGraph replaces on each update

class MigraineState(dict):
    """
    LangGraph state for MigraineTackler.

    Two SQLite databases:
      data/migraine.db    — LogEntry health records (SQLModel)
      data/langgraph.db   — This state, persisted via SqliteSaver checkpoints

    Keeping them separate avoids schema conflicts and makes it easy to wipe
    agent memory without touching health records, or vice versa.
    """

    # ── Routing ──────────────────────────────────────────────────────────────
    intent: str                                  # log_entry | pattern_review | ...
    current_agent: str                           # which node is active

    # ── Long-term memory (persisted across sessions via SqliteSaver) ─────────
    confirmed_triggers: Annotated[list[str], operator.add]
    suspected_triggers: Annotated[list[str], operator.add]
    ruled_out_triggers: Annotated[list[str], operator.add]
    research_findings: Annotated[list[str], operator.add]   # "[date] topic: summary"
    medical_frameworks_applied: Annotated[list[str], operator.add]
    unknown_trigger_candidates: Annotated[list[str], operator.add]  # novel items correlating with migraine days

    current_root_cause_hypothesis: str
    root_cause_evidence: list[dict]            # [{claim, source, source_type}, ...]
    migraine_subtype: str
    protocol_version: int
    current_protocol: dict                       # serialised Protocol model
    session_history_summary: str

    # ── Current session context (replaced each session) ──────────────────────
    current_log_id: Optional[int]                # FK into migraine.db LogEntry
    deterministic_stats: dict                    # serialised DeterministicStats
    weather_snapshot: dict                       # serialised WeatherSnapshot
    red_flag_active: bool
    moh_alert_active: bool

    # ── Conversation (LangGraph manages append + dedup) ───────────────────────
    messages: Annotated[list, add_messages]


def default_state() -> dict:
    """Returns a clean initial state for a brand-new user."""
    return {
        "intent": "",
        "current_agent": "",
        "confirmed_triggers": [],
        "suspected_triggers": [],
        "ruled_out_triggers": [],
        "research_findings": [],
        "medical_frameworks_applied": [],
        "unknown_trigger_candidates": [],
        "current_root_cause_hypothesis": "",
        "root_cause_evidence": [],
        "migraine_subtype": "",
        "protocol_version": 0,
        "current_protocol": {},
        "session_history_summary": "",
        "current_log_id": None,
        "deterministic_stats": DeterministicStats().model_dump(),
        "weather_snapshot": WeatherSnapshot().model_dump(),
        "red_flag_active": False,
        "moh_alert_active": False,
        "messages": [],
    }
