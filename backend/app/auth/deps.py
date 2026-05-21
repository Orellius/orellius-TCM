"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, Request

from app.auth.jwt import decode_token
from app.config import settings
from app.errors import AuthError, ForbiddenError


async def get_current_user(request: Request) -> dict | None:
    """Extract current user from JWT token. Returns None in local/dev mode."""
    # Dev mode: no auth configured
    if not settings.api_secret_token:
        return None

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]

    # Try JWT first
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "org_id": payload.get("org_id"),
            "role": payload.get("role", "viewer"),
            "is_superadmin": payload.get("is_superadmin", False),
        }

    # Fallback: shared secret token (backward compat for local mode)
    if token == settings.api_secret_token:
        return {"user_id": "local", "email": "local", "org_id": None, "role": "admin", "is_superadmin": True}

    return None


def require_role(*roles: str):
    """FastAPI dependency that requires the user to have one of the specified roles."""

    async def _check(user: dict | None = Depends(get_current_user)):
        # Dev mode: no auth → allow everything
        if not settings.api_secret_token:
            return user

        if user is None:
            raise AuthError()

        if user.get("is_superadmin"):
            return user

        if user.get("role") not in roles:
            raise ForbiddenError(f"Role {user.get('role')} insufficient. Required: {', '.join(roles)}")

        return user

    return _check
