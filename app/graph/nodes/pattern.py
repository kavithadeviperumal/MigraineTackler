import json
import re
from datetime import date, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlmodel import Session

from app.graph.state import MigraineState
from app.database import engine
from app.services.log_service import list_recent
from app.config import settings

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    max_tokens=2048,
)

SYSTEM_PROMPT = """\
You are the Pattern Agent for MigraineTackler. You receive a structured history of migraine \
log entries and your job is to identify patterns, correlations, and trends.

You are a skilled data analyst with clinical knowledge of migraine triggers. You do not diagnose. \
You surface patterns from the data.

## What to Analyze

1. TRIGGER CORRELATIONS — what factors appear consistently before migraine days:
   - Sleep: hours, quality, bedtime consistency
   - Stress: level and source
   - Diet: specific foods, hydration, caffeine, alcohol, meal skipping, fasting duration
   - Hormonal: cycle day patterns
   - Weather: barometric pressure changes
   - Physical: neck tension, exercise
   - Chemical/fragrance exposure
   - Novel exposures: items in the novel_exposures field that are NOT in the standard trigger
     list. Treat each as an unknown variable. If a novel item appears on ≥2 migraine days,
     flag it as an unknown_trigger_candidate. Be specific about the item name.

2. PROTECTIVE FACTORS — what appears on migraine-free days but not migraine days

3. TRENDS — is frequency / pain level improving or worsening over the window?

4. CONFIDENCE — distinguish:
   - Confirmed trigger: appears before ≥70% of migraine days in the data
   - Suspected trigger: appears before 40–69% of migraine days
   - Weak signal: below 40% — omit from lists

## Output Format

Respond with exactly two sections:

### PATTERN SUMMARY
2–4 sentences, conversational and clinical. Lead with the most actionable finding. \
If there is insufficient data (fewer than 4 entries), say so clearly.

### STRUCTURED DATA
```json
{
  "confirmed_triggers": ["..."],
  "suspected_triggers": ["..."],
  "unknown_trigger_candidates": ["..."],
  "key_insight": "one sentence — the single most important finding",
  "trend": "improving | worsening | stable"
}
```

Rules:
- Only list triggers backed by at least 2 occurrences in the data
- Be specific ("sleep < 6 hours" not just "poor sleep")
- Return empty lists if data is insufficient — do not guess
- unknown_trigger_candidates: only items from novel_exposures fields that appear on ≥2 migraine
  days — never guess or include standard trigger list items here
"""


def _format_entries(entries: list) -> str:
    if not entries:
        return "No log entries found for the analysis window."

    lines = [f"Total entries in window: {len(entries)}", ""]

    for e in entries:
        yn = lambda v: "Yes" if v else "No"
        opt = lambda v, suffix="": f"{v}{suffix}" if v is not None else "—"
        lst = lambda v: ", ".join(v) if v else "none"

        lines.append(f"--- {e.entry_date} | Migraine: {yn(e.migraine_occurred)} ---")
        if e.migraine_occurred:
            lines.append(
                f"  Pain: {opt(e.pain_level, '/10')} | Location: {opt(e.pain_location)}"
                f" | Duration: {opt(e.duration_hours, 'h')}"
            )
        lines.append(
            f"  Sleep: {opt(e.sleep_hours, 'h')} (quality {opt(e.sleep_quality, '/10')})"
            f" | Bedtime: {opt(e.bedtime)}"
        )
        lines.append(f"  Stress: {opt(e.stress_level, '/10')} — {opt(e.stress_source)}")
        lines.append(
            f"  Foods: {lst(e.foods)} | Hydration: {opt(e.hydration_oz, ' oz')}"
            f" | Caffeine: {opt(e.caffeine_mg, ' mg')} | Alcohol: {opt(e.alcohol_drinks, ' standard drinks')}"
        )
        lines.append(
            f"  Meals skipped: {lst(e.meals_skipped) if e.meals_skipped else 'none'}"
            f" | Fasting: {opt(e.fasting_hours, 'h without food')}"
        )
        lines.append(f"  Prodrome: {lst(e.prodrome_symptoms)}")
        lines.append(
            f"  Neck tension: {opt(e.neck_tension, '/10')} | Screen: {opt(e.screen_hours, 'h')}"
        )
        lines.append(
            f"  Chemical: {lst(e.chemical_exposure)}"
            f" | Fragrance: {yn(e.fragrance_exposure) if e.fragrance_exposure is not None else '—'}"
        )
        lines.append(f"  Hormonal: cycle day {opt(e.menstrual_cycle_day)}")
        lines.append(f"  Location: {e.location_city or '—'}")
        lines.append(
            f"  Weather: {opt(e.barometric_pressure_hpa, ' hPa')}"
            f" | Delta: {opt(e.pressure_delta_24h, ' hPa/24h')}"
        )
        lines.append(f"  Medications: {lst(e.medications)}")
        lines.append(f"  Notes: {e.notes or '—'}")
        lines.append(f"  Novel exposures: {lst(e.novel_exposures) if e.novel_exposures else '—'}")
        lines.append("")

    return "\n".join(lines)


def _parse_structured(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _parse_summary(text: str) -> str:
    match = re.search(r"### PATTERN SUMMARY\s*(.*?)(?=###|\Z)", text, re.DOTALL)
    return match.group(1).strip() if match else text


def run(state: MigraineState) -> dict:
    since = date.today() - timedelta(days=60)

    with Session(engine) as session:
        entries = list_recent(session, limit=60, since=since)

    context = _format_entries(entries)

    response = _llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
    ])

    text = response.content
    structured = _parse_structured(text)

    updates: dict = {
        "current_agent": "pattern",
        "messages": [response],
        "session_history_summary": _parse_summary(text),
    }

    if structured.get("confirmed_triggers"):
        updates["confirmed_triggers"] = structured["confirmed_triggers"]
    if structured.get("suspected_triggers"):
        updates["suspected_triggers"] = structured["suspected_triggers"]
    if structured.get("unknown_trigger_candidates"):
        updates["unknown_trigger_candidates"] = structured["unknown_trigger_candidates"]

    return updates
