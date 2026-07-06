from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _engine_url() -> str:
    url = settings.database_url
    # SQLAlchemy needs the psycopg driver prefix
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_engine_url(), echo=False)


def create_db_and_tables() -> None:
    # pgvector extension must exist before the vector column type is created
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    import app.models.knowledge_chunk
    import app.models.log_entry
    import app.models.user  # — register with SQLModel metadata
    import app.models.user_profile  # noqa: F401

    # Inline schema migrations — all statements are idempotent
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS home_city VARCHAR"))
        # Make knowledge_chunks.user_id nullable so shared/system chunks use NULL instead of 0.
        # Migrate any existing user_id=0 rows (guideline seeder sentinel) to NULL.
        conn.execute(text("ALTER TABLE knowledge_chunks ALTER COLUMN user_id DROP NOT NULL"))
        conn.execute(text("UPDATE knowledge_chunks SET user_id = NULL WHERE user_id = 0"))
        conn.commit()

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def get_session_dep() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
