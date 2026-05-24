"""AI Operating System - Health API Route"""

from fastapi import APIRouter
from datetime import datetime

from ai_os.models.schemas import HealthStatus

router = APIRouter()


@router.get("/")
async def health_check():
    """Health check endpoint"""
    # Would check all components
    components = {
        "api": "healthy",
        "event_bus": "healthy",
        "model_pool": "healthy",
        "worker_manager": "healthy",
        "task_queue": "healthy",
        "vision": "healthy",
        "memory": "healthy",
        "auditor": "healthy"
    }
    
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow(),
        components=components
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check"""
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """Liveness check"""
    return {"alive": True}