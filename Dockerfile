# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir ".[standard]" 2>/dev/null || \
    pip install --no-cache-dir \
        fastapi==0.135.1 \
        uvicorn[standard]==0.41.0 \
        pydantic==2.12.5 \
        pydantic-settings==2.7.0 \
        python-multipart==0.0.22 \
        httpx==0.28.1 \
        redis==7.4.0 \
        aiofiles==25.1.0 \
        python-jose==3.5.0 \
        PyJWT[crypto]==2.11.0 \
        authlib==1.6.10 \
        bcrypt==5.0.0 \
        psutil \
        loguru==0.7.3 \
        aiohttp==3.13.5 \
        requests==2.33.1 \
        pytest==8.3.5 \
        pytest-asyncio==0.24.0

# ---- Runtime stage ----
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user to run the application
RUN groupadd --gid 1001 aios && \
    useradd --uid 1001 --gid aios --shell /bin/bash --create-home aios

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini ./

# Set ownership so non-root user can write to /app/src/ai_os/data (tenant DB)
RUN mkdir -p /app/src/ai_os/data && chown -R aios:aios /app

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_NAME="AI-OS"

# ── SECURITY: No secrets in ENV defaults ──────────────────────────────────
# SECRET_KEY and JWT_SECRET must be injected at runtime via:
#   - docker run -e SECRET_KEY=... -e JWT_SECRET=...
#   - docker-compose environment section (from .env file, NOT hardcoded)
#   - Kubernetes Secret mounted as env vars
#
# The application will refuse to start if these are missing or placeholder values.
# ─────────────────────────────────────────────────────────────────────────
ENV DEBUG="false"
ENV OLLAMA_BASE_URL="http://ollama:11434"
ENV REDIS_HOST="redis"
ENV REDIS_PORT="6379"
ENV RABBITMQ_HOST="rabbitmq"
ENV RABBITMQ_PORT="5672"
ENV AUTH_ENABLED="true"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health/live || exit 1

# Run as non-root
USER aios

CMD ["uvicorn", "ai_os.main:app", "--host", "0.0.0.0", "--port", "8080"]
