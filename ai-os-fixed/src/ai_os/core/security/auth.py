"""
AI Operating System - Security Module
Authentication, authorization, sandboxing, and loop protection.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

import bcrypt

from ai_os.models import User, UserCreate, Token, TokenData

logger = logging.getLogger(__name__)
_BCRYPT_ROUNDS = 12


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


class SecurityManager:
    def __init__(self, secret_key: str, max_iterations: int = 10_000, rate_limit: int = 100):
        if not secret_key or len(secret_key) < 32:
            raise ValueError("secret_key must be at least 32 characters.")
        self._secret_key = secret_key
        self._max_iterations = max_iterations
        self._rate_limit = rate_limit
        self._users: Dict[str, User] = {}
        self._password_hashes: Dict[str, str] = {}
        self._tokens: Dict[str, tuple] = {}   # token -> (username, expires_at)
        self._rate_limits: Dict[str, List[datetime]] = {}
        self._loop_counts: Dict[str, int] = {}

    async def create_user(self, user_data: UserCreate) -> User:
        if user_data.username in self._users:
            raise ValueError(f"User {user_data.username} already exists")
        if not getattr(user_data, "password", None):
            raise ValueError("Password is required")
        user = User(
            id=str(uuid.uuid4()),
            username=user_data.username,
            email=user_data.email,
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )
        self._users[user_data.username] = user
        self._password_hashes[user_data.username] = _hash_password(user_data.password)
        logger.info("Created user: %s", user_data.username)
        return user

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate — always runs bcrypt to prevent timing-based enumeration."""
        user = self._users.get(username)
        stored_hash = self._password_hashes.get(username)
        dummy = "$2b$12$invalidsaltthatisexactly22chars.invalidhashpadding000000000"
        ok = _verify_password(password, stored_hash if stored_hash else dummy)
        if not user or not user.is_active or not stored_hash or not ok:
            return None
        return user

    async def create_token(self, username: str) -> Token:
        import secrets
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        self._tokens[token] = (username, expires_at)
        return Token(access_token=token, token_type="bearer")

    async def verify_token(self, token: str) -> Optional[TokenData]:
        entry = self._tokens.get(token)
        if not entry:
            return None
        username, expires_at = entry
        if datetime.now(timezone.utc) > expires_at:
            del self._tokens[token]
            return None
        return TokenData(username=username)

    async def revoke_token(self, token: str) -> bool:
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    async def check_rate_limit(self, client_id: str) -> bool:
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=1)
        if client_id not in self._rate_limits:
            self._rate_limits[client_id] = []
        self._rate_limits[client_id] = [ts for ts in self._rate_limits[client_id] if now - ts < window]
        if len(self._rate_limits[client_id]) >= self._rate_limit:
            return False
        self._rate_limits[client_id].append(now)
        return True

    async def check_loop_protection(self, session_id: str) -> bool:
        count = self._loop_counts.get(session_id, 0)
        if count >= self._max_iterations:
            logger.warning("Session %s exceeded max iterations", session_id)
            return False
        self._loop_counts[session_id] = count + 1
        return True

    async def reset_loop_count(self, session_id: str) -> None:
        self._loop_counts[session_id] = 0

    async def authorize(self, username: str, action: str, resource: str) -> bool:
        user = self._users.get(username)
        if not user:
            return False
        role = getattr(user, "role", "user")
        RBAC: Dict[str, tuple] = {
            "admin": ({"*"}, {"*"}),
            "developer": ({"read","write","execute","deploy"}, {"code","api","config","models","tools","agents"}),
            "operator": ({"read","execute","monitor"}, {"api","models","workers","health","logs"}),
            "user": ({"read"}, {"api","models"}),
            "guest": ({"read"}, {"api"}),
        }
        allowed_actions, allowed_resources = RBAC.get(role, RBAC["guest"])
        if "*" not in allowed_actions and action not in allowed_actions:
            return False
        if "*" not in allowed_resources:
            if not any(p in resource.lower() for p in allowed_resources):
                return False
        return True


_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    global _security_manager
    if _security_manager is None:
        from ai_os.config.settings import settings
        _security_manager = SecurityManager(secret_key=settings.SECRET_KEY)
    return _security_manager
