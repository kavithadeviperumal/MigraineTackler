"""
MigraineTackler MCP server.

Exposes migraine data as tools callable from Claude Code or any MCP client.

Usage:
    python -m app.mcp_server.server

Configuration:
    MIGRAINE_USER_ID   — which user's data to operate on (default: 1)
    DATABASE_URL       — PostgreSQL connection string (same as the main app)
"""

import os
from contextvars import ContextVar
from datetime import date

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, select

from app.database import engine
from app.models.log_entry import LogEntry
from app.models.user_profile import UserProfile
from app.rules.rules_engine import build_deterministic_stats, top_triggers

mcp = FastMCP("MigraineTackler")

# Set by MCPAuthMiddleware for HTTP requests; None means fall back to env var (stdio mode).
_current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)

_FOOD_TRIGGER_SET = {
    "alcohol", "beer", "red_wine", "chocolate", "aged_cheese",
    "processed_meat", "msg", "artificial_sweeteners", "citrus",
    "fermented_foods", "tyramine_rich_foods", "yeast_extract",
}


def _uid() -> int:
    uid = _current_user_id.get()
    if uid is not None:
        return uid
    return int(os.getenv("MIGRAINE_USER_ID", "1"))


def _summarise_triggers(e: LogEntry) -> list[str]:
    t: list[str] = []
    if e.foods:
        t.extend(e.foods)
    if e.stress_level and e.stress_level >= 7:
        t.append(f"stress_{e.stress_level}")
    if e.sleep_hours is not None and e.sleep_hours < 6:
        t.append(f"sleep_{e.sleep_hours}h")
    if e.alcohol_drinks and e.alcohol_drinks > 0:
        t.append("alcohol")
    if e.fragrance_exposure:
        t.append("fragrance")
    if e.caffeine_mg == 0:
        t.append("caffeine_withdrawal")
    if e.pressure_delta_24h and abs(e.pressure_delta_24h) >= 5:
        t.append("barometric_change")
    if e.neck_tension and e.neck_tension >= 7:
        t.append(f"neck_tension_{e.neck_tension}")
    if e.novel_exposures:
        t.extend(e.novel_exposures)
    return t


@mcp.tool()
def get_episodes(date_from: str, date_to: str) -> list[dict]:
    """
    Return migraine log entries within a date range (inclusive).

    Args:
        date_from: Start date in YYYY-MM-DD format.
        date_to:   End date in YYYY-MM-DD format.

    Returns a list of episodes with date, pain level, duration, triggers,
    medications, and notes. Includes non-migraine days where a log was recorded.
    """
    start = date.fromisoformat(date_from)
    end   = date.fromisoformat(date_to)

    with Session(engine) as session:
        stmt = (
            select(LogEntry)
            .where(
                LogEntry.user_id == _uid(),
                LogEntry.entry_date >= start,
                LogEntry.entry_date <= end,
            )
            .order_by(LogEntry.entry_date)
        )
        entries = session.exec(stmt).all()

    return [
        {
            "date":           str(e.entry_date),
            "migraine":       e.migraine_occurred,
            "pain_level":     e.pain_level,
            "duration_hours": e.duration_hours,
            "triggers":       _summarise_triggers(e),
            "medications":    e.medications or [],
            "notes":          e.notes or "",
        }
        for e in entries
    ]


@mcp.tool()
def get_triggers() -> dict:
    """
    Return the user's trigger profile: food triggers from onboarding,
    any other noted triggers, and the top 5 triggers from the last 30 days
    derived from log data.
    """
    uid = _uid()

    with Session(engine) as session:
        profile = session.exec(
            select(UserProfile).where(UserProfile.user_id == uid)
        ).first()
        top_30d = top_triggers(session, n=5, days=30, user_id=uid)

    return {
        "known_food_triggers": (profile.known_food_triggers or []) if profile else [],
        "other_triggers":      (profile.other_triggers or "") if profile else "",
        "top_5_last_30_days":  top_30d,
    }


@mcp.tool()
def get_severity_trends() -> dict:
    """
    Return severity trends and stats over the last 30 days:
    migraine day count, average pain level, trend direction (improving /
    worsening / stable), migraine-free streak, MOH risk, top 5 triggers,
    and total events logged.
    """
    with Session(engine) as session:
        stats = build_deterministic_stats(session, user_id=_uid())

    return stats.model_dump()


@mcp.tool()
def log_episode(
    entry_date: str,
    pain_level: int,
    triggers: list[str],
    notes: str = "",
    dry_run: bool = False,
) -> dict:
    """
    Log a migraine episode.

    Args:
        entry_date: Date of the episode in YYYY-MM-DD format.
        pain_level: Pain severity from 1 (mild) to 10 (worst).
        triggers:   List of trigger labels, e.g. ["poor_sleep", "red_wine", "stress"].
                    Known food triggers are stored in the foods field.
                    Behavioural triggers map to their log fields (stress, sleep, etc.).
                    Anything unrecognised is stored as a novel exposure.
        notes:      Optional free-text notes.
        dry_run:    If true, validate and return what would be logged without writing.

    Recognised behavioural trigger labels:
        poor_sleep, stress / high_stress, fragrance, caffeine_withdrawal,
        alcohol, neck_tension, barometric_change, meal_skipping, dehydration
    """
    if not 1 <= pain_level <= 10:
        return {"error": "pain_level must be between 1 and 10"}

    parsed_date = date.fromisoformat(entry_date)

    # Partition triggers into their LogEntry fields
    foods: list[str] = []
    stress_level: int | None = None
    sleep_hours: float | None = None
    fragrance_exposure: bool | None = None
    caffeine_mg: float | None = None
    alcohol_drinks: float | None = None
    neck_tension: int | None = None
    meals_skipped: list[str] | None = None
    hydration_oz: float | None = None
    novel: list[str] = []

    for t in triggers:
        label = t.lower().strip()
        if label in _FOOD_TRIGGER_SET:
            foods.append(label)
        elif label in ("stress", "high_stress"):
            stress_level = 8
        elif label == "poor_sleep":
            sleep_hours = 5.0
        elif label == "fragrance":
            fragrance_exposure = True
        elif label == "caffeine_withdrawal":
            caffeine_mg = 0
        elif label == "alcohol":
            alcohol_drinks = 1.0
        elif label == "neck_tension":
            neck_tension = 8
        elif label == "meal_skipping":
            meals_skipped = ["unknown"]
        elif label == "dehydration":
            hydration_oz = 30.0
        else:
            novel.append(t)

    entry = LogEntry(
        user_id=_uid(),
        entry_date=parsed_date,
        migraine_occurred=True,
        pain_level=pain_level,
        foods=foods or None,
        stress_level=stress_level,
        sleep_hours=sleep_hours,
        fragrance_exposure=fragrance_exposure,
        caffeine_mg=caffeine_mg,
        alcohol_drinks=alcohol_drinks,
        neck_tension=neck_tension,
        meals_skipped=meals_skipped,
        hydration_oz=hydration_oz,
        novel_exposures=novel or None,
        notes=notes or None,
    )

    if dry_run:
        return {
            "dry_run": True,
            "would_log": {
                "date":       entry_date,
                "pain_level": pain_level,
                "triggers":   triggers,
                "notes":      notes,
            },
        }

    with Session(engine) as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)

    return {
        "status":     "logged",
        "id":         entry.id,
        "date":       entry_date,
        "pain_level": pain_level,
        "triggers":   triggers,
    }


if __name__ == "__main__":
    mcp.run()
