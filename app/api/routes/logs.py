from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.database import get_session_dep
from app.models.user import User
from app.services import log_service
from app.services import email as email_svc
from app.rules.rules_engine import rolling_load
from app.api.schemas import LogEntryCreate, LogEntryRead, LogCreateResponse, ToxicLoadResponse

router = APIRouter()


@router.post("/", response_model=LogCreateResponse, status_code=201)
def create_log(
    payload:          LogEntryCreate,
    background_tasks: BackgroundTasks,
    current_user:     User    = Depends(get_current_user),
    session:          Session = Depends(get_session_dep),
):
    data = payload.model_dump()
    data["user_id"] = current_user.id
    result = log_service.create(session, data)

    if result.red_flag:
        background_tasks.add_task(email_svc.send_red_flag_alert, result.red_flag_symptoms)
    if result.moh_alert:
        background_tasks.add_task(email_svc.send_moh_alert, result.triptan_days, result.nsaid_days)

    return LogCreateResponse(
        log=LogEntryRead.model_validate(result.entry),
        red_flag=result.red_flag,
        red_flag_symptoms=result.red_flag_symptoms,
        moh_alert=result.moh_alert,
        triptan_days=result.triptan_days,
        nsaid_days=result.nsaid_days,
    )


@router.get("/toxic-load", response_model=ToxicLoadResponse)
def get_toxic_load(
    as_of: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    load = rolling_load(session, as_of, user_id=current_user.id)
    return ToxicLoadResponse(
        today_score=load.today_score,
        carryover_score=load.carryover_score,
        rolling_score=load.rolling_score,
        threshold=load.threshold,
        fill_pct=load.fill_pct,
        risk_level=load.risk_level,
        breakdown=load.breakdown,
    )


@router.get("/{log_id}", response_model=LogEntryRead)
def get_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    entry = log_service.get(session, log_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Log entry not found")
    return LogEntryRead.model_validate(entry)


@router.get("/", response_model=list[LogEntryRead])
def list_logs(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    entries = log_service.list_recent(session, limit=limit, user_id=current_user.id)
    return [LogEntryRead.model_validate(e) for e in entries]
