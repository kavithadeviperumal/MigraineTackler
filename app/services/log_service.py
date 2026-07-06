from datetime import date

from sqlmodel import Session, col, select

from app.models.log_entry import LogEntry
from app.rules.rules_engine import check_moh, check_red_flags
from app.services.weather_service import append_weather


class LogCreateResult:
    __slots__ = (
        "entry",
        "red_flag",
        "red_flag_symptoms",
        "moh_alert",
        "triptan_days",
        "nsaid_days",
    )

    def __init__(
        self,
        entry: LogEntry,
        red_flag: bool,
        red_flag_symptoms: list[str],
        moh_alert: bool,
        triptan_days: int,
        nsaid_days: int,
    ):
        self.entry = entry
        self.red_flag = red_flag
        self.red_flag_symptoms = red_flag_symptoms
        self.moh_alert = moh_alert
        self.triptan_days = triptan_days
        self.nsaid_days = nsaid_days


def create(session: Session, data: dict) -> LogCreateResult:
    """
    Persist a new LogEntry then run deterministic safety checks.
    Safety checks run after save so rules_engine can query the full 30-day window
    including the entry just written.
    """
    city = data.pop("city", None)

    entry = LogEntry(**data)
    session.add(entry)
    session.commit()
    session.refresh(entry)

    append_weather(session, entry, city=city)

    red_flag, red_flag_symptoms = check_red_flags(entry.notes or "", entry.prodrome_symptoms)
    moh_alert, triptan_days, nsaid_days = check_moh(
        session, entry.entry_date, user_id=entry.user_id
    )

    return LogCreateResult(
        entry=entry,
        red_flag=red_flag,
        red_flag_symptoms=red_flag_symptoms,
        moh_alert=moh_alert,
        triptan_days=triptan_days,
        nsaid_days=nsaid_days,
    )


def get(session: Session, log_id: int) -> LogEntry | None:
    return session.get(LogEntry, log_id)


def list_recent(
    session: Session,
    limit: int = 30,
    since: date | None = None,
    user_id: int | None = None,
) -> list[LogEntry]:
    stmt = select(LogEntry).order_by(col(LogEntry.entry_date).desc())
    if since:
        stmt = stmt.where(LogEntry.entry_date >= since)
    if user_id is not None:
        stmt = stmt.where(LogEntry.user_id == user_id)
    stmt = stmt.limit(limit)
    return list(session.exec(stmt).all())
