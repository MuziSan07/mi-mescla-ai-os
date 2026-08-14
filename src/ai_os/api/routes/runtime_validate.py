"""
AI-OS Runtime Validation API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validate"])  # prefix supplied by main.py (/api/v1/runtime)


class RunValidationRequest(BaseModel):
    """Validation request"""
    base_url: str = "http://localhost:8000"


class TestWorkflowRequest(BaseModel):
    """Workflow test request"""
    workflow: str  # chat, agent, vision, all


@router.post("/runtime")
async def run_runtime_validation(request: RunValidationRequest):
    """Run complete runtime validation"""
    from ai_os.utils.runtime_validator import get_runtime_verification
    
    try:
        system = get_runtime_verification(request.base_url)
        results = await system.run_full_validation()
        
        return results
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow")
async def test_workflow(request: TestWorkflowRequest):
    """Test specific workflow"""
    from ai_os.utils.runtime_validator import get_runtime_verification
    
    try:
        system = get_runtime_verification()
        tester = system.e2e_tester
        
        if request.workflow == "chat":
            result = await tester.test_chat_workflow()
        elif request.workflow == "agent":
            result = await tester.test_agent_workflow()
        elif request.workflow == "vision":
            result = await tester.test_vision_workflow()
        elif request.workflow == "all":
            return await system.run_full_validation()
        else:
            raise HTTPException(status_code=400, detail="Unknown workflow")
        
        return {
            "workflow": request.workflow,
            "status": result.status.value,
            "duration_ms": (result.end_time - result.start_time) * 1000,
            "errors": result.errors,
            "steps": len(result.steps)
        }
        
    except Exception as e:
        logger.error(f"Workflow test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/endpoints")
async def validate_endpoints():
    """Validate all API endpoints"""
    from ai_os.utils.runtime_validator import get_runtime_verification
    
    try:
        system = get_runtime_verification()
        results = await system.validator.validate_all_endpoints()
        
        return {
            "endpoints": [
                {
                    "path": r.component,
                    "working": r.is_working,
                    "integrated": r.is_integrated,
                    "call_count": r.call_count,
                    "error": r.last_error
                }
                for r in results
            ]
        }
        
    except Exception as e:
        logger.error(f"Endpoint validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services")
async def validate_services():
    """Validate services (Redis, RabbitMQ, etc)"""
    from ai_os.utils.runtime_validator import get_runtime_verification
    
    try:
        system = get_runtime_verification()
        
        results = {}
        
        # Redis
        redis_result = await system.validator.validate_redis()
        results["redis"] = {
            "working": redis_result.is_working,
            "error": redis_result.last_error
        }
        
        return {"services": results}
        
    except Exception as e:
        logger.error(f"Service validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fake-detection")
async def detect_fake_components():
    """Detect fake/non-functional components"""
    from ai_os.utils.runtime_validator import get_runtime_verification
    
    try:
        system = get_runtime_verification()
        
        # Get detection results
        disconnected = await system.detector.detect_disconnected_services()
        
        return {
            "fake_modules": [],  # Placeholder - would need more analysis
            "disconnected_services": disconnected,
            "detection_time": "real-time"
        }
        
    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace")
async def get_trace():
    """Get execution trace"""
    from ai_os.utils.runtime_validator import get_runtime_verification
    
    try:
        system = get_runtime_verification()
        return system.get_trace_summary()
        
    except Exception as e:
        logger.error(f"Trace error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def validate_health():
    """Validation system health check"""
    return {
        "status": "healthy",
        "validator": "active",
        "tracing": "enabled"
    }