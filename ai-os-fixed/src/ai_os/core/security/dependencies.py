"""
AI Operating System - Auth Dependencies
FastAPI Depends() guards for JWT / opaque-token authentication.

Usage:
    from ai_os.core.security.dependencies import require_auth, require_role

    @router.get("/protected")
    async def protected(user: TokenData = Depends(require_auth)):
        return {"user": user.username}
"""

import os
import logging
from typing import Optional, Callable
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ai_os.models import TokenData
from ai_os.config.settings import settings

logger = logging.getLogger(__name__)

# Auth is ENABLED by default — only disable with AUTH_ENABLED=false in local dev.
AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "true").lower() == "true"

_bearer = HTTPBearer(auto_error=False)


async def _decode_token(token: str) -> Optional[TokenData]:
    """Try JWT first, fall back to opaque SecurityManager token."""
    try:
        import jwt
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                             options={"require": ["sub", "exp"]})
        username = payload.get("sub")
        if username:
            return TokenData(username=username)
    except Exception:
        pass

    try:
        from ai_os.core.security.auth import get_security_manager
        sm = get_security_manager()
        return await sm.verify_token(token)
    except Exception as exc:
        logger.debug("Token verification failed: %s", exc)
        return None


def create_access_token(username: str, expires_minutes: int = None) -> str:
    import jwt
    minutes = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": username, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> TokenData:
    """Require valid JWT or opaque token. Raises 401 if missing/invalid."""
    if not AUTH_ENABLED:
        logger.warning("AUTH_ENABLED=false — treating all requests as dev-user. Never use in production.")
        return TokenData(username="dev-user")

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = await _decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[TokenData]:
    """Auth optional — returns TokenData or None."""
    if not AUTH_ENABLED or not credentials:
        return None
    return await _decode_token(credentials.credentials)


def require_role(*roles: str) -> Callable:
    """Factory for role-gated endpoints: Depends(require_role('admin'))"""
    async def _dep(user: TokenData = Depends(require_auth)) -> TokenData:
        user_role = getattr(user, "role", "user")
        if user_role not in roles and "*" not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not permitted. Required: {roles}",
            )
        return user
    return _dep
