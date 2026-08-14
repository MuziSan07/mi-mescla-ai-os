"""
AI Operating System - GPU Worker Manager

Manages distributed GPU workers including Google Colab instances,
handles task distribution, result synchronization, and heartbeat monitoring.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

from ai_os.models.schemas import (
    WorkerStatus, WorkerType, Worker, WorkerStats, WorkerCreate
)
from ai_os.core.events.event_bus import get_event_bus, EventTypes
from ai_os.interfaces.event_bus import Event

logger = logging.getLogger(__name__)


class GPUWorkerManager:
    """
    Manages distributed GPU workers for parallel task execution
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        heartbeat_interval: int = 30,
        worker_timeout: int = 300
    ):
        self._workers: Dict[str, Worker] = {}
        self._worker_stats: Dict[str, WorkerStats] = {}
        self._max_workers = max_workers
        self._heartbeat_interval = heartbeat_interval
        self._worker_timeout = worker_timeout
        self._lock = asyncio.Lock()
        self._event_bus = get_event_bus()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the worker manager"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_workers())
        logger.info("GPU Worker Manager started")
    
    async def stop(self):
        """Stop the worker manager"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("GPU Worker Manager stopped")
    
    async def register_worker(self, worker_data: WorkerCreate) -> Worker:
        """Register a new GPU worker"""
        async with self._lock:
            # Check max workers
            if len(self._workers) >= self._max_workers:
                raise RuntimeError(f"Maximum workers ({self._max_workers}) reached")
            
            worker_id = f"worker-{uuid4().hex[:8]}"
            
            worker = Worker(
                id=worker_id,
                name=worker_data.name,
                worker_type=worker_data.worker_type,
                status=WorkerStatus.IDLE,
                endpoint=worker_data.endpoint,
                capabilities=worker_data.capabilities,
                created_at=datetime.utcnow()
            )
            
            self._workers[worker_id] = worker
            self._worker_stats[worker_id] = WorkerStats()
            
            # Emit event
            await self._event_bus.publish(Event(
                event_type=EventTypes.WORKER_REGISTERED,
                source="gpu_manager",
                data={"worker_id": worker_id, "worker_type": worker_data.worker_type.value}
            ))
            
            logger.info(f"Registered worker: {worker_id}")
            return worker
    
    async def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker"""
        async with self._lock:
            if worker_id not in self._workers:
                return False
            
            del self._workers[worker_id]
            if worker_id in self._worker_stats:
                del self._worker_stats[worker_id]
            
            logger.info(f"Unregistered worker: {worker_id}")
            return True
    
    async def heartbeat(self, worker_id: str) -> bool:
        """Process worker heartbeat"""
        async with self._lock:
            if worker_id not in self._workers:
                return False
            
            worker = self._workers[worker_id]
            worker.last_heartbeat = datetime.utcnow()
            
            if worker.status == WorkerStatus.DEAD:
                worker.status = WorkerStatus.IDLE
                logger.info(f"Worker recovered: {worker_id}")
            
            return True
    
    async def assign_task(self, worker_id: str, task_id: str) -> bool:
        """Assign a task to a worker"""
        async with self._lock:
            if worker_id not in self._workers:
                return False
            
            worker = self._workers[worker_id]
            if worker.status != WorkerStatus.IDLE:
                return False
            
            worker.status = WorkerStatus.BUSY
            worker.current_task = task_id
            
            if worker_id in self._worker_stats:
                self._worker_stats[worker_id].total_tasks += 1
            
            return True
    
    async def complete_task(
        self,
        worker_id: str,
        task_id: str,
        result: Dict[str, Any]
    ):
        """Mark task as completed"""
        async with self._lock:
            if worker_id not in self._workers:
                return
            
            worker = self._workers[worker_id]
            worker.status = WorkerStatus.IDLE
            worker.current_task = None
            
            if worker_id in self._worker_stats:
                stats = self._worker_stats[worker_id]
                stats.completed_tasks += 1
    
    async def mark_dead(self, worker_id: str):
        """Mark a worker as dead"""
        async with self._lock:
            if worker_id not in self._workers:
                return
            
            worker = self._workers[worker_id]
            worker.status = WorkerStatus.DEAD
            
            # Emit event
            await self._event_bus.publish(Event(
                event_type=EventTypes.WORKER_DEAD,
                source="gpu_manager",
                data={"worker_id": worker_id}
            ))
            
            logger.warning(f"Worker marked dead: {worker_id}")
    
    async def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Get worker by ID"""
        return self._workers.get(worker_id)
    
    async def list_workers(
        self,
        status: Optional[WorkerStatus] = None,
        worker_type: Optional[WorkerType] = None
    ) -> List[Worker]:
        """List workers with optional filtering"""
        workers = list(self._workers.values())
        
        if status:
            workers = [w for w in workers if w.status == status]
        
        if worker_type:
            workers = [w for w in workers if w.worker_type == worker_type]
        
        return workers
    
    async def get_available_worker(
        self,
        required_capabilities: Optional[List[str]] = None
    ) -> Optional[Worker]:
        """Get an available worker"""
        for worker in self._workers.values():
            if worker.status != WorkerStatus.IDLE:
                continue
            
            if required_capabilities:
                if not all(
                    cap in worker.capabilities
                    for cap in required_capabilities
                ):
                    continue
            
            return worker
        
        return None
    
    async def get_stats(self, worker_id: str) -> Optional[WorkerStats]:
        """Get worker statistics"""
        return self._worker_stats.get(worker_id)
    
    async def _monitor_workers(self):
        """Monitor worker heartbeats"""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                now = datetime.utcnow()
                timeout = timedelta(seconds=self._worker_timeout)
                
                async with self._lock:
                    for worker_id, worker in self._workers.items():
                        if worker.last_heartbeat:
                            if now - worker.last_heartbeat > timeout:
                                await self.mark_dead(worker_id)
                        
                        # Check for workers that have been dead too long
                        if worker.status == WorkerStatus.DEAD:
                            if worker.last_heartbeat:
                                if now - worker.last_heartbeat > timeout * 2:
                                    # Remove dead worker after double timeout
                                    logger.info(f"Removing dead worker: {worker_id}")
                                    self._workers.pop(worker_id, None)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker monitor error: {e}")
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health of worker pool"""
        total = len(self._workers)
        by_status = {}
        by_type = {}
        
        for worker in self._workers.values():
            status = worker.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            wtype = worker.worker_type.value
            by_type[wtype] = by_type.get(wtype, 0) + 1
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "max_workers": self._max_workers
        }


# Singleton instance
_worker_manager_instance: Optional[GPUWorkerManager] = None


def get_worker_manager() -> GPUWorkerManager:
    """Get the worker manager singleton"""
    global _worker_manager_instance
    if _worker_manager_instance is None:
        _worker_manager_instance = GPUWorkerManager()
    return _worker_manager_instance