"""ITaskQueue - Task Queue Contract"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time


class TaskStatus(Enum):
    """Task status states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """Task contract"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    retries_remaining: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    

class ITaskQueue(ABC):
    """Task queue contract with backpressure"""
    
    @abstractmethod
    async def enqueue(self, task: Task) -> str:
        """Enqueue task, return task_id"""
        pass
    
    @abstractmethod
    async def dequeue(self, timeout: float = 30.0) -> Optional[Task]:
        """Dequeue task with timeout"""
        pass
    
    @abstractmethod
    async def ack(self, task_id: str, result: Dict) -> bool:
        """Acknowledge task completion"""
        pass
    
    @abstractmethod
    async def nack(self, task_id: str, error: str, requeue: bool = True) -> bool:
        """Nack task failure"""
        pass
    
    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """Cancel pending task"""
        pass
    
    @abstractmethod
    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status"""
        pass
    
    @abstractmethod
    async def get_queue_depth(self) -> int:
        """Current queue depth"""
        pass
    
    @abstractmethod
    async def get_pending_tasks(self, limit: int = 100) -> List[Task]:
        """Get pending tasks"""
        pass
