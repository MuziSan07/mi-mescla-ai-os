"""AI Operating System - Configuration Module"""

import os
from typing import Optional
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
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ai-os-secret-key-change-in-production")

    def __post_init_checks(self):
        import warnings
        if self.SECRET_KEY == "ai-os-secret-key-change-in-production":
            warnings.warn(
                "WARNING: SECRET_KEY is set to the insecure default. "
                "Set SECRET_KEY env var before deploying to production!",
                stacklevel=2
            )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./aios.db")
    
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
        extra = "ignore"  # tolerate env keys not declared on this model

    @property
    def is_secure(self) -> bool:
        """Returns False if running with insecure defaults"""
        return self.SECRET_KEY != "ai-os-secret-key-change-in-production"

    @property
    def allowed_origins(self):
        raw = os.getenv("ALLOWED_ORIGINS", "*")
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()