from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.api.schemas import UserProfileCreate, UserProfileRead, UserProfileUpdate
from app.database import get_session_dep
from app.models.log_entry import LogEntry
from app.models.user import User
from app.models.user_profile import UserProfile

_BASE_FOODS = [
    "aged_cheese",
    "alcohol",
    "artificial_sweeteners",
    "avocado",
    "bananas",
    "beans_legumes",
    "beer",
    "caffeine",
    "chocolate",
    "citrus",
    "fermented_foods",
    "garlic",
    "gluten",
    "MSG",
    "nuts",
    "onions",
    "pickled_foods",
    "pizza",
    "processed_meat",
    "red_wine",
    "smoked_fish",
    "tyramine_rich_foods",
    "yeast_extract",
]

router = APIRouter()


@router.get("/me", response_model=UserProfileRead)
def get_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfileRead.model_validate(profile)


@router.post("/me", response_model=UserProfileRead, status_code=201)
def create_profile(
    payload: UserProfileCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    existing = session.exec(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists — use PATCH to update")
    profile = UserProfile(user_id=current_user.id, **payload.model_dump())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return UserProfileRead.model_validate(profile)


@router.get("/me/reference-foods")
def get_reference_foods(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """Return the merged food list: base curated list + user's profile triggers + every food the user has ever logged."""
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    ).first()
    profile_foods = (profile.known_food_triggers or []) if profile else []

    logs = session.exec(select(LogEntry).where(LogEntry.user_id == current_user.id)).all()
    logged_foods: set[str] = set()
    for log in logs:
        if log.foods:
            logged_foods.update(log.foods)

    combined = sorted(set(_BASE_FOODS + profile_foods) | logged_foods, key=str.casefold)
    return {"foods": combined}


@router.patch("/me", response_model=UserProfileRead)
def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return UserProfileRead.model_validate(profile)
