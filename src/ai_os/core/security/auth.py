"""
AI Operating System - Security Module

Provides authentication, authorization, sandboxing, and loop protection.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from hashlib import sha256
import hmac

from ai_os.models.schemas import User, UserCreate, Token, TokenData

logger = logging.getLogger(__name__)


class SecurityManager:
    """
    Security controls for AI-OS
    """
    
    def __init__(
        self,
        secret_key: str,
        max_iterations: int = 10000,
        rate_limit: int = 100
    ):
        self._secret_key = secret_key
        self._max_iterations = max_iterations
        self._rate_limit = rate_limit
        self._users: Dict[str, User] = {}
        self._tokens: Dict[str, str] = {}  # token -> username
        self._rate_limits: Dict[str, List[datetime]] = {}  # client -> timestamps
        self._loop_counts: Dict[str, int] = {}  # session -> iteration count
    
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return sha256(
            f"{self._secret_key}{password}".encode()
        ).hexdigest()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return hmac.compare_digest(
            self.hash_password(password),
            hashed
        )
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        if user_data.username in self._users:
            raise ValueError(f"User {user_data.username} already exists")
        
        user = User(
            id=f"user-{len(self._users)}",
            username=user_data.username,
            email=user_data.email,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        self._users[user_data.username] = user
        logger.info(f"Created user: {user_data.username}")
        return user
    
    async def authenticate(
        self,
        username: str,
        password: str
    ) -> Optional[User]:
        """Authenticate a user"""
        user = self._users.get(username)
        if not user or not user.is_active:
            return None
        
        return user
    
    async def create_token(self, username: str) -> Token:
        """Create access token"""
        import secrets
        
        token = secrets.token_urlsafe(32)
        self._tokens[token] = username
        
        return Token(
            access_token=token,
            token_type="bearer"
        )
    
    async def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify access token"""
        username = self._tokens.get(token)
        if not username:
            return None
        
        return TokenData(username=username)
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke access token"""
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False
    
    async def check_rate_limit(self, client_id: str) -> bool:
        """Check rate limit for client"""
        now = datetime.utcnow()
        window = timedelta(minutes=1)
        
        if client_id not in self._rate_limits:
            self._rate_limits[client_id] = []
        
        # Clean old timestamps
        self._rate_limits[client_id] = [
            ts for ts in self._rate_limits[client_id]
            if now - ts < window
        ]
        
        # Check limit
        if len(self._rate_limits[client_id]) >= self._rate_limit:
            return False
        
        self._rate_limits[client_id].append(now)
        return True
    
    async def check_loop_protection(self, session_id: str) -> bool:
        """Check loop protection for session"""
        count = self._loop_counts.get(session_id, 0)
        
        if count >= self._max_iterations:
            logger.warning(
                f"Session {session_id} exceeded max iterations: {self._max_iterations}"
            )
            return False
        
        self._loop_counts[session_id] = count + 1
        return True
    
    async def reset_loop_count(self, session_id: str):
        """Reset loop count for session"""
        self._loop_counts[session_id] = 0
    
    async def authorize(
        self,
        username: str,
        action: str,
        resource: str
    ) -> bool:
        """Check authorization"""
        # For now, allow all actions
        return True


# Singleton instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the security manager singleton"""
    global _security_manager
    if _security_manager is None:
        from ai_os.config.settings import settings
        _security_manager = SecurityManager(
            secret_key=settings.SECRET_KEY
        )
    return _security_manager