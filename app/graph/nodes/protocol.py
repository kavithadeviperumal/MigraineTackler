import json
import re
from datetime import date

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import MigraineState, Protocol, ProtocolItem
from app.config import settings

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.google_api_key,
    max_tokens=3000,
)

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

## Output Format

### PROTOCOL SUMMARY
3–5 sentences. Explain the overall strategy — what you're targeting and why, \
in plain language the user can act on today.

### STRUCTURED DATA
```json
{
  "active_tier": 1,
  "active_items": [
    {
      "intervention": "...",
      "tier": 1,
      "dose_or_detail": "...",
      "rationale": "...",
      "what_to_log": "...",
      "assessment_weeks": 4
    }
  ],
  "on_deck": [
    {
      "intervention": "...",
      "tier": 2,
      "dose_or_detail": "...",
      "rationale": "...",
      "what_to_log": "...",
      "assessment_weeks": 6
    }
  ]
}
```
"""


def _build_context(state: MigraineState) -> str:
    lst = lambda v: ", ".join(v) if v else "none identified"
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
        json.dumps(existing_protocol, indent=2) if existing_protocol else "None — this is the first protocol.",
    ]
    return "\n".join(lines)


def _parse_structured(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def run(state: MigraineState) -> dict:
    context = _build_context(state)

    response = _llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
    ])

    text = response.content
    structured = _parse_structured(text)

    existing = state.get("current_protocol", {})
    prior_version = existing.get("version", 0)

    try:
        active_items = [ProtocolItem(**item) for item in structured.get("active_items", [])]
        on_deck = [ProtocolItem(**item) for item in structured.get("on_deck", [])]
        protocol = Protocol(
            version=prior_version + 1,
            date=str(date.today()),
            active_tier=structured.get("active_tier", 1),
            active_items=active_items,
            on_deck=on_deck,
        )
        serialized_protocol = protocol.model_dump()
    except Exception:
        serialized_protocol = existing

    return {
        "current_agent": "protocol",
        "messages": [response],
        "current_protocol": serialized_protocol,
        "protocol_version": prior_version + 1,
    }
