import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from sqlalchemy import text
from sqlmodel import Session

from app.config import settings
from app.core.security import decode_user_id
from app.database import engine, get_session_dep
from app.models.user import User

_bearer = HTTPBearer()


def _user_id_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], settings.jwt_secret_key, algorithms=["HS256"])
            return f"user:{payload['sub']!s}"
        except jwt.InvalidTokenError:
            pass
    return str(request.client.host) if request.client else "unknown"


user_limiter = Limiter(key_func=_user_id_key)


def _decode_token(token: str) -> int:
    try:
        return decode_user_id(token)
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from err


def _set_rls_user(session: Session, user_id: int) -> None:
    """Set the Postgres session variable that RLS policies read.

    SET LOCAL scopes the variable to the current transaction — it resets
    automatically on commit/rollback, so it never leaks across pooled connections.
    Skipped on non-Postgres engines (e.g. SQLite in local dev without Docker).
    """
    if engine.dialect.name == "postgresql":
        session.execute(text(f"SET LOCAL app.current_user_id = '{int(user_id)}'"))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session_dep),
) -> User:
    user_id = _decode_token(credentials.credentials)
    _set_rls_user(session, user_id)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
