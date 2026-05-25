from datetime import date, timedelta
from statistics import mean

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlmodel import Session

from app.graph.state import MigraineState
from app.database import engine
from app.services.log_service import list_recent
from app.config import settings

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.google_api_key,
    max_tokens=2500,
)

SYSTEM_PROMPT = """\
You are the Preventive Care Agent for MigraineTackler. You receive a user's personal migraine \
data — their confirmed triggers, root cause hypothesis, recent lifestyle log trends, relief methods \
that worked, their existing protocol, and any research findings already recorded.

Your job is to surface a personalised, actionable preventive care summary.

## CRITICAL GROUNDING RULES
- ONLY reference information that appears in the data passed to you in this context.
- NEVER introduce research statistics, supplement dosing claims, or general migraine facts \
  that are not grounded in the user's own trigger patterns, logged relief methods, or \
  research_findings already in their records.
- Every recommendation must explicitly state WHICH data point it comes from.
- If a section has no supporting data, say "No data yet — keep logging."
- Do not hallucinate. If you are uncertain, say so.

## Four Sections to Cover

### 1. WHAT'S SLIPPING
Lifestyle habits that have measurably declined in the last 30 days compared to the user's \
baseline or their own earlier log averages. Only include if the log data shows an actual trend. \
Tag each finding with its source (e.g., [avg sleep quality last 14d: 5.2 vs earlier 7.1]).

### 2. WHAT HAS WORKED FOR YOU
Relief methods or habits that appear in logs with relief_effectiveness ≥ 7. \
List what worked, when, and how effective. Only from actual logged data. \
Tag each item with its source (e.g., [logged 3 times, avg effectiveness 8.3/10]).

### 3. PERSONALISED PROTOCOL
2–4 non-medication interventions tied directly to this user's confirmed triggers or migraine \
subtype. If supplements are mentioned (magnesium, feverfew, riboflavin, etc.), only recommend \
them if they are already in the user's profile supplements list OR if research_findings in their \
records mention them. Include specific detail (what, when, how much if in their records). \
Tag each recommendation with [confirmed trigger], [subtype evidence], [prior protocol], or \
[from your logs].

### 4. RESEARCH RELEVANT TO YOU
Summarise 1–2 findings from research_findings that directly apply to this user's confirmed \
triggers or subtype. Only if research_findings is non-empty. Tag each with [research memory]. \
If research_findings is empty, skip this section entirely.
"""


def _build_context(state: MigraineState, entries: list) -> str:
    lst = lambda v: ", ".join(v) if v else "none identified"

    # ── Lifestyle trend from recent logs ────────────────────────────────────────
    migraine_entries = [e for e in entries if e.migraine_occurred]
    free_entries = [e for e in entries if not e.migraine_occurred]

    def _avg(vals):
        clean = [v for v in vals if v is not None]
        return round(mean(clean), 1) if clean else None

    # Split recent 30d into two halves for drift detection
    cutoff = date.today() - timedelta(days=15)
    recent_half = [e for e in free_entries if e.entry_date >= cutoff]
    earlier_half = [e for e in free_entries if e.entry_date < cutoff]

    sleep_q_recent = _avg([e.sleep_quality for e in recent_half])
    sleep_q_earlier = _avg([e.sleep_quality for e in earlier_half])
    stress_recent = _avg([e.stress_level for e in recent_half])
    stress_earlier = _avg([e.stress_level for e in earlier_half])
    hydration_recent = _avg([e.hydration_oz for e in recent_half])
    hydration_earlier = _avg([e.hydration_oz for e in earlier_half])

    # ── High-effectiveness relief methods ────────────────────────────────────────
    relief_records: dict[str, list[int]] = {}
    for e in migraine_entries:
        if e.relief_methods and e.relief_effectiveness and e.relief_effectiveness >= 7:
            for method in e.relief_methods:
                relief_records.setdefault(method, []).append(e.relief_effectiveness)
    relief_summary = [
        f"{method}: avg {round(mean(scores), 1)}/10 ({len(scores)} log{'s' if len(scores) > 1 else ''})"
        for method, scores in sorted(relief_records.items(), key=lambda x: -mean(x[1]))
    ]

    stats = state.get("deterministic_stats", {})
    existing_protocol = state.get("current_protocol", {})

    lines = [
        "=== USER TRIGGER PROFILE ===",
        f"Confirmed triggers:  {lst(state.get('confirmed_triggers', []))}",
        f"Suspected triggers:  {lst(state.get('suspected_triggers', []))}",
        f"Migraine subtype:    {state.get('migraine_subtype', 'not yet classified')}",
        f"Root cause hypothesis: {state.get('current_root_cause_hypothesis', 'not yet established')}",
        "",
        "=== LIFESTYLE TREND (last 30 days, split by 15-day halves) ===",
        f"Sleep quality  — recent 15d avg: {sleep_q_recent or '—'}  |  earlier 15d avg: {sleep_q_earlier or '—'}",
        f"Stress level   — recent 15d avg: {stress_recent or '—'}  |  earlier 15d avg: {stress_earlier or '—'}",
        f"Hydration (oz) — recent 15d avg: {hydration_recent or '—'}  |  earlier 15d avg: {hydration_earlier or '—'}",
        f"Migraine-free days in window: {len(free_entries)} / {len(entries)}",
        "",
        "=== HIGH-EFFECTIVENESS RELIEF METHODS (≥7/10) ===",
        "\n".join(relief_summary) if relief_summary else "None logged with effectiveness ≥ 7 yet.",
        "",
        "=== 30-DAY STATS ===",
        f"Migraine days (30d):  {stats.get('migraine_days_last_30d', 0)}",
        f"Avg pain level (30d): {stats.get('avg_pain_level_last_30d', 0)}",
        f"Trend:                {stats.get('pain_trend_direction', 'stable')}",
        f"MOH alert active:     {stats.get('moh_alert_active', False)}",
        "",
        "=== CURRENT PROTOCOL (for reference — do not duplicate) ===",
    ]

    if existing_protocol and existing_protocol.get("active_items"):
        for item in existing_protocol["active_items"]:
            lines.append(f"  • {item.get('intervention', '')} — {item.get('dose_or_detail', '')}")
    else:
        lines.append("  No protocol established yet.")

    lines += [
        "",
        "=== RESEARCH FINDINGS IN RECORDS ===",
        "\n".join(state.get("research_findings", [])) or "None recorded yet.",
        "",
        "=== PATTERN SUMMARY ===",
        state.get("session_history_summary", "Not yet available."),
    ]

    return "\n".join(lines)


def run(state: MigraineState) -> dict:
    since = date.today() - timedelta(days=30)
    with Session(engine) as session:
        entries = list_recent(session, limit=60, since=since)

    context = _build_context(state, entries)

    response = _llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
    ])

    return {
        "current_agent": "preventive_care",
        "messages": [response],
    }
