"""
ASGI middleware that authenticates MCP HTTP requests via Bearer JWT.

Wraps the FastMCP ASGI app mounted at /mcp.  On valid token it sets
_current_user_id so all MCP tools resolve the right user.  On missing
or invalid token it returns 401 without touching the inner app.
"""

import json

import jwt
from starlette.requests import Request

from app.core.security import decode_user_id
from app.mcp_server.server import _current_user_id


class MCPAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        auth = Request(scope).headers.get("authorization", "")

        if not auth.startswith("Bearer "):
            await _send_401(scope, send, "Not authenticated")
            return

        token = auth[len("Bearer ") :]
        try:
            user_id = decode_user_id(token)
        except jwt.ExpiredSignatureError:
            await _send_401(scope, send, "Token expired")
            return
        except jwt.InvalidTokenError:
            await _send_401(scope, send, "Invalid token")
            return

        ctx_token = _current_user_id.set(user_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_user_id.reset(ctx_token)


async def _send_401(scope, send, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
