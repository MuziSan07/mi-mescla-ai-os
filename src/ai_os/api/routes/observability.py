"""
AI-OS Distributed Observability API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observe"])  # prefix supplied by main.py (/api/v1/observe)


class RunObservabilityRequest(BaseModel):
    """Observability request"""
    base_url: str = "http://localhost:8000"


@router.post("/full")
async def run_full_observability(request: RunObservabilityRequest):
    """Run full distributed observability suite"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability(request.base_url)
        results = await system.run_full_observability()
        
        return results
        
    except Exception as e:
        logger.error(f"Observability error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coverage")
async def get_execution_coverage():
    """Get execution coverage"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability()
        coverage = await system.measure_real_execution_coverage()
        
        return coverage
        
    except Exception as e:
        logger.error(f"Coverage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources")
async def get_resources():
    """Get resource usage"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability()
        
        resource = await system.resource_monitor.take_snapshot()
        trends = system.resource_monitor.get_trends()
        anomalies = system.resource_monitor.detect_anomalies()
        
        return {
            "snapshot": {
                "cpu_percent": resource.cpu_percent,
                "memory_percent": resource.memory_percent,
                "memory_used_mb": resource.memory_used_mb,
                "gpu_utilization": resource.gpu_utilization,
                "gpu_memory_used_mb": resource.gpu_memory_used_mb
            },
            "trends": trends,
            "anomalies": anomalies
        }
        
    except Exception as e:
        logger.error(f"Resources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores")
async def get_reality_scores():
    """Get reality scores"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability()
        scores = await system.calculate_reality_scores()
        
        return {
            "runtime_integrity": scores.runtime_integrity,
            "workflow_completion": scores.workflow_completion,
            "distributed_stability": scores.distributed_stability,
            "recovery_success": scores.recovery_success,
            "execution_coverage": scores.execution_coverage,
            "event_consistency": scores.event_consistency,
            "queue_stability": scores.queue_stability,
            "resource_stability": scores.resource_stability,
            "overall": scores.overall
        }
        
    except Exception as e:
        logger.error(f"Scores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows")
async def get_workflow_states():
    """Get workflow states"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability()
        states = system.workflow_validator.get_workflow_states()
        stats = system.workflow_validator.validate_workflow_completion()
        deadlocks = system.workflow_validator.detect_deadlocks()
        
        return {
            "states": states,
            "stats": stats,
            "deadlocks": deadlocks
        }
        
    except Exception as e:
        logger.error(f"Workflows error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chaos")
async def run_chaos_tests():
    """Run chaos test suite"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability()
        results = await system.chaos_engine.run_chaos_suite()
        
        return results
        
    except Exception as e:
        logger.error(f"Chaos test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies")
async def detect_anomalies():
    """Detect system anomalies"""
    from ai_os.utils.observability import get_observability
    
    try:
        system = get_observability()
        
        resource_anomalies = system.resource_monitor.detect_anomalies()
        workflow_deadlocks = system.workflow_validator.detect_deadlocks()
        
        return {
            "resource_anomalies": resource_anomalies,
            "workflow_deadlocks": workflow_deadlocks,
            "detection_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Anomalies error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def observe_health():
    """Observability system health"""
    return {
        "status": "healthy",
        "observability": "active",
        "coverage_tracker": "active",
        "resource_monitor": "active",
        "chaos_engine": "active"
    }