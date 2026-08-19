from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from app.api.schemas import RefreshRequest, TokenResponse, UserLogin, UserRegister
from app.config import settings
from app.core.security import generate_refresh_token, hash_token
from app.database import get_session_dep
from app.models.refresh_token import RefreshToken
from app.models.user import User

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    return token.decode("utf-8") if isinstance(token, bytes) else token


def _issue_token_pair(user: User, session: Session) -> TokenResponse:
    """Create a new access + refresh token pair, persist the refresh token, and return both."""
    assert user.id is not None
    raw_refresh, refresh_hash = generate_refresh_token()
    record = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(record)
    # Caller must commit after this returns.
    return TokenResponse(
        token=_create_access_token(user.id),
        refresh_token=raw_refresh,
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
    response = _issue_token_pair(user, session)
    session.commit()
    return response


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: UserLogin, session: Session = Depends(get_session_dep)):
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not User.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    response = _issue_token_pair(user, session)
    session.commit()
    return response


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
def refresh(request: Request, payload: RefreshRequest, session: Session = Depends(get_session_dep)):
    record = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token))
    ).first()
    if not record or record.revoked_at or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    # Rotate: revoke the old token so it cannot be reused.
    record.revoked_at = datetime.utcnow()
    session.add(record)
    user = session.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    response = _issue_token_pair(user, session)
    session.commit()
    return response


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, session: Session = Depends(get_session_dep)):
    record = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token))
    ).first()
    if record and not record.revoked_at:
        record.revoked_at = datetime.utcnow()
        session.add(record)
        session.commit()
    return Response(status_code=204)
