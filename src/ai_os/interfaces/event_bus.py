"""IEventBus - Event Bus Contract"""

from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid
import time


class EventPriority(Enum):
    """Event priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class EventTypes(str, Enum):
    """System event types"""
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    WORKER_REGISTERED = "worker.registered"
    WORKER_HEARTBEAT = "worker.heartbeat"
    WORKER_DEAD = "worker.dead"
    MODEL_SELECTED = "model.selected"
    AUDIT_STARTED = "audit.started"
    AUDIT_COMPLETED = "audit.completed"
    AGENT_STATE_CHANGED = "agent.state.changed"


@dataclass(frozen=True)
class Event:
    """Immutable event contract"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Subscription:
    """Subscription metadata"""
    def __init__(self, subscription_id: str, event_type: str, handler, priority: EventPriority):
        self.subscription_id = subscription_id
        self.event_type = event_type
        self.handler = handler
        self.priority = priority
        self.created_at = time.time()


class IEventBus(ABC):
    """EventBus contract - pub/sub with guarantees"""
    
    @abstractmethod
    async def subscribe(
        self, 
        event_type: str, 
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL
    ) -> str:
        """Subscribe to event type, return subscription_id"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe by ID, return success"""
        pass
    
    @abstractmethod
    async def publish(self, event: Event, wait: bool = False) -> int:
        """Publish event, optionally wait for handlers, return handler count"""
        pass
    
    @abstractmethod
    async def get_subscription_status(self, subscription_id: str) -> Dict:
        """Health check for subscription"""
        pass
    
    @abstractmethod
    async def flush(self) -> int:
        """Process all pending events, return count"""
        pass
    
    @abstractmethod
    def get_subscriptions(self, event_type: str) -> List[Subscription]:
        """Get all subscriptions for event type"""
        pass
    
    @abstractmethod
    def get_pending_count(self) -> int:
        """Get pending event count"""
        pass
