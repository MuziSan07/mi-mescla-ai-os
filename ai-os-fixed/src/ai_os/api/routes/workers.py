"""AI Operating System - Workers API Route"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_os.models.schemas import (
    Worker, WorkerCreate, WorkerStats, WorkerStatus, WorkerType
)
from ai_os.core.gpu.worker_manager import get_worker_manager
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData


router = APIRouter()


class HeartbeatRequest(BaseModel):
    worker_id: str


@router.get("/", response_model=List[Worker])
async def list_workers(
    status: Optional[str] = None,
    worker_type: Optional[str] = None
,
    user: TokenData = Depends(require_auth)
):
    """List all workers"""
    worker_manager = get_worker_manager()
    
    s = None
    if status:
        try:
            s = WorkerStatus(status)
        except ValueError:
            pass
    
    wt = None
    if worker_type:
        try:
            wt = WorkerType(worker_type)
        except ValueError:
            pass
    
    return await worker_manager.list_workers(status=s, worker_type=wt)


@router.get("/{worker_id}", response_model=Worker)
async def get_worker(worker_id: str,
    user: TokenData = Depends(require_auth)
):
    """Get a specific worker"""
    worker_manager = get_worker_manager()
    worker = await worker_manager.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    return worker


@router.post("/")
async def register_worker(worker_data: WorkerCreate,
    user: TokenData = Depends(require_auth)
):
    """Register a new worker"""
    worker_manager = get_worker_manager()
    worker = await worker_manager.register_worker(worker_data)
    return worker


@router.delete("/{worker_id}")
async def unregister_worker(worker_id: str,
    user: TokenData = Depends(require_auth)
):
    """Unregister a worker"""
    worker_manager = get_worker_manager()
    result = await worker_manager.unregister_worker(worker_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    return {"status": "unregistered"}


@router.post("/heartbeat")
async def heartbeat(request: HeartbeatRequest,
    user: TokenData = Depends(require_auth)
):
    """Process worker heartbeat"""
    worker_manager = get_worker_manager()
    result = await worker_manager.heartbeat(request.worker_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    return {"status": "ok"}


@router.get("/{worker_id}/stats", response_model=WorkerStats)
async def get_worker_stats(worker_id: str,
    user: TokenData = Depends(require_auth)
):
    """Get worker statistics"""
    worker_manager = get_worker_manager()
    stats = await worker_manager.get_stats(worker_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    return stats