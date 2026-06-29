import logging

from pydantic import ValidationError
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from sqlmodel import Session

from app.graph.state import MigraineState
from app.config import settings
from app.database import engine
from app.services.rag_service import retrieve_relevant
from app.graph.nodes.schemas import RootCauseOutput

_logger = logging.getLogger(__name__)

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    max_tokens=2048,
    temperature=0,
)
_structured_llm = _llm.with_structured_output(RootCauseOutput)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_not_exception_type(ValidationError),
    reraise=True,
)
def _invoke(messages: list):
    return _structured_llm.invoke(messages)


SYSTEM_PROMPT = """\
You are the Root Cause Agent for MigraineTackler. You receive a synthesis of a user's migraine \
trigger patterns, history, and statistics. Your job is to form a root cause hypothesis — the most \
likely underlying driver of their migraine condition.

You are a knowledgeable clinical analyst. You do not diagnose. You reason from patterns in \
self-reported data to the most probable physiological or behavioral mechanism.

## CRITICAL GROUNDING RULE
Every claim you make must be traceable to specific data passed to you in this context. \
Do NOT introduce research statistics, general facts, or claims that are not directly supported \
by the user's own trigger lists, stats, pattern summary, or log findings provided below. \
If the data is insufficient, say so explicitly rather than filling gaps with assumptions.

## Migraine Subtypes to Consider
- hormonal_migraine — cycle-linked, estrogen-drop driven
- sleep_disorder_migraine — sleep deprivation or inconsistency is primary driver
- stress_tension_migraine — chronic stress + neck tension + emotional load
- environmental_migraine — barometric pressure, AQI, chemical/fragrance dominant
- dietary_migraine — food triggers (caffeine, alcohol, specific foods) primary
- moh_migraine — medication overuse is perpetuating the cycle
- chronic_migraine — ≥15 days/month, mechanism less trigger-specific
- mixed_trigger_migraine — multiple equally weighted contributors, no single dominant driver

## What to Reason Over
- Which confirmed triggers have the highest co-occurrence with migraine days?
- Is there a consistent physiological mechanism tying the triggers together?
- Do the stats (frequency, trend, triptan use) suggest MOH risk?
- Is the pattern improving or worsening — and why?

## Output
- root_cause_summary: 3-5 sentences explaining the hypothesis and reasoning in plain language.
  Name the mechanism, not just the trigger. If data is insufficient, say so explicitly.
- hypothesis: one clear sentence stating the most likely root cause
- migraine_subtype: exactly one of the subtypes listed above
- confidence: low | medium | high
- reasoning: 2-3 sentences explaining what data supports this hypothesis
- evidence: each item must cite a specific source in the data provided (e.g. '6 of 8 migraine days', '30-day stats')
- what_to_watch: next data points or patterns to confirm or rule out this hypothesis
"""


def _format_kb_block(passages: list[dict]) -> str:
    if not passages:
        return ""
    lines = ["=== KNOWLEDGE BASE CONTEXT (Clinical Guidelines / Ayurvedic / Doctor Notes) ==="]
    for i, p in enumerate(passages, 1):
        lines += [
            f"\n[KB-{i}] {p['doc_title']} [{p['source_label']}]"
            f" (relevance: {p['top_similarity']})",
            f"    {p['combined_text']}",
        ]
    return "\n".join(lines)


def _build_context(state: MigraineState, kb_passages: list[dict]) -> str:
    lst = lambda v: ", ".join(dict.fromkeys(v)) if v else "none yet"

    stats    = state.get("deterministic_stats", {})
    research = state.get("research_findings", [])[-20:]
    kb_block = _format_kb_block(kb_passages)

    lines = [
        "=== TRIGGER PATTERNS ===",
        f"Confirmed triggers:  {lst(state.get('confirmed_triggers', []))}",
        f"Suspected triggers:  {lst(state.get('suspected_triggers', []))}",
        f"Ruled out:           {lst(state.get('ruled_out_triggers', []))}",
        "",
        "=== PATTERN SUMMARY (from Pattern Agent) ===",
        state.get("session_history_summary", "Not yet available."),
        "",
        "=== 30-DAY STATS ===",
        f"Migraine days (30d):   {stats.get('migraine_days_last_30d', 0)}",
        f"Avg pain level (30d):  {stats.get('avg_pain_level_last_30d', 0)}",
        f"Trend:                 {stats.get('pain_trend_direction', 'stable')}",
        f"Triptan days (30d):    {stats.get('triptan_days_last_30d', 0)}",
        f"NSAID days (30d):      {stats.get('nsaid_days_last_30d', 0)}",
        f"MOH alert active:      {stats.get('moh_alert_active', False)}",
        "",
        "=== RESEARCH FINDINGS (from Research Agent) ===",
        "\n".join(research) or "None recorded.",
    ]

    if kb_block:
        lines += ["", kb_block]

    lines += [
        "",
        "=== PRIOR HYPOTHESIS ===",
        state.get("current_root_cause_hypothesis", "None established yet."),
    ]
    return "\n".join(lines)


def _validate_grounding(result: RootCauseOutput) -> RootCauseOutput:
    if result.hypothesis and not result.evidence:
        _logger.warning("root_cause: hypothesis set but evidence list is empty — downgrading confidence to low")
        return result.model_copy(update={"confidence": "low"})
    if result.confidence == "high" and len(result.evidence) < 2:
        _logger.warning("root_cause: high confidence with fewer than 2 evidence items — downgrading to medium")
        return result.model_copy(update={"confidence": "medium"})
    return result


def run(state: MigraineState) -> dict:
    kb_passages: list[dict] = []
    kb_failed = False
    user_id = state.get("user_id")
    if user_id:
        confirmed = state.get("confirmed_triggers", [])
        suspected = state.get("suspected_triggers", [])
        if confirmed or suspected:
            query = "migraine root cause mechanism " + ", ".join(confirmed + suspected)
            try:
                with Session(engine) as session:
                    kb_passages = retrieve_relevant(session, user_id, query, top_k=6)
            except Exception as exc:
                _logger.warning("root_cause: KB retrieval failed for user %s: %s", user_id, exc)
                kb_failed = True
                kb_passages = []

    context = _build_context(state, kb_passages)

    try:
        result: RootCauseOutput = _invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=context),
        ])
    except Exception as exc:
        return {
            "current_agent": "root_cause",
            "messages": [AIMessage(content=f"Root cause analysis failed — AI service error: {exc}. Your data has been saved; try again in a moment.")],
        }

    result = _validate_grounding(result)

    confirmed = set(state.get("confirmed_triggers", []))
    suspected = set(state.get("suspected_triggers", []))

    updates: dict = {
        "current_agent": "root_cause",
        "root_cause_triggers_seen": list(confirmed | suspected),
    }

    if result.hypothesis:
        updates["current_root_cause_hypothesis"] = result.hypothesis
    if result.migraine_subtype:
        updates["migraine_subtype"] = result.migraine_subtype
    if result.evidence:
        updates["root_cause_evidence"] = [e.model_dump() for e in result.evidence]

    if kb_failed:
        updates["messages"] = [AIMessage(content="Note: your personal documents were temporarily unavailable.")]

    return updates
