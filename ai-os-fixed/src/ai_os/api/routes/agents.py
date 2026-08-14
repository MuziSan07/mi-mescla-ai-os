"""
AI-OS Agent API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from ai_os.core.orchestrator.agent_mesh import (
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData

    get_agent_coordinator,
    AgentTask,
    AgentSpecialization,
    AgentCoordinator
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])


class AgentRequest(BaseModel):
    """Request to execute an agent task"""
    task_type: str
    prompt: str
    context: Optional[Dict[str, Any]] = {}
    files: Optional[List[str]] = []


class AgentResponse(BaseModel):
    """Response from agent execution"""
    task_id: str
    agent_type: str
    response: str
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AgentStatsResponse(BaseModel):
    """Agent system statistics"""
    total_tasks: int
    total_time: float
    agents: Dict[str, Any]


@router.post("/execute", response_model=AgentResponse)
async def execute_agent(request: AgentRequest,
    user: TokenData = Depends(require_auth)
):
    """Execute a task with the appropriate specialized agent"""
    try:
        coordinator = get_agent_coordinator()
        
        task = AgentTask(
            task_type=request.task_type,
            prompt=request.prompt,
            context=request.context,
            files=request.files
        )
        
        result = await coordinator.execute_task(task)
        
        return AgentResponse(
            task_id=result.task_id,
            agent_type=result.agent_type,
            response=result.response,
            success=result.success,
            error=result.error,
            metadata=result.metadata
        )
        
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/batch")
async def execute_agents_batch(requests: List[AgentRequest],
    user: TokenData = Depends(require_auth)
):
    """Execute multiple tasks in parallel"""
    try:
        coordinator = get_agent_coordinator()
        
        tasks = [
            AgentTask(
                task_type=r.task_type,
                prompt=r.prompt,
                context=r.context,
                files=r.files
            )
            for r in requests
        ]
        
        results = await coordinator.execute_parallel(tasks)
        
        return [
            AgentResponse(
                task_id=result.task_id,
                agent_type=result.agent_type,
                response=result.response,
                success=result.success,
                error=result.error,
                metadata=result.metadata
            )
            for result in results
        ]
        
    except Exception as e:
        logger.error(f"Batch execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=AgentStatsResponse)
async def get_agent_stats(user: TokenData = Depends(require_auth)):
    """Get agent system statistics"""
    try:
        coordinator = get_agent_coordinator()
        stats = coordinator.get_stats()
        
        return AgentStatsResponse(
            total_tasks=stats["total_tasks"],
            total_time=stats["total_time"],
            agents=stats["agents"]
        )
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def get_agent_types(user: TokenData = Depends(require_auth)):
    """Get available agent types"""
    return {
        "types": [
            {"name": "coding", "description": "Code writing, debugging, refactoring"},
            {"name": "chat", "description": "General conversation"},
            {"name": "vision", "description": "Image analysis, OCR"},
            {"name": "research", "description": "Search and gather information"},
            {"name": "analysis", "description": "Data analysis and insights"},
            {"name": "diffusion", "description": "Image generation"}
        ]
    }


@router.get("/health")
async def agents_health():
    """Health check for agent system"""
    return {
        "status": "healthy",
        "coordinator": "active"
    }