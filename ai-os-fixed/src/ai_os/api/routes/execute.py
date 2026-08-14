"""Task Execution API Routes — authenticated with payload validation"""

import asyncio, logging, json
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator

from ai_os.interfaces.task_queue import Task, TaskStatus, TaskPriority
from ai_os.core.orchestrator.task_queue import get_task_queue
from ai_os.core.events.event_bus import get_event_bus
from ai_os.interfaces.event_bus import Event
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/execute", tags=["execution"])
_MAX_PAYLOAD = 1_000_000  # 1 MB


class ExecuteRequest(BaseModel):
    task_type: str
    payload: Dict[str, Any]
    priority: int = 2
    timeout: Optional[float] = None

    @field_validator("task_type")
    @classmethod
    def task_type_valid(cls, v):
        v = v.strip()
        if not v or len(v) > 128: raise ValueError("task_type must be 1-128 chars")
        return v

    @field_validator("payload")
    @classmethod
    def payload_size(cls, v):
        try: s = json.dumps(v)
        except Exception as e: raise ValueError(f"Payload not JSON-serialisable: {e}")
        if len(s) > _MAX_PAYLOAD: raise ValueError("Payload exceeds 1 MB limit")
        return v

    @field_validator("priority")
    @classmethod
    def priority_range(cls, v):
        if v not in range(1, 6): raise ValueError("priority must be 1-5")
        return v

    @field_validator("timeout")
    @classmethod
    def timeout_range(cls, v):
        if v is not None and (v <= 0 or v > 600): raise ValueError("timeout must be 0-600 s")
        return v


class ExecuteResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None


@router.post("", response_model=ExecuteResponse)
async def execute_task(request: ExecuteRequest, user: TokenData = Depends(require_auth)):
    tq = get_task_queue()
    eb = get_event_bus()
    task = Task(task_type=request.task_type, payload=request.payload,
                priority=TaskPriority(request.priority), timeout=request.timeout)
    task_id = await tq.enqueue(task)
    logger.info("Task enqueued: %s type=%s user=%s", task_id, request.task_type, user.username)

    if eb:
        await eb.publish(Event(event_type="task.enqueued", source="api",
                               data={"task_id": task_id, "task_type": request.task_type, "user": user.username}))

    max_wait = request.timeout or 60.0
    try:
        for _ in range(int(max_wait)):
            await asyncio.sleep(1)
            status = await tq.get_status(task_id)
            if status is None:
                ct = getattr(tq, "_completed_tasks", {}).get(task_id)
                if ct:
                    return ExecuteResponse(task_id=task_id, status="completed",
                                           result=ct.result or {"message":"Task completed","task_type":request.task_type})
                dead = next((t for t in getattr(tq,"_dead_letter",[]) if t.task_id==task_id), None)
                if dead:
                    return ExecuteResponse(task_id=task_id, status="failed", error=dead.error or "Task failed")
            elif status == TaskStatus.COMPLETED:
                ct = getattr(tq,"_completed_tasks",{}).get(task_id)
                return ExecuteResponse(task_id=task_id, status="completed",
                                       result=ct.result if ct else {"message":"Task completed"})
            elif status == TaskStatus.FAILED:
                return ExecuteResponse(task_id=task_id, status="failed", error="Task execution failed")
        return ExecuteResponse(task_id=task_id, status="timeout", error=f"Timed out after {max_wait}s")
    except Exception as e:
        logger.error("Execution error for %s: %s", task_id, e)
        return ExecuteResponse(task_id=task_id, status="error", error=str(e))


@router.get("/queue")
async def get_queue_status(user: TokenData = Depends(require_auth)):
    return {"depth": await get_task_queue().get_queue_depth(), "max_depth": 10_000}


@router.get("/health")
async def execution_health():
    tq = get_task_queue(); eb = get_event_bus()
    return {"status":"healthy","subsystems":{"task_queue":"ok" if tq else "unavailable",
                                              "event_bus":"ok" if eb else "unavailable"}}
