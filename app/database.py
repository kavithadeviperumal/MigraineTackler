from collections.abc import Generator
from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine
from app.config import settings
import app.models.user  # noqa: F401 — register User table with SQLModel metadata
import app.models.user_profile  # noqa: F401 — register UserProfile table

# SQLite URL — forward slashes work on all platforms with SQLAlchemy
_db_url = f"sqlite:///{settings.db_path}"

engine = create_engine(
    _db_url,
    echo=False,
    connect_args={"check_same_thread": False},  # needed for SQLite + multi-thread
)


def create_db_and_tables() -> None:
    """Create all tables defined in SQLModel models. Safe to call on every startup."""
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Add columns introduced after initial schema without dropping existing data."""
    new_columns = [
        "ALTER TABLE log_entries ADD COLUMN location_city TEXT",
        "ALTER TABLE log_entries ADD COLUMN meals_skipped TEXT",
        "ALTER TABLE log_entries ADD COLUMN fasting_hours REAL",
        "ALTER TABLE log_entries ADD COLUMN user_id INTEGER REFERENCES users(id)",
    ]
    with engine.connect() as conn:
        for stmt in new_columns:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists


def get_session() -> Session:
    """Return a new SQLModel session. Caller is responsible for closing it."""
    return Session(engine)


def get_session_dep() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a session and closes it after the request."""
    with Session(engine) as session:
        yield session
