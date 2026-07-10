from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from app.api.schemas import TokenResponse, UserLogin, UserRegister
from app.config import settings
from app.database import get_session_dep
from app.models.user import User

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(days=settings.jwt_expire_days),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    # PyJWT < 2.0 returned bytes; >= 2.0 returns str. Handle both.
    return token.decode("utf-8") if isinstance(token, bytes) else token


def _token_response(user: User) -> TokenResponse:
    assert user.id is not None
    return TokenResponse(
        token=_create_token(user.id),
        id=user.id,
        username=user.username,
        created_at=user.created_at,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: UserRegister, session: Session = Depends(get_session_dep)):
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        username=payload.username,
        password_hash=User.hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: UserLogin, session: Session = Depends(get_session_dep)):
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not User.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return _token_response(user)
