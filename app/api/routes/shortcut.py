"""
Apple Shortcuts integration — lightweight log endpoint secured by a static API key.

Shortcuts setup (iOS):
  1. Create a new Shortcut → Add Action → "Get Contents of URL"
  2. URL:     https://<your-domain>/shortcut/log
  3. Method:  POST
  4. Headers: X-Shortcuts-Key = <your SHORTCUTS_API_KEY>
  5. Body (JSON):
       {
         "username":   "your_username",
         "migraine":   true,
         "pain_level": 7,
         "medication": "sumatriptan",
         "notes":      "Shortcut: woke up with it"
       }
  6. Add a "Speak Text" action using the "spoken" field from the response.

Optional voice flow:
  - Add "Ask for Input" actions before the URL step to capture pain_level and
    medication via Siri dictation, then pass them into the JSON body.
"""

from datetime import date as date_type

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session_dep
from app.models.user import User
from app.services import email as email_svc
from app.services.log_service import create

router = APIRouter()


# ── Auth ──────────────────────────────────────────────────────────────────────

def _verify_key(x_shortcuts_key: str = Header(...)):
    if not settings.shortcuts_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shortcuts integration is not configured on this server.",
        )
    if x_shortcuts_key != settings.shortcuts_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Shortcuts key.")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ShortcutLogRequest(BaseModel):
    username:   str
    migraine:   bool
    pain_level: int   = 5
    medication: str   = ""
    notes:      str   = ""


class ShortcutLogResponse(BaseModel):
    spoken:      str
    red_flag:    bool
    moh_alert:   bool
    moh_warning: str | None = None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/log", response_model=ShortcutLogResponse)
def shortcut_log(
    body:             ShortcutLogRequest,
    background_tasks: BackgroundTasks,
    session:          Session = Depends(get_session_dep),
    _:                None    = Depends(_verify_key),
):
    user = session.exec(select(User).where(User.username == body.username)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Username not found.")

    payload: dict = {
        "user_id":          user.id,
        "entry_date":       date_type.today(),
        "migraine_occurred": body.migraine,
    }
    if body.migraine:
        payload["pain_level"] = body.pain_level
    if body.medication.strip():
        payload["medications"] = [body.medication.strip()]
    if body.notes.strip():
        payload["notes"] = body.notes.strip()

    result = create(session, payload)

    # ── Email alerts (non-blocking) ───────────────────────────────────────────
    if result.red_flag:
        background_tasks.add_task(
            email_svc.send_red_flag_alert, result.red_flag_symptoms
        )
    if result.moh_alert:
        background_tasks.add_task(
            email_svc.send_moh_alert, result.triptan_days, result.nsaid_days
        )

    # ── Spoken response ───────────────────────────────────────────────────────
    if result.red_flag:
        spoken = (
            "Warning: red flag symptoms detected. "
            "Please seek medical attention if symptoms are severe."
        )
    elif body.migraine:
        med_part = f" {body.medication} recorded." if body.medication.strip() else ""
        spoken   = f"Migraine logged. Pain {body.pain_level} out of 10.{med_part}"
        if result.moh_alert:
            spoken += " Medication overuse alert — check the app."
    else:
        spoken = "Good news logged. Migraine-free day recorded."

    moh_warning = None
    if result.moh_alert:
        moh_warning = (
            f"MOH threshold reached: {result.triptan_days} triptan days, "
            f"{result.nsaid_days} NSAID days in the last 30 days."
        )

    return ShortcutLogResponse(
        spoken=spoken,
        red_flag=result.red_flag,
        moh_alert=result.moh_alert,
        moh_warning=moh_warning,
    )
