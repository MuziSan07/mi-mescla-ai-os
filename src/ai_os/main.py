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
from ai_os.api.routes import worker_lifecycle, execute

app.include_router(chat.router, prefix=settings.API_PREFIX, tags=["chat"])
app.include_router(models.router, prefix=settings.API_PREFIX, tags=["models"])
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


@app.get("/dashboard-ui", response_class=HTMLResponse)
async def dashboard_ui():
    """Serve the AI-OS Dashboard UI"""
    import os
    dashboard_path = "/app/frontend/dashboard.html"
    if os.path.exists(dashboard_path):
        with open(dashboard_path) as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard not found</h1>")

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "dashboard": "/dashboard-ui",
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
