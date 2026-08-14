"""
AI Operating System - Main FastAPI Application
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from ai_os.config.settings import settings
from ai_os.core.events.event_bus import get_event_bus
from ai_os.core.router.model_pool import get_model_pool
from ai_os.core.gpu.worker_manager import get_worker_manager
from ai_os.core.orchestrator.task_queue import get_task_queue
from ai_os.core.vision.processor import get_vision_pipeline
from ai_os.core.memory.short_term import get_memory_store
from ai_os.core.audit.auditor import get_auditor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Starting AI-OS...")

    # EventBus — no start() method, just initialize
    event_bus = get_event_bus()
    logger.info("EventBus ready")

    # Model pool
    model_pool = get_model_pool()
    await model_pool.initialize_default_models()
    logger.info("Model pool ready")

    # Worker manager — has start()
    worker_manager = get_worker_manager()
    await worker_manager.start()
    logger.info("Worker manager ready")

    # Task queue — no start() method, just initialize
    task_queue = get_task_queue()
    logger.info("Task queue ready")

    # Vision pipeline — has initialize()
    vision = get_vision_pipeline()
    await vision.initialize()
    logger.info("Vision pipeline ready")

    # Memory store — no start needed
    memory = get_memory_store()
    logger.info("Memory store ready")

    # Auditor — has start()
    auditor = get_auditor()
    await auditor.start()
    logger.info("Auditor ready")

    logger.info("AI-OS started successfully")

    yield

    # Shutdown
    logger.info("Shutting down AI-OS...")
    await auditor.stop()
    await worker_manager.stop()
    logger.info("AI-OS stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from ai_os.api.routes import chat, models, workers, vision, memory, tools, health
from ai_os.api.routes import agents, browser, vms, gateway, tunnels, source, audit, runtime_validate, observability
from ai_os.api.routes import worker_lifecycle, execute, dashboard, voice, conductor, developer, knowledge, setup

app.include_router(chat.router, prefix=settings.API_PREFIX, tags=["chat"])
app.include_router(models.router, prefix=settings.API_PREFIX + "/models", tags=["models"])
app.include_router(workers.router, prefix=settings.API_PREFIX + "/workers", tags=["workers"])
app.include_router(vision.router, prefix=settings.API_PREFIX + "/vision", tags=["vision"])
app.include_router(memory.router, prefix=settings.API_PREFIX + "/memory", tags=["memory"])
app.include_router(tools.router, prefix=settings.API_PREFIX + "/tools", tags=["tools"])
app.include_router(health.router, prefix=settings.API_PREFIX + "/health", tags=["health"])
app.include_router(agents.router, prefix=settings.API_PREFIX + "/agents", tags=["agents"])
app.include_router(browser.router, prefix=settings.API_PREFIX + "/browser", tags=["browser"])
app.include_router(vms.router, prefix=settings.API_PREFIX + "/vms", tags=["vms"])
app.include_router(gateway.router, prefix=settings.API_PREFIX + "/gateway", tags=["gateway"])
app.include_router(tunnels.router, prefix=settings.API_PREFIX + "/tunnels", tags=["tunnels"])
app.include_router(source.router, prefix=settings.API_PREFIX + "/source", tags=["source"])
app.include_router(audit.router, prefix=settings.API_PREFIX + "/audit", tags=["audit"])
app.include_router(runtime_validate.router, prefix=settings.API_PREFIX + "/runtime", tags=["runtime"])
app.include_router(observability.router, prefix=settings.API_PREFIX + "/observe", tags=["observe"])
app.include_router(worker_lifecycle.router, prefix=settings.API_PREFIX + "/lifecycle", tags=["lifecycle"])
# dashboard routes already include the /dashboard/ path internally -> mount at API root
app.include_router(dashboard.router, prefix=settings.API_PREFIX, tags=["dashboard"])
# execute router carries its own full /api/v1/execute prefix
app.include_router(execute.router, tags=["execution"])
app.include_router(voice.router, prefix=settings.API_PREFIX + "/voice", tags=["voice"])
app.include_router(conductor.router, prefix=settings.API_PREFIX + "/conductor", tags=["conductor"])
app.include_router(developer.router, prefix=settings.API_PREFIX + "/developer", tags=["developer"])
app.include_router(knowledge.router, prefix=settings.API_PREFIX + "/knowledge", tags=["knowledge"])
app.include_router(setup.router, prefix=settings.API_PREFIX + "/setup", tags=["setup"])


@app.get("/dashboard-ui", response_class=HTMLResponse)
async def dashboard_ui():
    """Serve the AI-OS Dashboard UI.

    Resolves the dashboard HTML from several candidate locations so it works
    both in Docker (/app/...) and on a bare VM/appliance install. Override with
    the DASHBOARD_HTML env var.
    """
    import os
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.getenv("DASHBOARD_HTML", ""),
        "/app/frontend/dashboard.html",
        os.path.join(repo_root, "frontend", "dashboard.html"),
        os.path.join(repo_root, "dashboard.html"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Dashboard not found</h1><p>Set DASHBOARD_HTML to the dashboard.html path.</p>",
        status_code=404,
    )

def _serve_frontend(filename: str, env_var: str) -> HTMLResponse:
    """Resolve a frontend HTML file across Docker/VM/dev layouts and serve it."""
    import os
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.getenv(env_var, ""),
        f"/app/frontend/{filename}",
        os.path.join(repo_root, "frontend", filename),
        os.path.join(repo_root, filename),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(content=f"<h1>{filename} not found</h1>", status_code=404)


@app.get("/voice-ui", response_class=HTMLResponse)
async def voice_ui():
    """Serve the push-to-talk voice assistant page."""
    return _serve_frontend("voice.html", "VOICE_HTML")


@app.get("/setup-ui", response_class=HTMLResponse)
async def setup_ui():
    """Serve the first-run setup wizard."""
    return _serve_frontend("setup.html", "SETUP_HTML")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "dashboard": "/dashboard-ui",
        "voice": "/voice-ui",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_os.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG
    )
