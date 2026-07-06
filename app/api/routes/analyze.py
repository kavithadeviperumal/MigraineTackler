from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, HumanMessage
from sqlmodel import Session

from app.api.deps import get_current_user
from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.database import get_session_dep
from app.graph.graph import get_graph
from app.graph.state import default_state
from app.models.user import User
from app.rules.rules_engine import build_deterministic_stats

router = APIRouter()


@router.get("/state/me")
def get_state(current_user: User = Depends(get_current_user)):
    thread_id = f"user_{current_user.id}"
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = graph.get_state(config)
        return snapshot.values or {}
    except Exception:
        return {}


@router.post("", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    thread_id = f"user_{current_user.id}"
    graph = get_graph()
    stats = build_deterministic_stats(session, user_id=current_user.id)
    config = {"configurable": {"thread_id": thread_id}}

    state_update: dict = {
        "intent": request.intent,
        "deterministic_stats": stats.model_dump(),
        "user_id": current_user.id,
    }
    if request.current_log_id is not None:
        state_update["current_log_id"] = request.current_log_id
    if request.message:
        state_update["messages"] = [HumanMessage(content=request.message)]

    try:
        checkpoint = graph.get_state(config)
        is_new_thread = checkpoint.values == {}
    except Exception:
        is_new_thread = True

    if is_new_thread:
        full_state = {**default_state(), **state_update}
    else:
        full_state = state_update

    result = graph.invoke(full_state, config=config)

    ai_messages = [msg.content for msg in result.get("messages", []) if isinstance(msg, AIMessage)]

    return AnalyzeResponse(
        messages=ai_messages,
        moh_alert=result.get("moh_alert_active", False),
        red_flag=result.get("red_flag_active", False),
    )
