import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from sqlmodel import Session, col, delete

from app.api.deps import get_current_user
from app.api.routes import analyze, auth, knowledge, logs, profile, shortcut
from app.database import create_db_and_tables, engine, get_session_dep
from app.mcp_server.auth_middleware import MCPAuthMiddleware
from app.mcp_server.server import mcp
from app.models.log_entry import LogEntry
from app.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    from app.graph.graph import get_graph

    threading.Thread(target=get_graph, daemon=True).start()

    def _seed_guidelines():
        from app.services.guideline_seeder import seed_guidelines

        with Session(engine) as session:
            seed_guidelines(session)

    threading.Thread(target=_seed_guidelines, daemon=True).start()
    yield


app = FastAPI(title="MigraineTackler API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
app.include_router(shortcut.router, prefix="/shortcut", tags=["shortcut"])
app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])

app.mount("/mcp", MCPAuthMiddleware(mcp.streamable_http_app()))


@app.get("/health/ready", tags=["ops"], include_in_schema=False)
def health_ready(response: Response):
    from app.graph.graph import is_graph_ready

    if not is_graph_ready():
        response.status_code = 503
        return {"status": "not_ready", "reason": "graph compiling"}
    return {"status": "ready"}


@app.post("/reset", tags=["dev"])
def reset_all_data(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """Wipe the current user's log entries and agent state."""
    session.exec(delete(LogEntry).where(col(LogEntry.user_id) == current_user.id))
    session.commit()

    thread_id = f"user_{current_user.id}"
    import app.graph.graph as _graph_module

    if _graph_module._graph is not None:
        conn = _graph_module._graph.checkpointer.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
            cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
            cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,))
        conn.commit()

    return {"status": "reset complete"}
