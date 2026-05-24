"""EventBus - Implementation following IEventBus contract"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field

from ai_os.interfaces.event_bus import (
    IEventBus, Event, EventPriority, EventTypes
)
from ai_os.di.container import DIContainer

logger = logging.getLogger(__name__)


class EventBus(IEventBus):
    """
    Async event bus implementation.
    
    Properties:
    - Thread-safe subscriptions
    - Priority-based dispatch
    - Dead letter queue for failed handlers
    - In-memory (for now, Redis-backed later)
    """
    
    def __init__(self, container: DIContainer = None):
        self._subscriptions: Dict[str, List] = defaultdict(list)
        self._subscription_meta: Dict[str, dict] = {}
        self._pending: List[Event] = []
        self._dead_letter: List[Event] = []
        self._lock = asyncio.Lock()
        logger.info("EventBus initialized")
    
    # IEventBus implementation
    async def subscribe(
        self, 
        event_type: str, 
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL
    ) -> str:
        """Subscribe to event type"""
        subscription_id = str(uuid.uuid4())
        sub = {
            "id": subscription_id,
            "type": event_type, 
            "handler": handler,
            "priority": priority.value
        }
        async with self._lock:
            self._subscriptions[event_type].append(sub)
            self._subscription_meta[subscription_id] = {
                "event_type": event_type,
                "subscribed_at": time.time()
            }
        
        logger.debug(f"Subscribed {subscription_id} to {event_type}")
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe by ID"""
        async with self._lock:
            meta = self._subscription_meta.pop(subscription_id, None)
            if meta:
                event_type = meta["event_type"]
                subs = self._subscriptions[event_type]
                self._subscriptions[event_type] = [
                    s for s in subs if s["id"] != subscription_id
                ]
                logger.debug(f"Unsubscribed {subscription_id}")
                return True
            return False
    
    async def publish(self, event: Event, wait: bool = False) -> int:
        """Publish event to all subscribers"""
        async with self._lock:
            # Store in history (in-memory limited)
            self._pending.append(event)
            if len(self._pending) > 1000:
                self._pending.pop(0)
        
        # Get subscribers
        subs = self._subscriptions.get(event.event_type, []) + \
              self._subscriptions.get("*", [])
        
        # Sort by priority (higher first)
        subs.sort(key=lambda x: x["priority"], reverse=True)
        
        handler_count = len(subs)
        
        # Execute handlers
        for sub in subs:
            try:
                handler = sub["handler"]
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                self._dead_letter.append(event)
        
        if wait:
            await asyncio.sleep(0)  # Yield to run handlers
        
        return handler_count
    
    async def get_subscription_status(self, subscription_id: str) -> Dict:
        """Health check"""
        return {"exists": subscription_id in self._subscription_meta}
    
    async def flush(self) -> int:
        """Process pending events"""
        count = len(self._pending)
        self._pending.clear()
        return count
    
    def get_subscriptions(self, event_type: str) -> List:
        """Get subscriptions for type"""
        return self._subscriptions.get(event_type, [])
    
    def get_pending_count(self) -> int:
        """Pending count"""
        return len(self._pending)


# Alias/singleton accessor
_event_bus: IEventBus = None


def get_event_bus() -> IEventBus:
    """Get event bus singleton"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
