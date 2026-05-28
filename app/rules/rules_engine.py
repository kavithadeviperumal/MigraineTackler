from datetime import date, timedelta
from collections import Counter
from dataclasses import dataclass, field
from sqlmodel import Session, select
from app.models.log_entry import LogEntry
from app.graph.state import DeterministicStats


# ── Thresholds ────────────────────────────────────────────────────────────────
MOH_TRIPTAN_THRESHOLD = 10    # days in 30-day window
MOH_NSAID_THRESHOLD = 15

RED_FLAG_SYMPTOMS = {
    "worst headache of life",
    "thunderclap",
    "fever and stiff neck",
    "neurological deficit",
    "vision loss",
    "confusion",
    "weakness one side",
    "new pattern after 50",
    "headache after head injury",
    "headache on exertion",
}


# ── Public API ────────────────────────────────────────────────────────────────

def check_red_flags(notes: str, prodrome: list[str] | None) -> tuple[bool, list[str]]:
    """
    Returns (alert_active, matched_flags).
    Checks free-text notes and prodrome list for emergency symptoms.
    This runs before any agent is invoked — safety is always first.
    """
    text = (notes or "").lower()
    symptoms = [s.lower() for s in (prodrome or [])]
    combined = text + " " + " ".join(symptoms)

    matched = [flag for flag in RED_FLAG_SYMPTOMS if flag in combined]
    return bool(matched), matched


def check_moh(
    session: Session, as_of: date | None = None, user_id: int | None = None
) -> tuple[bool, int, int]:
    """
    Returns (alert_active, triptan_days, nsaid_days) over the rolling 30-day window.
    MOH = Medication Overuse Headache.
    """
    cutoff = (as_of or date.today()) - timedelta(days=30)
    stmt = select(LogEntry).where(LogEntry.entry_date >= cutoff)
    if user_id is not None:
        stmt = stmt.where(LogEntry.user_id == user_id)
    entries = session.exec(stmt).all()

    triptan_days = sum(
        1 for e in entries
        if e.medications and any("triptan" in m.lower() for m in e.medications)
    )
    nsaid_days = sum(
        1 for e in entries
        if e.medications and any(
            kw in m.lower()
            for m in e.medications
            for kw in ("ibuprofen", "naproxen", "aspirin", "nsaid", "excedrin")
        )
    )

    alert = triptan_days >= MOH_TRIPTAN_THRESHOLD or nsaid_days >= MOH_NSAID_THRESHOLD
    return alert, triptan_days, nsaid_days


def compute_streak(
    session: Session, as_of: date | None = None, user_id: int | None = None
) -> int:
    """Returns number of consecutive migraine-free days ending on as_of (inclusive)."""
    today = as_of or date.today()
    streak = 0
    check_date = today

    while True:
        stmt = select(LogEntry).where(LogEntry.entry_date == check_date)
        if user_id is not None:
            stmt = stmt.where(LogEntry.user_id == user_id)
        entry = session.exec(stmt).first()

        if entry is None or not entry.migraine_occurred:
            streak += 1
            check_date -= timedelta(days=1)
            # Stop looking back beyond 365 days to avoid infinite loops on new installs
            if streak > 365:
                break
        else:
            break

    return streak


def top_triggers(
    session: Session, n: int = 5, days: int = 30, as_of: date | None = None, user_id: int | None = None
) -> list[str]:
    """
    Returns the top-n trigger labels by frequency over the last `days` days.
    Only counts entries where migraine_occurred is True.
    """
    cutoff = (as_of or date.today()) - timedelta(days=days)
    stmt = select(LogEntry).where(
        LogEntry.entry_date >= cutoff,
        LogEntry.migraine_occurred == True,  # noqa: E712
    )
    if user_id is not None:
        stmt = stmt.where(LogEntry.user_id == user_id)
    entries = session.exec(stmt).all()

    counter: Counter = Counter()
    for e in entries:
        if e.foods:
            counter.update(e.foods)
        if e.chemical_exposure:
            counter.update(e.chemical_exposure)
        if e.stress_level and e.stress_level >= 7:
            counter["high_stress"] += 1
        if e.sleep_hours and e.sleep_hours < 6:
            counter["poor_sleep"] += 1
        if e.pressure_delta_24h and abs(e.pressure_delta_24h) >= 5:
            counter["barometric_change"] += 1
        if e.fragrance_exposure:
            counter["fragrance_exposure"] += 1
        if e.caffeine_mg and e.caffeine_mg == 0:
            counter["caffeine_withdrawal"] += 1
        if e.alcohol_drinks and e.alcohol_drinks > 0:
            counter["alcohol"] += 1
        if e.meals_skipped:
            counter["meal_skipping"] += 1
        if e.fasting_hours is not None and e.fasting_hours >= 5:
            counter["fasting"] += 1
        if e.novel_exposures:
            counter.update(e.novel_exposures)

    return [label for label, _ in counter.most_common(n)]


