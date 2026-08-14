"""
AI-OS Colab Worker Lifecycle API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workers", tags=["workers"])


class StartWorkerRequest(BaseModel):
    """Start worker request"""
    credentials: dict = {}
    worker_config: Optional[dict] = None


class WorkerResponse(BaseModel):
    """Worker info"""
    worker_id: str
    status: str
    gpu_available: bool
    uptime_seconds: float


class RecoveryRequest(BaseModel):
    """Recovery request"""
    worker_id: str


@router.post("/start")
async def start_worker(request: StartWorkerRequest,
    user: TokenData = Depends(require_auth)
):
    """Start a new Colab worker"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        worker = await manager.start_worker(
            request.credentials,
            request.worker_config
        )
        
        return {
            "worker_id": worker.worker_id,
            "status": worker.status.value,
            "session_id": worker.session_id,
            "gpu_available": worker.gpu_available
        }
        
    except Exception as e:
        logger.error(f"Start worker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{worker_id}")
async def stop_worker(worker_id: str,
    user: TokenData = Depends(require_auth)
):
    """Stop a worker"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        await manager.stop_worker(worker_id)
        
        return {"message": f"Worker {worker_id} stopped"}
        
    except Exception as e:
        logger.error(f"Stop worker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_workers(user: TokenData = Depends(require_auth)):
    """List all workers"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        workers = list(manager.registry.workers.values())
        
        return {
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "status": w.status.value,
                    "gpu_available": w.gpu_available,
                    "gpu_type": w.gpu_type,
                    "uptime_seconds": time.time() - w.created_at,
                    "tasks_completed": w.task_completed,
                    "tasks_failed": w.task_failed
                }
                for w in workers
            ]
        }
        
    except Exception as e:
        logger.error(f"List workers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{worker_id}")
async def get_worker(worker_id: str,
    user: TokenData = Depends(require_auth)
):
    """Get worker details"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        worker = manager.registry.get_worker(worker_id)
        
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        
        return {
            "worker_id": worker.worker_id,
            "status": worker.status.value,
            "gpu_available": worker.gpu_available,
            "gpu_type": worker.gpu_type,
            "gpu_memory_total": worker.gpu_memory_total,
            "gpu_memory_used": worker.gpu_memory_used,
            "cpu_usage": worker.cpu_usage,
            "ram_usage": worker.ram_usage,
            "vram_usage": worker.vram_usage,
            "uptime_seconds": time.time() - worker.created_at,
            "tasks_completed": worker.task_completed,
            "tasks_failed": worker.task_failed,
            "health_score": worker.health_score
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get worker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recover/{worker_id}")
async def recover_worker(worker_id: str,
    user: TokenData = Depends(require_auth)
):
    """Recover a worker"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        result = await manager.recovery_engine.recover_worker(
            worker_id,
            manager.auth_manager
        )
        
        return {
            "success": result.success,
            "recovery_time_ms": result.recovery_time_ms,
            "actions_taken": result.actions_taken,
            "tasks_restored": result.tasks_restored,
            "error": result.error
        }
        
    except Exception as e:
        logger.error(f"Recover error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_worker_stats(user: TokenData = Depends(require_auth)):
    """Get worker statistics"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        return await manager.get_worker_stats()
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def workers_health(user: TokenData = Depends(require_auth)):
    """Workers health check"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        health = await manager.health_monitor.check_all_workers()
        
        return health
        
    except Exception as e:
        logger.error(f"Health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints")
async def get_checkpoints(user: TokenData = Depends(require_auth)):
    """Get task checkpoints"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        pending = manager.checkpoints.get_pending_tasks()
        
        return {
            "pending_checkpoints": pending,
            "count": len(pending)
        }
        
    except Exception as e:
        logger.error(f"Checkpoints error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/checkpoint/{task_id}")
async def delete_checkpoint(task_id: str,
    user: TokenData = Depends(require_auth)
):
    """Delete a checkpoint"""
    from ai_os.utils.colab_worker_lifecycle import get_lifecycle_manager
    
    try:
        manager = get_lifecycle_manager()
        await manager.checkpoints.delete_checkpoint(task_id)
        
        return {"message": f"Checkpoint {task_id} deleted"}
        
    except Exception as e:
        logger.error(f"Delete checkpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


import time  # Add missing import
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData
