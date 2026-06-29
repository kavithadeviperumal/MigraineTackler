import logging
from datetime import date, timedelta

from pydantic import ValidationError
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from sqlmodel import Session

from app.graph.state import MigraineState
from app.database import engine
from app.services.log_service import list_recent
from app.config import settings
from app.graph.nodes.schemas import PatternOutput

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    max_tokens=2048,
    temperature=0,
)
_structured_llm = _llm.with_structured_output(PatternOutput)
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

## Rules
- Only list triggers backed by at least 2 occurrences in the data
- Be specific ("sleep < 6 hours" not just "poor sleep")
- Return empty lists if data is insufficient — do not guess
- unknown_trigger_candidates: only items from novel_exposures fields that appear on ≥2 migraine
  days — never guess or include standard trigger list items here
- If there are ZERO migraine days in the window: set pattern_summary to one sentence stating
  there are no migraine days to analyze, and return empty lists for all trigger fields.
  Do NOT speculate about what might become a trigger.
"""


def _format_entries(entries: list) -> str:
    if not entries:
        return "No log entries found for the analysis window."

    migraine_count = sum(1 for e in entries if e.migraine_occurred)
    lines = [
        f"Total entries in window: {len(entries)}",
        f"Migraine days: {migraine_count}",
        f"Non-migraine days: {len(entries) - migraine_count}",
        "",
    ]

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


def run(state: MigraineState) -> dict:
    since = date.today() - timedelta(days=60)

    with Session(engine) as session:
        entries = list_recent(session, limit=60, since=since)

    context = _format_entries(entries)

    try:
        result: PatternOutput = _invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=context),
        ])
    except Exception as exc:
        _logger.warning("pattern: LLM invoke failed: %s", exc)
        return {
            "current_agent": "pattern",
            "messages": [AIMessage(content="Pattern analysis failed — AI service error. Please try again in a moment.")],
        }

    updates: dict = {
        "current_agent": "pattern",
        "session_history_summary": result.pattern_summary,
    }

    if result.confirmed_triggers:
        updates["confirmed_triggers"] = result.confirmed_triggers
    if result.suspected_triggers:
        updates["suspected_triggers"] = result.suspected_triggers
    if result.unknown_trigger_candidates:
        updates["unknown_trigger_candidates"] = result.unknown_trigger_candidates

    return updates
