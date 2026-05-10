import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlmodel import Session, SQLModel, delete

from app.database import create_db_and_tables, engine, get_session_dep
from app.config import settings
from app.api.deps import get_current_user
from app.models.user import User
from app.models.log_entry import LogEntry
from app.api.routes import logs, analyze, auth, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    create_db_and_tables()
    yield


app = FastAPI(title="MigraineTackler API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])


@app.post("/reset", tags=["dev"])
def reset_all_data(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """Wipe the current user's log entries and agent state."""
    session.exec(delete(LogEntry).where(LogEntry.user_id == current_user.id))
    session.commit()

    thread_id = f"user_{current_user.id}"
    import app.graph.graph as _graph_module
    if _graph_module._graph is not None:
        conn = _graph_module._graph.checkpointer.conn
        cur = conn.cursor()
        cur.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))
        cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = ?", (thread_id,))
        conn.commit()

    return {"status": "reset complete"}
