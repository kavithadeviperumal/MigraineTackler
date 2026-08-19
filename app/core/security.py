import hashlib
import secrets

import jwt

from app.config import settings


def decode_user_id(token: str) -> int:
    """
    Decode a HS256 JWT and return the user_id from the 'sub' claim.
    Raises jwt.InvalidTokenError (or subclass) on failure — callers decide
    how to surface the error (HTTPException, ASGI 401, etc.).
    """
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    return int(payload["sub"])


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). Store only the hash; send the raw token to the client."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
