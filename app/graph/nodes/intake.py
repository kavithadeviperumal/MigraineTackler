from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlmodel import Session

from app.graph.state import MigraineState
from app.database import engine
from app.models.log_entry import LogEntry
from app.config import settings

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    max_tokens=1024,
)

SYSTEM_PROMPT = """\
You are the Intake Agent for MigraineTackler. You receive a freshly saved log \
record after the user has filled the structured form. Your job is to read what \
was captured, identify what is missing or ambiguous, and ask exactly 1–2 \
targeted follow-up questions to deepen the record.

You are a skilled clinical interviewer — curious, specific, non-judgmental. \
You do not diagnose. You do not give advice. You draw out better data.

## What to Look For (in priority order)

1. HIGH-SIGNAL MISSING FIELDS — if migraine occurred and any of these are blank, ask first:
   - Pain location (maps to medical framework)
   - Prodrome symptoms (diagnostically important)
   - Chemical or fragrance exposure (commonly underreported)
   - Menstrual cycle day (hormonal pattern is a top driver)

2. AMBIGUOUS FREE-TEXT NOTES — if notes are vague, ask one specific clarifier:
   - "When you say X — was that before or after the headache started?"
   - "What kind of stress — sustained mental load, conflict, or deadline crunch?"

3. NOVEL / UNUSUAL EXPOSURES — scan foods, supplements, traditional_medicine, chemical_exposure,
   and notes for anything that does not appear in the standard migraine trigger list AND looks
   one-off or outside normal routine (new supplement, unfamiliar ingredient, new cleaning product,
   herbal remedy, protein powder, essential oil, etc.). If you spot one, ask:
   "I noticed you mentioned [X] — is that a regular part of your day, or something new you tried?"
   Their answer should be captured as a novel exposure so the system can watch for correlation.
   Novel exposures already logged are shown in the NOVEL EXPOSURES line below.

4. KNOWN TRIGGERS NOT LOGGED — cross-reference confirmed triggers in memory:
   - "You haven't mentioned [known trigger] today — any exposure?"

5. MEDICATION DETAIL — if medication logged but effectiveness/timing missing:
   - "How long after taking [medication] did pain ease?"

6. ANOMALOUS PATTERNS — migraine with no triggers, or triggers present but no migraine:
   - Surface it specifically and ask what felt different.

## Rules
- Ask maximum 2 questions. Quality over quantity.
- Be specific — never ask "how do you feel?"
- Frame conversationally, not like a form.
- After user responds: one sentence confirming record is updated, then stop.

## Output Format
1. One brief acknowledgment sentence (e.g. "Logged — pain 7, left temporal.")
2. Your 1–2 follow-up questions (numbered)
"""


def _opt(v, suffix: str = "") -> str:
    return f"{v}{suffix}" if v is not None else "not logged"


def _list_or(v: list | None, fallback: str = "none logged") -> str:
    return ", ".join(v) if v else fallback


