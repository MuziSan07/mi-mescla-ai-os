"""TaskQueue - Implementation following ITaskQueue contract"""

import asyncio
import logging
import time
from collections import deque
from typing import Dict, List, Optional

from ai_os.interfaces.task_queue import (
    ITaskQueue, Task, TaskStatus, TaskPriority
)
from ai_os.interfaces.event_bus import IEventBus, Event, EventPriority

logger = logging.getLogger(__name__)

MAX_QUEUE_DEPTH = 10000
BACKPRESSURE_THRESHOLD = 8000
RETRY_DELAYS = [1, 2, 4, 8, 16]


class TaskQueue(ITaskQueue):
    """Task queue with proper execution semantics."""

    def __init__(self, event_bus: IEventBus = None):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_DEPTH)
        self._backpressure_threshold = BACKPRESSURE_THRESHOLD
        self._pending_tasks: Dict[str, Task] = {}
        self._running_tasks: Dict[str, Task] = {}
        self._completed_tasks: Dict[str, Task] = {}
        self._dead_letter: deque = deque(maxlen=1000)
        self._event_bus = event_bus
        self._enqueued_count = 0
        self._completed_count = 0
        self._failed_count = 0
        logger.info("TaskQueue initialized")

    async def enqueue(self, task: Task) -> str:
        depth = await self.get_queue_depth()
        if depth >= self._backpressure_threshold:
            raise asyncio.QueueFull(f"Backpressure: {depth}")
        task.status = TaskStatus.PENDING
        task.created_at = time.time()
        self._pending_tasks[task.task_id] = task
        self._queue.put_nowait(task)
        self._enqueued_count += 1
        if self._event_bus:
            event = Event(
                event_type="task.enqueued",
                source="task_queue",
                data={"task_id": task.task_id}
            )
            await self._event_bus.publish(event)
        return task.task_id

    async def dequeue(self, timeout: float = 30.0) -> Optional[Task]:
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self._running_tasks[task.task_id] = task
            self._pending_tasks.pop(task.task_id, None)
            return task
        except asyncio.TimeoutError:
            return None

    async def ack(self, task_id: str, result: Dict) -> bool:
        task = self._running_tasks.pop(task_id) or self._pending_tasks.pop(task_id)
        if not task:
            return False
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = time.time()
        self._completed_tasks[task_id] = task
        if len(self._completed_tasks) > 1000:
            self._completed_tasks.pop(next(iter(self._completed_tasks)))
        self._completed_count += 1
        return True

    async def nack(self, task_id: str, error: str, requeue: bool = True) -> bool:
        task = self._running_tasks.pop(task_id)
        if not task:
            return False
        if requeue and task.retries_remaining > 0:
            task.retries_remaining -= 1
            task.status = TaskStatus.RETRYING
            delay = RETRY_DELAYS[min(len(RETRY_DELAYS) - 1, task.retries_remaining)]
            asyncio.create_task(self._retry_after(task, delay))
            return True
        task.status = TaskStatus.FAILED
        task.error = error
        self._failed_count += 1
        self._dead_letter.append(task)
        return True

    async def _retry_after(self, task: Task, delay: float):
        await asyncio.sleep(delay)
        task.status = TaskStatus.PENDING
        self._pending_tasks[task.task_id] = task
        self._queue.put_nowait(task)

    async def cancel(self, task_id: str) -> bool:
        task = self._pending_tasks.pop(task_id)
        if not task:
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        return True

    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        # Check pending and running first
        task = self._pending_tasks.get(task_id) or self._running_tasks.get(task_id)
        if task:
            return task.status
        # Check completed tasks
        completed = self._completed_tasks.get(task_id)
        if completed:
            return TaskStatus.COMPLETED
        # Check dead letter queue for failed tasks
        dead = next((t for t in self._dead_letter if t.task_id == task_id), None)
        if dead:
            return TaskStatus.FAILED
        return None

    async def get_queue_depth(self) -> int:
        return self._queue.qsize()

    async def get_pending_tasks(self, limit: int = 100) -> List[Task]:
        return list(self._pending_tasks.values())[:limit]


_task_queue: Optional[ITaskQueue] = None


def get_task_queue(event_bus: IEventBus = None) -> ITaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(event_bus=event_bus)
    return _task_queue
