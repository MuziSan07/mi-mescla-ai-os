"""IWorkerManager - Worker Manager Contract"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid


class WorkerStatus(Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    BUSY = "busy"
    UNHEALTHY = "unhealthy"
    DEAD = "dead"


@dataclass
class WorkerSpec:
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    worker_type: str = "cpu"  # gpu, cpu, browser
    capacity: Dict[str, Any] = field(default_factory=dict)
    zones: List[str] = field(default_factory=list)


@dataclass
class WorkerInfo:
    worker_id: str
    status: WorkerStatus
    spec: WorkerSpec
    current_task: Optional[str] = None
    metrics: Dict = field(default_factory=dict)


class IWorkerManager(ABC):
    @abstractmethod
    async def register_worker(self, spec: WorkerSpec) -> str:
        pass
    
    @abstractmethod
    async def unregister_worker(self, worker_id: str) -> bool:
        pass
    
    @abstractmethod
    async def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        pass
    
    @abstractmethod
    async def assign_task(self, worker_id: str, task: Dict) -> bool:
        pass
    
    @abstractmethod
    async def heartbeat(self, worker_id: str, metrics: Dict) -> None:
        pass
    
    @abstractmethod
    async def list_workers(self, status: WorkerStatus = None) -> List[WorkerInfo]:
        pass