def pain_trend(
    session: Session, as_of: date | None = None, user_id: int | None = None
) -> tuple[float, float, str]:
    """
    Returns (avg_7d, avg_30d, direction).
    direction: 'improving' | 'worsening' | 'stable'
    Only includes entries where migraine_occurred is True.
    """
    today = as_of or date.today()

    def avg_pain(days: int) -> float:
        cutoff = today - timedelta(days=days)
        stmt = select(LogEntry).where(
            LogEntry.entry_date >= cutoff,
            LogEntry.migraine_occurred == True,  # noqa: E712
            LogEntry.pain_level.is_not(None),
        )
        if user_id is not None:
            stmt = stmt.where(LogEntry.user_id == user_id)
        entries = session.exec(stmt).all()
        if not entries:
            return 0.0
        return sum(e.pain_level for e in entries) / len(entries)

    avg_7 = avg_pain(7)
    avg_30 = avg_pain(30)

    if avg_7 == 0 or avg_30 == 0:
        direction = "stable"
    elif avg_7 < avg_30 - 0.5:
        direction = "improving"
    elif avg_7 > avg_30 + 0.5:
        direction = "worsening"
    else:
        direction = "stable"

    return avg_7, avg_30, direction


LOAD_THRESHOLD = 10.0

# Clinical lookback window per trigger (in days).
# A trigger on day D contributes to the rolling load for all days D through D+window-1.
# Sources: Rains & Poceta 2006; Houle et al. 2012; Griffiths et al. 1995;
#          Okuma et al. 2015; Mukamal et al. 2009; Fernández-de-Las-Peñas et al.
TRIGGER_WINDOWS: dict[str, int] = {
    "sleep_deprivation": 3,    # cumulative sleep debt over 3 nights
    "poor_sleep": 3,
    "poor_sleep_quality": 3,
    "severe_stress": 5,        # letdown migraine can fire up to 5 days post-stressor
    "high_stress": 5,
    "caffeine_withdrawal": 2,  # withdrawal peaks at 20–51h (Griffiths 1995)
    "barometric_shift": 2,     # effect within 24–48h (Okuma 2015)
    "neck_tension": 3,         # cervicogenic contribution over 2–3 days
    "alcohol": 1,              # acute — cleared within 24h
    "caffeine_excess": 1,
    "hormonal_peak": 1,        # phase-based; present each day of phase, no carryover
    "fragrance_exposure": 1,
    "dehydration": 1,
    "trigger_foods": 1,
    "meal_skipping": 1,    # hypoglycemia is acute; resolves with next meal
    "fasting": 1,
    "novel_exposure": 2,   # unknown substance — 2-day window covers delayed reactions
}


@dataclass
class ToxicLoad:
    today_score: float
    carryover_score: float     # contributions from prior days still within their window
    rolling_score: float
    threshold: float
    fill_pct: float            # 0–100, capped at 100
    risk_level: str            # low | moderate | high | critical
    breakdown: dict[str, float] = field(default_factory=dict)


def daily_load_score(entry: LogEntry) -> tuple[float, dict[str, float]]:
    """Compute single-day trigger load for one LogEntry. Returns (score, breakdown)."""
    breakdown: dict[str, float] = {}

    def add(label: str, value: float) -> None:
        breakdown[label] = round(value, 2)

    if entry.sleep_hours is not None:
        if entry.sleep_hours < 5:
            add("sleep_deprivation", 3.5)
        elif entry.sleep_hours < 6:
            add("poor_sleep", 2.0)

    if entry.sleep_quality is not None and entry.sleep_quality <= 3:
        add("poor_sleep_quality", 1.0)

    if entry.stress_level is not None:
        if entry.stress_level >= 9:
            add("severe_stress", 2.5)
        elif entry.stress_level >= 7:
            add("high_stress", 1.5)

    if entry.alcohol_drinks:
        add("alcohol", min(round(entry.alcohol_drinks * 1.5, 2), 3.0))

    if entry.caffeine_mg == 0:
        add("caffeine_withdrawal", 2.0)
    elif entry.caffeine_mg and entry.caffeine_mg > 400:
        add("caffeine_excess", 1.0)

    if entry.menstrual_cycle_day is not None:
        if entry.menstrual_cycle_day >= 24 or entry.menstrual_cycle_day <= 2:
            add("hormonal_peak", 2.5)

    if entry.pressure_delta_24h is not None:
        delta = abs(entry.pressure_delta_24h)
        if delta >= 8:
            add("barometric_shift", 2.5)
        elif delta >= 5:
            add("barometric_shift", 1.5)

    if entry.fragrance_exposure:
        add("fragrance_exposure", 1.0)

    if entry.neck_tension is not None and entry.neck_tension >= 7:
        add("neck_tension", 1.5)

    if entry.hydration_oz is not None and entry.hydration_oz < 40:
        add("dehydration", 1.0)

    if entry.meals_skipped:
        n = len(entry.meals_skipped)
        add("meal_skipping", 2.5 if n >= 2 else 1.5)

    if entry.fasting_hours is not None:
        if entry.fasting_hours >= 8:
            add("fasting", 2.0)
        elif entry.fasting_hours >= 5:
            add("fasting", 1.0)

    if entry.foods:
        trigger_foods = [
            f for f in entry.foods
            if f in {
                "alcohol", "beer", "red_wine", "chocolate", "aged_cheese",
                "processed_meat", "MSG", "artificial_sweeteners", "citrus",
                "fermented_foods", "tyramine_rich_foods", "yeast_extract",
            }
        ]
        if trigger_foods:
            add("trigger_foods", min(round(len(trigger_foods) * 0.3, 2), 1.5))

    if entry.novel_exposures:
        # Each unknown substance adds uncertainty load; capped to avoid over-weighting
        add("novel_exposure", min(round(len(entry.novel_exposures) * 0.5, 2), 1.5))

    total = round(sum(breakdown.values()), 2)
    return total, breakdown


