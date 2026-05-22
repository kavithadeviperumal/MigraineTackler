from collections.abc import Generator
from sqlmodel import SQLModel, Session, create_engine
from app.config import settings


def _engine_url() -> str:
    url = settings.database_url
    # SQLAlchemy needs the psycopg driver prefix
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_engine_url(), echo=False)


def create_db_and_tables() -> None:
    import app.models.user        # noqa: F401 — register with SQLModel metadata
    import app.models.user_profile  # noqa: F401
    import app.models.log_entry   # noqa: F401
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def get_session_dep() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
