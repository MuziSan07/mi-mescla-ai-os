"""AI Operating System - Configuration Module"""

import os
import sys
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # App
    APP_NAME: str = "AI-OS"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # API
    API_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./aios.db")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS", "guest")

    # Qdrant
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Worker Settings
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "10"))
    WORKER_TIMEOUT: int = int(os.getenv("WORKER_TIMEOUT", "300"))
    HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

    # Model Settings
    DEFAULT_CODING_MODEL: str = "codellama:13b"
    DEFAULT_REASONING_MODEL: str = "mistral:7b"
    DEFAULT_VISION_MODEL: str = "llava:7b"

    # Audit Settings
    AUDIT_INTERVAL: int = int(os.getenv("AUDIT_INTERVAL", "300"))
    AUTO_CORRECT: bool = os.getenv("AUTO_CORRECT", "true").lower() == "true"

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def is_secure(self) -> bool:
        return bool(self.SECRET_KEY) and len(self.SECRET_KEY) >= 32

    @property
    def allowed_origins(self) -> List[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "")
        if not raw or raw.strip() == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def validate_production_secrets(self) -> None:
        """Refuse to start with placeholder or missing SECRET_KEY."""
        insecure = {
            "", "change-me-in-production", "change-me-to-a-random-string",
            "ai-os-secret-key-change-in-production", "CHANGE_ME_IN_PRODUCTION",
        }
        if self.SECRET_KEY in insecure:
            print(
                "\n[FATAL] SECRET_KEY is not set or is an insecure placeholder.\n"
                "Generate one with:\n"
                "  python3 -c \"import secrets; print(secrets.token_hex(32))\"\n"
                "Then add it to your .env file as SECRET_KEY=<value>\n",
                file=sys.stderr,
            )
            sys.exit(1)
        if len(self.SECRET_KEY) < 32:
            print("\n[FATAL] SECRET_KEY must be at least 32 characters.\n", file=sys.stderr)
            sys.exit(1)


settings = Settings()
