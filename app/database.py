from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, create_engine

from app.config import settings

_PROJECT_ROOT = Path(__file__).parent.parent


def _engine_url() -> str:
    url = settings.database_url
    # SQLAlchemy needs the psycopg driver prefix
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_engine_url(), echo=False)


def create_db_and_tables() -> None:
    from alembic import command  # type: ignore[attr-defined]
    from alembic.config import Config

    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    command.upgrade(cfg, "head")


def get_session() -> Session:
    return Session(engine)


def get_session_dep() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
