import pytest
from sqlmodel import create_engine, SQLModel, Session
from fastapi.testclient import TestClient

import app.database as db_module
from app.database import get_session_dep
from app.api.main import app


@pytest.fixture(autouse=True)
def test_engine(monkeypatch):
    """
    Replaces the module-level engine with an in-memory SQLite engine for every test.
    autouse=True means every test gets a fresh, isolated DB automatically.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    return engine


@pytest.fixture
def session(test_engine):
    """Yields a live session against the in-memory test DB."""
    with Session(test_engine) as s:
        yield s


@pytest.fixture
def client(session):
    """
    FastAPI TestClient with the DB session dependency overridden.
    Route handlers get the same in-memory session as the test body.
    """
    def override():
        yield session

    app.dependency_overrides[get_session_dep] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
