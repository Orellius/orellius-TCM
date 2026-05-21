"""Bearer token authentication middleware.

When `settings.api_secret_token` is empty, auth is completely bypassed (dev mode).
When set, all requests except public paths must include `Authorization: Bearer <token>`.
WebSocket auth uses `?token=<token>` query parameter.
"""

import logging

from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

# Paths that never require auth
PUBLIC_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc"}
PUBLIC_PREFIXES = ("/media/",)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Dev mode: no token configured → skip auth entirely
        if not settings.api_secret_token:
            return await call_next(request)

        path = request.url.path

        # Public endpoints
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # WebSocket upgrade handled separately in the WS endpoint
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "Authentication required", "code": "auth_error"},
            )

        token = auth_header[7:]
        if token != settings.api_secret_token:
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "Invalid token", "code": "auth_error"},
            )

        return await call_next(request)


def verify_ws_token(websocket: WebSocket) -> bool:
    """Verify WebSocket token from query parameter. Returns True if valid or auth disabled."""
    if not settings.api_secret_token:
        return True
    token = websocket.query_params.get("token", "")
    return token == settings.api_secret_token
