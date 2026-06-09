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
