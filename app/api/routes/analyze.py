from fastapi import APIRouter, Depends, Request
from langchain_core.messages import AIMessage, HumanMessage
from sqlmodel import Session

from app.api.deps import get_current_user, user_limiter
from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.database import get_session_dep
from app.graph.graph import get_graph
from app.graph.state import default_state
from app.models.user import User
from app.rules.rules_engine import build_deterministic_stats, check_red_flags
from app.services import log_service

router = APIRouter()


@router.get("/state/me")
async def get_state(current_user: User = Depends(get_current_user)):
    thread_id = f"user_{current_user.id}"
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = await graph.aget_state(config)
        return snapshot.values or {}
    except Exception:
        return {}


@router.post("", response_model=AnalyzeResponse)
@user_limiter.limit("20/minute")
async def analyze(
    request: Request,
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    thread_id = f"user_{current_user.id}"
    graph = get_graph()
    stats = build_deterministic_stats(session, user_id=current_user.id)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

    state_update: dict = {
        "intent": body.intent,
        "deterministic_stats": stats.model_dump(),
        "user_id": current_user.id,
    }
    if body.current_log_id is not None:
        state_update["current_log_id"] = body.current_log_id
        entry = log_service.get(session, body.current_log_id)
        if entry is not None:
            red_flag, _ = check_red_flags(entry.notes or "", entry.prodrome_symptoms)
            state_update["red_flag_active"] = red_flag
    if body.message:
        state_update["messages"] = [HumanMessage(content=body.message)]

    try:
        checkpoint = await graph.aget_state(config)
        is_new_thread = checkpoint.values == {}
    except Exception:
        is_new_thread = True

    if is_new_thread:
        full_state = {**default_state(), **state_update}
    else:
        full_state = state_update

    result = await graph.ainvoke(full_state, config=config)

    ai_messages = [msg.content for msg in result.get("messages", []) if isinstance(msg, AIMessage)]

    return AnalyzeResponse(
        messages=ai_messages,
        moh_alert=result.get("moh_alert_active", False),
        red_flag=result.get("red_flag_active", False),
    )