def rolling_load(
    session: Session, as_of: date | None = None, user_id: int | None = None
) -> ToxicLoad:
    """
    Compute rolling toxic load using trigger-specific clinical windows.
    Fetches up to 5 days of entries (max window = 5 for stress triggers).
    Each trigger only contributes for the number of days supported by evidence.
    """
    today = as_of or date.today()
    max_window = max(TRIGGER_WINDOWS.values())

    entries_by_offset: dict[int, LogEntry] = {}
    for offset in range(max_window):
        stmt = select(LogEntry).where(LogEntry.entry_date == today - timedelta(days=offset))
        if user_id is not None:
            stmt = stmt.where(LogEntry.user_id == user_id)
        entry = session.exec(stmt).first()
        if entry:
            entries_by_offset[offset] = entry

    rolling = 0.0
    carryover = 0.0
    today_bd: dict[str, float] = {}

    for offset, entry in entries_by_offset.items():
        _, bd = daily_load_score(entry)
        for trigger, score in bd.items():
            if offset < TRIGGER_WINDOWS.get(trigger, 1):
                rolling += score
                if offset == 0:
                    today_bd[trigger] = score
                else:
                    carryover += score

    rolling = round(rolling, 2)
    carryover = round(carryover, 2)
    today_score = round(rolling - carryover, 2)
    fill_pct = round(min(rolling / LOAD_THRESHOLD * 100, 100), 1)

    if rolling < 4:
        risk = "low"
    elif rolling < 7:
        risk = "moderate"
    elif rolling < 10:
        risk = "high"
    else:
        risk = "critical"

    return ToxicLoad(
        today_score=today_score,
        carryover_score=carryover,
        rolling_score=rolling,
        threshold=LOAD_THRESHOLD,
        fill_pct=fill_pct,
        risk_level=risk,
        breakdown=today_bd,
    )


def build_deterministic_stats(
    session: Session, as_of: date | None = None, user_id: int | None = None
) -> DeterministicStats:
    """
    Assembles all deterministic stats into a single object.
    Called by the context builder before every agent invocation.
    """
    today = as_of or date.today()
    cutoff_30 = today - timedelta(days=30)

    moh_alert, triptan_days, nsaid_days = check_moh(session, today, user_id=user_id)
    streak = compute_streak(session, today, user_id=user_id)
    triggers = top_triggers(session, n=5, days=30, as_of=today, user_id=user_id)
    _, avg_30, direction = pain_trend(session, today, user_id=user_id)

    migraine_stmt = select(LogEntry).where(
        LogEntry.entry_date >= cutoff_30,
        LogEntry.migraine_occurred == True,  # noqa: E712
    )
    if user_id is not None:
        migraine_stmt = migraine_stmt.where(LogEntry.user_id == user_id)
    migraine_days_30 = session.exec(migraine_stmt).all()

    total_stmt = select(LogEntry)
    if user_id is not None:
        total_stmt = total_stmt.where(LogEntry.user_id == user_id)
    total = session.exec(total_stmt).all()

    return DeterministicStats(
        migraine_free_streak_days=streak,
        migraine_days_last_30d=len(migraine_days_30),
        avg_pain_level_last_30d=round(avg_30, 1),
        pain_trend_direction=direction,
        triptan_days_last_30d=triptan_days,
        nsaid_days_last_30d=nsaid_days,
        moh_alert_active=moh_alert,
        top_5_triggers_last_30d=triggers,
        total_events_logged=len(total),
    )
