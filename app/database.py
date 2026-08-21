from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, create_engine

from app.config import settings

_PROJECT_ROOT = Path(__file__).parent.parent


def _engine_url() -> str:
    url = settings.database_url
    # Supabase pooler appends ?pgbouncer=true as a docs hint; psycopg passes
    # all query params to libpq as connection options and rejects unknown ones.
    url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    # Normalize to postgresql+psycopg:// for SQLAlchemy 2.x + psycopg3.
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_engine_url(), echo=False, pool_size=10, max_overflow=20)


def create_db_and_tables() -> None:
    from sqlalchemy import inspect

    from alembic import command  # type: ignore[attr-defined]
    from alembic.config import Config

    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))

    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        # Tables exist but alembic_version doesn't — DB was created outside
        # Alembic (e.g. earlier manual run). Stamp head so upgrade is a no-op.
        if "users" in tables and "alembic_version" not in tables:
            command.stamp(cfg, "head")

    command.upgrade(cfg, "head")


def get_session() -> Session:
    return Session(engine)


def get_session_dep() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