def _build_log_context(entry: LogEntry, stats: dict, state: MigraineState) -> str:
    yn = lambda v: "Yes" if v else "No"

    lines = [
        f"=== LOG ENTRY: {entry.entry_date} ===",
        f"Migraine occurred: {yn(entry.migraine_occurred)}",
    ]

    if entry.migraine_occurred:
        lines += [
            f"Pain level: {_opt(entry.pain_level, '/10')}",
            f"Pain location: {_opt(entry.pain_location)}",
            f"Pain quality: {_opt(entry.pain_quality)}",
            f"Duration: {_opt(entry.duration_hours, ' hours')}",
        ]

    lines += [
        "",
        f"PRODROME:   {_list_or(entry.prodrome_symptoms)}",
        f"POSTDROME:  {_list_or(entry.postdrome_symptoms)}",
        "",
        f"DIET:        {_list_or(entry.foods)}",
        f"HYDRATION:   {_opt(entry.hydration_oz, ' oz')}",
        f"CAFFEINE:    {_opt(entry.caffeine_mg, ' mg')}",
        f"ALCOHOL:     {_opt(entry.alcohol_drinks, ' standard drinks')}",
        f"MEALS SKIPPED: {_list_or(entry.meals_skipped, 'none')}",
        f"FASTING:     {_opt(entry.fasting_hours, 'h without food')}",
        "",
        f"SUPPLEMENTS: {_list_or(entry.supplements, 'none')}",
        f"MEDICATIONS: {_list_or(entry.medications, 'none')}",
        "",
        f"SLEEP:       {_opt(entry.sleep_hours, ' hrs')} (quality {_opt(entry.sleep_quality, '/10')})"
        f", bedtime {_opt(entry.bedtime)}, wake {_opt(entry.wake_time)}",
        f"STRESS:      level {_opt(entry.stress_level, '/10')} — {_opt(entry.stress_source)}",
        f"CHEMICALS:   {_list_or(entry.chemical_exposure, 'none')}"
        f", fragrance: {yn(entry.fragrance_exposure) if entry.fragrance_exposure is not None else 'not logged'}",
        f"EXERCISE:    {_opt(entry.exercise_type)}, {_opt(entry.exercise_minutes, ' min')}",
        f"SCREEN:      {_opt(entry.screen_hours, ' hrs')}",
        f"NECK:        {_opt(entry.neck_tension, '/10')}",
        f"HORMONAL:    cycle day {_opt(entry.menstrual_cycle_day)}, {_opt(entry.hormonal_notes)}",
        f"GUT:         Bristol {_opt(entry.bowel_quality)}"
        f", bloating: {yn(entry.bloating) if entry.bloating is not None else 'not logged'}",
        f"RELIEF:      {_list_or(entry.relief_methods, 'none')} (effectiveness {_opt(entry.relief_effectiveness, '/10')})",
        "",
        f"LOCATION:    {entry.location_city or 'not detected (using default city)'}",
        f"WEATHER:     {_opt(entry.barometric_pressure_hpa, ' hPa')}"
        f", delta {_opt(entry.pressure_delta_24h, ' hPa/24h')}"
        f", {_opt(entry.temperature_f, '°F')}, AQI {_opt(entry.aqi)}",
        "",
        f"NOTES:       {entry.notes or 'none'}",
        f"NOVEL EXPOSURES: {_list_or(entry.novel_exposures, 'none flagged')}",
    ]

    confirmed = state.get("confirmed_triggers", [])
    suspected = state.get("suspected_triggers", [])
    hypothesis = state.get("current_root_cause_hypothesis", "")
    unknown_candidates = state.get("unknown_trigger_candidates", [])

    lines += [
        "",
        "=== LONG-TERM MEMORY ===",
        f"Confirmed triggers:       {_list_or(confirmed, 'none yet')}",
        f"Suspected triggers:       {_list_or(suspected, 'none yet')}",
        f"Unknown candidates:       {_list_or(unknown_candidates, 'none yet')}",
        f"Current hypothesis:       {hypothesis or 'not yet established'}",
        "",
        "=== 30-DAY STATS ===",
        f"Migraine-free streak:  {stats.get('migraine_free_streak_days', 0)} days",
        f"Migraines last 30d:    {stats.get('migraine_days_last_30d', 0)}",
        f"Avg pain (30d):        {stats.get('avg_pain_level_last_30d', 0)}",
        f"Trend:                 {stats.get('pain_trend_direction', 'stable')}",
        f"Top triggers:          {_list_or(stats.get('top_5_triggers_last_30d', []), 'insufficient data')}",
    ]

    # Pre-compute missing high-signal fields so the agent doesn't re-derive them
    if entry.migraine_occurred:
        missing = []
        if not entry.pain_location:
            missing.append("pain location")
        if not entry.prodrome_symptoms:
            missing.append("prodrome symptoms")
        if entry.chemical_exposure is None and entry.fragrance_exposure is None:
            missing.append("chemical/fragrance exposure")
        if entry.menstrual_cycle_day is None:
            missing.append("menstrual cycle day")
        if missing:
            lines += ["", f"MISSING HIGH-SIGNAL FIELDS: {', '.join(missing)}"]

    return "\n".join(lines)


def run(state: MigraineState) -> dict:
    log_id = state.get("current_log_id")
    if not log_id:
        return {"current_agent": "intake"}

    with Session(engine) as session:
        entry = session.get(LogEntry, log_id)

    if entry is None:
        return {"current_agent": "intake"}

    stats = state.get("deterministic_stats", {})
    context = _build_log_context(entry, stats, state)

    prior_messages = list(state.get("messages", []))
    if not prior_messages:
        # First turn — inject the saved log as the human message
        input_messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=context),
        ]
    else:
        # Subsequent turn — user has responded to the follow-up questions
        input_messages = [SystemMessage(content=SYSTEM_PROMPT)] + prior_messages

    response = _llm.invoke(input_messages)

    return {
        "messages": [response],
        "current_agent": "intake",
    }
