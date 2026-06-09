import json
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlmodel import Session

from app.graph.state import MigraineState
from app.config import settings
from app.database import engine
from app.services.rag_service import retrieve_relevant

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    max_tokens=2048,
)

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

## Output Format

### ROOT CAUSE SUMMARY
3–5 sentences. Explain the hypothesis and the reasoning behind it in plain language. \
Be specific — name the mechanism, not just the trigger. \
If data is insufficient for a confident hypothesis, say so and describe what's still needed.

### STRUCTURED DATA
```json
{
  "hypothesis": "one clear sentence stating the most likely root cause",
  "migraine_subtype": "one of the subtypes above",
  "confidence": "low | medium | high",
  "reasoning": "2–3 sentences explaining what data supports this hypothesis",
  "evidence": [
    {
      "claim": "specific claim this evidence supports",
      "source": "exact reference in the data (e.g. '6 of 8 migraine days', 'pattern summary', '30-day stats')",
      "source_type": "log_history | onboarding | weather | agent_memory | stats"
    }
  ],
  "what_to_watch": ["next data point or pattern to confirm or rule out this hypothesis"]
}
```
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


def _parse_structured(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def run(state: MigraineState) -> dict:
    # Retrieve KB passages relevant to the current trigger profile
    kb_passages: list[dict] = []
    user_id = state.get("user_id")
    if user_id:
        confirmed = state.get("confirmed_triggers", [])
        suspected = state.get("suspected_triggers", [])
        if confirmed or suspected:
            query = "migraine root cause mechanism " + ", ".join(confirmed + suspected)
            try:
                with Session(engine) as session:
                    kb_passages = retrieve_relevant(session, user_id, query, top_k=6)
            except Exception:
                kb_passages = []

    context = _build_context(state, kb_passages)

    response = _llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
    ])

    text = response.content
    structured = _parse_structured(text)

    confirmed = set(state.get("confirmed_triggers", []))
    suspected = set(state.get("suspected_triggers", []))

    updates: dict = {
        "current_agent": "root_cause",
        "messages": [response],
        "root_cause_triggers_seen": list(confirmed | suspected),
    }

    if structured.get("hypothesis"):
        updates["current_root_cause_hypothesis"] = structured["hypothesis"]
    if structured.get("migraine_subtype"):
        updates["migraine_subtype"] = structured["migraine_subtype"]
    if isinstance(structured.get("evidence"), list):
        updates["root_cause_evidence"] = structured["evidence"]

    return updates
