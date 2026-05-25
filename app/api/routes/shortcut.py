"""
Apple Shortcuts integration — two-step flow (Option A).

─────────────────────────────────────────────────────────────
STEP 1 — Fetch baseline context  (GET /shortcut/context)
─────────────────────────────────────────────────────────────
  URL:    GET https://<your-domain>/shortcut/context?username=<your_username>
  Header: X-Shortcuts-Key = <SHORTCUTS_API_KEY>

  Returns:
    {
      "typical_sleep_hours":  7.5,
      "typical_stress_level": 4,
      "typical_hydration_oz": 64.0,
      "typical_caffeine":     "moderate"
    }

  In Shortcuts:
    → Get Dictionary Value "typical_sleep_hours"  → save as TypicalSleep
    → Get Dictionary Value "typical_stress_level" → save as TypicalStress
    → Get Dictionary Value "typical_hydration_oz" → save as TypicalHydration

─────────────────────────────────────────────────────────────
STEP 2 — Log entry  (POST /shortcut/log)
─────────────────────────────────────────────────────────────
  Header: X-Shortcuts-Key = <SHORTCUTS_API_KEY>

  Migraine day flow:
    Ask "Pain level 1–10?"              → pain_level
    Ask "Medication taken? (or blank)"  → medication
    Ask "Any notes?"                    → notes
    POST { username, migraine:true, pain_level, medication, notes }

  Migraine-free day flow (uses baseline from Step 1):
    Ask "Sleep normal? Your usual is [TypicalSleep] hrs. (yes/no)"
      → If "no":  Ask "How many hours?" → sleep_hours (number)
      → If "yes": sleep_hours = TypicalSleep

    Ask "Sleep quality different? (yes/no)"
      → If "no":  sleep_quality = null (server skips it)
      → If "yes": Ask "Quality 1–10?"  → sleep_quality (number)

    Ask "Stress different? Your usual is [TypicalStress]/10. (yes/no)"
      → If "no":  stress_level = TypicalStress
      → If "yes": Ask "Stress level 1–10?" → stress_level (number)

    Ask "Hydration low today? (yes/no)"
      → If "yes": hydration_oz = TypicalHydration × 0.5
      → If "no":  hydration_oz = TypicalHydration

    POST { username, migraine:false, sleep_hours, sleep_quality,
           stress_level, hydration_oz }

  Response:
    { "spoken": "...", "red_flag": false, "moh_alert": false }

  Add a "Speak Text" action using the "spoken" field — Siri reads it aloud.
"""

from datetime import date as date_type, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session_dep
from app.models.user import User
from app.models.user_profile import UserProfile
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sleep_hours(bedtime: str, wake_time: str) -> float | None:
    try:
        bt = datetime.strptime(bedtime, "%H:%M")
        wt = datetime.strptime(wake_time, "%H:%M")
        delta = wt - bt
        if delta.total_seconds() < 0:
            delta += timedelta(hours=24)
        return round(delta.total_seconds() / 3600, 1)
    except Exception:
        return None


def _lookup_user(session: Session, username: str) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Username not found.")
    return user


def _lookup_profile(session: Session, user_id: int) -> UserProfile | None:
    return session.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ShortcutContextResponse(BaseModel):
    typical_sleep_hours:  float | None
    typical_stress_level: int   | None
    typical_hydration_oz: float | None
    typical_caffeine:     str   | None


class ShortcutLogRequest(BaseModel):
    username:     str
    migraine:     bool
    # Migraine-day fields
    pain_level:   int   = 5
    medication:   str   = ""
    notes:        str   = ""
    # Migraine-free day fields (captured via conditional questions in Shortcuts)
    sleep_hours:  float | None = None
    sleep_quality: int  | None = None
    stress_level: int   | None = None
    hydration_oz: float | None = None


class ShortcutLogResponse(BaseModel):
    spoken:      str
    red_flag:    bool
    moh_alert:   bool
    moh_warning: str | None = None


# ── GET /shortcut/context ─────────────────────────────────────────────────────

@router.get("/context", response_model=ShortcutContextResponse)
def shortcut_context(
    username: str,
    session:  Session = Depends(get_session_dep),
    _:        None    = Depends(_verify_key),
):
    """Return the user's profile baseline so Shortcuts can ask relative questions."""
    user    = _lookup_user(session, username)
    profile = _lookup_profile(session, user.id)

    if not profile:
        return ShortcutContextResponse(
            typical_sleep_hours=None,
            typical_stress_level=None,
            typical_hydration_oz=None,
            typical_caffeine=None,
        )

    sleep = _sleep_hours(profile.typical_bedtime, profile.typical_wake_time) \
        if profile.typical_bedtime and profile.typical_wake_time else None

    return ShortcutContextResponse(
        typical_sleep_hours=sleep,
        typical_stress_level=profile.typical_stress_level,
        typical_hydration_oz=profile.typical_hydration_oz,
        typical_caffeine=profile.typical_caffeine_level,
    )


# ── POST /shortcut/log ────────────────────────────────────────────────────────

@router.post("/log", response_model=ShortcutLogResponse)
def shortcut_log(
    body:             ShortcutLogRequest,
    background_tasks: BackgroundTasks,
    session:          Session = Depends(get_session_dep),
    _:                None    = Depends(_verify_key),
):
    user = _lookup_user(session, body.username)

    payload: dict = {
        "user_id":           user.id,
        "entry_date":        date_type.today(),
        "migraine_occurred": body.migraine,
    }

    if body.migraine:
        payload["pain_level"] = body.pain_level
        if body.medication.strip():
            payload["medications"] = [body.medication.strip()]
        if body.notes.strip():
            payload["notes"] = body.notes.strip()
    else:
        # Non-migraine: include whatever baseline deviation was captured
        if body.sleep_hours  is not None: payload["sleep_hours"]   = body.sleep_hours
        if body.sleep_quality is not None: payload["sleep_quality"] = body.sleep_quality
        if body.stress_level is not None: payload["stress_level"]  = body.stress_level
        if body.hydration_oz is not None: payload["hydration_oz"]  = body.hydration_oz

    result = create(session, payload)

    # ── Email alerts (non-blocking) ───────────────────────────────────────────
    if result.red_flag:
        background_tasks.add_task(email_svc.send_red_flag_alert, result.red_flag_symptoms)
    if result.moh_alert:
        background_tasks.add_task(email_svc.send_moh_alert, result.triptan_days, result.nsaid_days)

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
        parts = ["Migraine-free day logged."]
        if body.sleep_hours  is not None: parts.append(f"Sleep {body.sleep_hours} hours recorded.")
        if body.stress_level is not None: parts.append(f"Stress {body.stress_level} out of 10 recorded.")
        spoken = " ".join(parts)

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
