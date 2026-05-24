"""Task Execution API Routes - Real endpoint integration"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import logging

from ai_os.interfaces.task_queue import Task, TaskStatus, TaskPriority
from ai_os.core.orchestrator.task_queue import get_task_queue
from ai_os.core.events.event_bus import get_event_bus
from ai_os.interfaces.event_bus import Event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/execute", tags=["execution"])


class ExecuteRequest(BaseModel):
    """Request to execute a task"""
    task_type: str
    payload: Dict[str, Any]
    priority: int = 2  # Normal
    timeout: Optional[float] = None


class ExecuteResponse(BaseModel):
    """Response from task execution"""
    task_id: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None


@router.post("", response_model=ExecuteResponse)
async def execute_task(request: ExecuteRequest):
    """
    Execute a task end-to-end.
    API -> TaskQueue -> Worker -> Tool -> Response
    """
    # get_task_queue and get_event_bus are sync singletons — do NOT await them
    tq = get_task_queue()
    eb = get_event_bus()

    task = Task(
        task_type=request.task_type,
        payload=request.payload,
        priority=TaskPriority(request.priority),
        timeout=request.timeout
    )

    # Enqueue task
    task_id = await tq.enqueue(task)
    logger.info(f"Task enqueued: {task_id}")

    # Notify via event bus
    if eb:
        await eb.publish(Event(
            event_type="task.enqueued",
            source="api",
            data={"task_id": task_id, "task_type": request.task_type}
        ))

    max_wait = request.timeout or 60.0

    try:
        for _ in range(int(max_wait)):
            await asyncio.sleep(1)

            # Check pending and running queues
            status = await tq.get_status(task_id)

            if status is None:
                # Not in pending/running — check completed dict directly
                completed_task = tq._completed_tasks.get(task_id)  # type: ignore[attr-defined]
                if completed_task:
                    return ExecuteResponse(
                        task_id=task_id,
                        status="completed",
                        result=completed_task.result or {
                            "message": "Task completed",
                            "task_type": request.task_type
                        }
                    )
                # Check dead letter for failed tasks
                dead = next(
                    (t for t in getattr(tq, "_dead_letter", []) if t.task_id == task_id),
                    None
                )
                if dead:
                    return ExecuteResponse(
                        task_id=task_id,
                        status="failed",
                        error=dead.error or "Task execution failed"
                    )

            elif status == TaskStatus.COMPLETED:
                completed_task = getattr(tq, "_completed_tasks", {}).get(task_id)
                return ExecuteResponse(
                    task_id=task_id,
                    status="completed",
                    result=completed_task.result if completed_task else {
                        "message": "Task completed",
                        "task_type": request.task_type
                    }
                )

            elif status == TaskStatus.FAILED:
                return ExecuteResponse(
                    task_id=task_id,
                    status="failed",
                    error="Task execution failed"
                )

        # Timed out
        return ExecuteResponse(
            task_id=task_id,
            status="timeout",
            error=f"Task timed out after {max_wait}s"
        )

    except Exception as e:
        logger.error(f"Execution error: {e}")
        return ExecuteResponse(
            task_id=task_id,
            status="error",
            error=str(e)
        )


@router.get("/queue")
async def get_queue_status():
    """Get current queue status"""
    tq = get_task_queue()  # sync — no await
    return {
        "depth": await tq.get_queue_depth(),
        "max_depth": 10000
    }


@router.get("/health")
async def execution_health():
    """Execution subsystem health"""
    tq = get_task_queue()
    eb = get_event_bus()
    return {
        "status": "healthy",
        "subsystems": {
            "task_queue": "ok" if tq else "unavailable",
            "event_bus": "ok" if eb else "unavailable"
        }
    }
