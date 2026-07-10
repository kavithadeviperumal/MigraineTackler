from fastapi import APIRouter, Depends
from sqlmodel import Session, col, delete

from app.api.deps import get_current_user
from app.database import get_session_dep
from app.models.log_entry import LogEntry
from app.models.user import User

router = APIRouter()


@router.post("/reset", tags=["dev"])
def reset_all_data(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """Wipe the current user's log entries and agent state. Dev only — not mounted in production."""
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
