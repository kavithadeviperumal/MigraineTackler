import json
import logging
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.graph.nodes.schemas import ProtocolOutput
from app.graph.state import MigraineState, Protocol, ProtocolItem

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    max_tokens=3000,
    temperature=0,
)
_structured_llm = _llm.with_structured_output(ProtocolOutput)
_logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_not_exception_type(ValidationError),
    reraise=True,
)
def _invoke(messages: list):
    return _structured_llm.invoke(messages)


SYSTEM_PROMPT = """\
You are the Protocol Agent for MigraineTackler. You receive a user's root cause hypothesis, \
migraine subtype, confirmed triggers, and current stats. Your job is to generate a personalized, \
tiered migraine management protocol.

You are a knowledgeable clinical advisor. You do not prescribe. You provide evidence-based \
lifestyle, supplement, and behavioral interventions the user can discuss with their doctor. \
Always recommend professional medical consultation for medication changes.

## Protocol Tiers

- Tier 1 — Lifestyle & behavioral (sleep hygiene, hydration, stress reduction, trigger avoidance)
- Tier 2 — Supplements (magnesium glycinate, riboflavin B2, CoQ10, melatonin, etc.)
- Tier 3 — Acute strategy (when a migraine starts — what to do and in what order)
- Tier 4 — Preventive considerations (for doctor discussion only — not self-administered)

## Rules
- Start with Tier 1. Only add Tier 2+ if Tier 1 alone is insufficient given the data.
- Be specific: "400mg magnesium glycinate at bedtime" not just "take magnesium"
- Each item must have a clear rationale tied to the root cause hypothesis
- what_to_log tells the user what to track in MigraineTackler to know if it's working
- assessment_weeks: how many weeks before evaluating if this item is working (typically 4–8)
- active_items: interventions to start now (max 4–5 to avoid overwhelm)
- on_deck: interventions to consider if active_items don't produce results in 8 weeks

## Output
- protocol_summary: 3-5 sentences explaining the overall strategy — what you're targeting
  and why, in plain language the user can act on today
- active_tier: the highest tier currently active (1-4)
- active_items: list of interventions to start now, each with intervention, tier, dose_or_detail,
  rationale, what_to_log, assessment_weeks
- on_deck: same structure, for future consideration
"""


def _build_context(state: MigraineState) -> str:
    def lst(v) -> str:
        return ", ".join(v) if v else "none identified"

    stats = state.get("deterministic_stats", {})

    existing_protocol = state.get("current_protocol", {})
    prior_version = existing_protocol.get("version", 0)

    lines = [
        "=== ROOT CAUSE & SUBTYPE ===",
        f"Hypothesis:      {state.get('current_root_cause_hypothesis', 'Not established.')}",
        f"Migraine subtype: {state.get('migraine_subtype', 'Unknown')}",
        "",
        "=== TRIGGERS ===",
        f"Confirmed: {lst(state.get('confirmed_triggers', []))}",
        f"Suspected: {lst(state.get('suspected_triggers', []))}",
        f"Ruled out: {lst(state.get('ruled_out_triggers', []))}",
        "",
        "=== 30-DAY STATS ===",
        f"Migraine days (30d):  {stats.get('migraine_days_last_30d', 0)}",
        f"Avg pain level (30d): {stats.get('avg_pain_level_last_30d', 0)}",
        f"Trend:                {stats.get('pain_trend_direction', 'stable')}",
        f"Triptan days (30d):   {stats.get('triptan_days_last_30d', 0)}",
        f"NSAID days (30d):     {stats.get('nsaid_days_last_30d', 0)}",
        f"MOH alert active:     {stats.get('moh_alert_active', False)}",
        "",
        f"=== EXISTING PROTOCOL (v{prior_version}) ===",
        json.dumps(existing_protocol, indent=2)
        if existing_protocol
        else "None — this is the first protocol.",
    ]
    return "\n".join(lines)


def run(state: MigraineState) -> dict:
    context = _build_context(state)

    existing = state.get("current_protocol", {})
    prior_version = existing.get("version", 0)

    try:
        result: ProtocolOutput = _invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=context),
            ]
        )
    except Exception as exc:
        _logger.warning("protocol: LLM invoke failed: %s", exc)
        return {
            "current_agent": "protocol",
            "current_protocol": existing,
            "messages": [
                AIMessage(
                    content="Protocol generation failed — AI service error. Your existing plan remains active."
                )
            ],
        }

    try:
        active_items = [ProtocolItem(**item.model_dump()) for item in result.active_items]
        on_deck = [ProtocolItem(**item.model_dump()) for item in result.on_deck]
        protocol = Protocol(
            version=prior_version + 1,
            date=str(date.today()),
            active_tier=result.active_tier,
            active_items=active_items,
            on_deck=on_deck,
        )
        serialized_protocol = protocol.model_dump()
    except Exception:
        serialized_protocol = existing

    return {
        "current_agent": "protocol",
        "current_protocol": serialized_protocol,
        "protocol_version": prior_version + 1,
    }
