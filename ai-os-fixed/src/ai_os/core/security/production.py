"""
Production Security Module — JWT, Rate Limiting, Input Sanitization, Security Headers
"""

import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import logging

from fastapi import Request, HTTPException, Depends, status
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ── JWT ──────────────────────────────────────────────────────────────────────

class JWTAuth:
    def __init__(self, secret_key: str = None, algorithm: str = "HS256",
                 access_token_expire: int = 3600, refresh_token_expire: int = 604800):
        self.secret_key = secret_key or os.getenv("JWT_SECRET")
        if not self.secret_key:
            raise ValueError("JWT_SECRET environment variable must be set.")
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire
        self.refresh_token_expire = refresh_token_expire

    def create_access_token(self, subject: str, roles: List[str] = None,
                            permissions: List[str] = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(seconds=self.access_token_expire)
        payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(expire.timestamp()),
                   "type": "access", "roles": roles or [], "permissions": permissions or []}
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "access":
                raise JWTError("Invalid token type")
            exp = payload.get("exp", 0)
            if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                raise ExpiredSignatureError("Token expired")
            return payload
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


_jwt_auth: Optional[JWTAuth] = None

def get_jwt_auth() -> JWTAuth:
    global _jwt_auth
    if _jwt_auth is None:
        _jwt_auth = JWTAuth(
            secret_key=os.getenv("JWT_SECRET"),
            algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire=int(os.getenv("JWT_ACCESS_EXPIRE", 3600)),
            refresh_token_expire=int(os.getenv("JWT_REFRESH_EXPIRE", 604800)),
        )
    return _jwt_auth


security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    payload = get_jwt_auth().verify_token(credentials.credentials)
    return {"user_id": payload.get("sub"), "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", [])}


# ── Password Hashing (bcrypt) ─────────────────────────────────────────────────

import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Rate Limiting (Redis-backed, atomic Lua — no TOCTOU) ──────────────────────

import redis.asyncio as redis

_RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, tostring(now) .. math.random())
    redis.call('EXPIRE', key, window)
    return 1
end
return 0
"""

class RateLimiter:
    """Redis-backed atomic sliding-window rate limiter. Fails CLOSED on error."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        self._script_sha: Optional[str] = None

    async def connect(self) -> None:
        if self._connected:
            return
        try:
            self._redis = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            await self._redis.ping()
            self._script_sha = await self._redis.script_load(_RATE_LIMIT_LUA)
            self._connected = True
        except Exception as e:
            logger.error("Rate limiter Redis connection failed: %s", e)
            self._connected = False

    async def check_rate_limit(self, identifier: str, limit: int = 100, window: int = 60) -> Dict[str, Any]:
        if not self._connected:
            await self.connect()
        if not self._connected:
            logger.error("Rate limiter unavailable — denying request for %s", identifier)
            return {"allowed": False, "remaining": 0, "limit": limit, "reset": 0}

        key = f"ratelimit:{identifier}"
        now = datetime.now(timezone.utc).timestamp()
        try:
            allowed = await self._redis.evalsha(self._script_sha, 1, key, str(limit), str(window), str(now))
            count_after = await self._redis.zcard(key)
            remaining = max(0, limit - count_after)
            return {"allowed": bool(allowed), "remaining": remaining if allowed else 0,
                    "limit": limit, "reset": int(now + window)}
        except Exception as e:
            logger.error("Rate limit Lua eval failed: %s — denying request", e)
            return {"allowed": False, "remaining": 0, "limit": limit, "reset": 0}


_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"))
    return _rate_limiter


# ── Input Sanitization ────────────────────────────────────────────────────────

class InputSanitizer:
    @staticmethod
    def sanitize_html(text: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"on\w+\s*=\s*[\"']?[^\"']+[\"']?", "", text, flags=re.IGNORECASE)
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def sanitize_shell(text: str) -> str:
        for char in [";", "|", "&", "`", "$", "(", ")", "<", ">"]:
            text = text.replace(char, "_")
        return text

    @staticmethod
    def sanitize_path(path: str, base_dir: str = "/app") -> str:
        import os
        normalised = os.path.normpath("/" + path.replace("..", ""))
        safe = os.path.join(base_dir, normalised.lstrip("/"))
        real_base = os.path.realpath(base_dir)
        real_path = os.path.realpath(safe)
        if not real_path.startswith(real_base + os.sep) and real_path != real_base:
            raise ValueError(f"Path traversal attempt detected: {path!r}")
        return real_path

    @staticmethod
    def validate_filename(filename: str) -> bool:
        if not filename or "/" in filename or "\\" in filename:
            return False
        return bool(re.match(r"^[\w\-\.]+$", filename))

    @staticmethod
    def validate_url(url: str, allowed_schemes: tuple = ("http", "https")) -> bool:
        import urllib.parse, ipaddress
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in allowed_schemes:
                return False
            hostname = parsed.hostname or ""
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
            except ValueError:
                if hostname.lower() in {"localhost", "metadata.google.internal"}:
                    return False
            return True
        except Exception:
            return False


# ── Security Headers Middleware ───────────────────────────────────────────────

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self';"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store",
}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


# ── Secret Manager ────────────────────────────────────────────────────────────

class SecretManager:
    def __init__(self):
        self._secrets: Dict[str, str] = {}

    def load_from_env(self, prefix: str = "AI_OS_") -> None:
        for key, value in os.environ.items():
            if key.startswith(prefix):
                self._secrets[key[len(prefix):].lower()] = value

    def get(self, key: str, default: str = None) -> Optional[str]:
        if not self._secrets:
            self.load_from_env()
        return self._secrets.get(key.lower(), default)


_secret_manager: Optional[SecretManager] = None

def get_secret_manager() -> SecretManager:
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager
