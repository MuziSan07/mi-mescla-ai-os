"""
AI Operating System - Auth Dependencies
Provides FastAPI Depends() guards for JWT authentication.

Usage in any route:
    from ai_os.core.security.dependencies import require_auth, optional_auth

    @router.get("/protected")
    async def protected(user: TokenData = Depends(require_auth)):
        return {"user": user.username}

    @router.get("/public-or-auth")
    async def maybe_auth(user: Optional[TokenData] = Depends(optional_auth)):
        return {"user": user.username if user else "anonymous"}
"""

import os
import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ai_os.models.schemas import TokenData
from ai_os.config.settings import settings

logger = logging.getLogger(__name__)

# Auth is disabled by default for dev — set AUTH_ENABLED=true in .env to enforce
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"

_bearer = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.
    Falls back to simple token lookup if PyJWT fails.
    """
    try:
        import jwt
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")
        if not username:
            return None
        return TokenData(username=username)
    except Exception:
        # Try legacy simple token via SecurityManager
        try:
            from ai_os.core.security.auth import get_security_manager
            import asyncio
            sm = get_security_manager()
            loop = asyncio.get_event_loop()
            token_data = loop.run_until_complete(sm.verify_token(token))
            return token_data
        except Exception as e:
            logger.debug(f"Token verification failed: {e}")
            return None


def create_access_token(username: str) -> str:
    """Create a signed JWT access token"""
    try:
        import jwt
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": username, "exp": expire}
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    except ImportError:
        import secrets
        return secrets.token_urlsafe(32)


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)
) -> TokenData:
    """
    FastAPI dependency — requires valid JWT.
    Returns TokenData with username.
    Raises 401 if token missing or invalid.

    Skipped entirely if AUTH_ENABLED=false (default for dev).
    """
    if not AUTH_ENABLED:
        return TokenData(username="dev-user")

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = _decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)
) -> Optional[TokenData]:
    """
    FastAPI dependency — auth optional.
    Returns TokenData if valid token provided, None otherwise.
    """
    if not AUTH_ENABLED:
        return None
    if not credentials:
        return None
    return _decode_token(credentials.credentials)
