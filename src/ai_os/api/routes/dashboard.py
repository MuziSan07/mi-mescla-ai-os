"""
AI-OS Dashboard API
Real-time system monitoring, metrics, and control endpoints.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import logging
import psutil
import os
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections.remove(d)

manager = ConnectionManager()


class NaturalLanguageCommand(BaseModel):
    command: str
    context: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# System Metrics
# ---------------------------------------------------------------------------

async def get_system_metrics() -> Dict[str, Any]:
    """Get real-time system metrics"""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # Get container/service status
    services = await get_service_status()

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu,
            "cores": psutil.cpu_count()
        },
        "memory": {
            "percent": mem.percent,
            "used_gb": round(mem.used / (1024**3), 2),
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2)
        },
        "disk": {
            "percent": disk.percent,
            "used_gb": round(disk.used / (1024**3), 2),
            "total_gb": round(disk.total / (1024**3), 2)
        },
        "services": services
    }


async def get_service_status() -> Dict[str, Any]:
    """Check status of all AI-OS services"""
    import httpx
    services = {}

    checks = {
        "ollama": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434") + "/api/tags",
        "n8n": os.getenv("N8N_BASE_URL", "http://localhost:5678") + "/healthz",
        "comfyui": os.getenv("COMFYUI_BASE_URL", "http://localhost:8188") + "/system_stats",
    }

    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in checks.items():
            try:
                r = await client.get(url)
                services[name] = {"status": "online", "code": r.status_code}
            except Exception as e:
                services[name] = {"status": "offline", "error": str(e)[:50]}

    # Redis check
    try:
        import redis
        r = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379)
        r.ping()
        services["redis"] = {"status": "online"}
    except Exception:
        services["redis"] = {"status": "offline"}

    return services


# ---------------------------------------------------------------------------
# Dashboard Endpoints
# ---------------------------------------------------------------------------

@router.get("/dashboard/metrics")
async def get_metrics():
    """Get current system metrics"""
    return await get_system_metrics()


@router.get("/dashboard/services")
async def get_services():
    """Get status of all services"""
    return await get_service_status()


@router.websocket("/dashboard/ws")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics streaming"""
    await manager.connect(websocket)
    try:
        while True:
            metrics = await get_system_metrics()

            # Add task queue info
            try:
                from ai_os.core.orchestrator.task_queue import get_task_queue
                tq = get_task_queue()
                metrics["task_queue"] = {
                    "depth": await tq.get_queue_depth(),
                    "pending": len(tq._pending_tasks),
                    "running": len(tq._running_tasks),
                    "completed": len(tq._completed_tasks)
                }
            except Exception:
                metrics["task_queue"] = {"depth": 0}

            # Add knowledge base info
            try:
                from ai_os.core.knowledge.knowledge_base import get_knowledge_base
                kb = get_knowledge_base()
                stats = kb.get_stats()
                metrics["knowledge_base"] = {
                    "total_entries": stats.get("total_entries", 0),
                    "research_reports": stats.get("research_reports", 0)
                }
            except Exception:
                metrics["knowledge_base"] = {"total_entries": 0}

            await websocket.send_json(metrics)
            await asyncio.sleep(2)  # Update every 2 seconds
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.post("/dashboard/command")
async def natural_language_command(request: NaturalLanguageCommand):
    """
    Execute a natural language command against the AI-OS system.
    Routes commands to the appropriate subsystem.
    """
    command = request.command.lower().strip()

    # Route command to appropriate handler
    if any(w in command for w in ["search github", "find repo", "github"]):
        from ai_os.utils.github_research_agent import get_github_research_agent
        query = command.replace("search github", "").replace("find repo", "").replace("github", "").strip()
        agent = get_github_research_agent()
        report = await agent.research(query, limit=5)
        return {"action": "github_search", "query": query, "result": report.summary, "data": [r.full_name for r in report.repos]}

    elif any(w in command for w in ["search huggingface", "find model", "huggingface", "hf"]):
        from ai_os.utils.huggingface_research_agent import get_hf_research_agent
        query = command.replace("search huggingface", "").replace("find model", "").replace("huggingface", "").replace("hf", "").strip()
        agent = get_hf_research_agent()
        report = await agent.research(query, limit=5)
        return {"action": "hf_search", "query": query, "result": report.summary, "best_model": report.best_model}

    elif any(w in command for w in ["create workflow", "make workflow", "n8n"]):
        from ai_os.utils.n8n_integration import get_n8n_client
        from ai_os.utils.n8n_integration import N8NWorkflowBuilder, N8NNodeTemplates
        client = get_n8n_client()
        name = command.replace("create workflow", "").replace("make workflow", "").replace("n8n", "").strip() or "New Workflow"
        builder = N8NWorkflowBuilder(name.title())
        builder.add_node(N8NNodeTemplates.webhook("Trigger", f"/{name.lower().replace(' ', '-')}"), connect_to_last=False)
        builder.add_node(N8NNodeTemplates.code("Process", "return items;"))
        workflow = builder.build()
        result = await client.create_workflow(workflow)
        return {"action": "create_workflow", "name": name, "id": result.get("id") if result else None}

    elif any(w in command for w in ["memory", "remember", "recall"]):
        from ai_os.core.memory.short_term import get_memory_store
        from ai_os.models.schemas import MemoryRecallInput
        store = get_memory_store()
        query = command.replace("memory", "").replace("remember", "").replace("recall", "").strip()
        results = await store.recall(MemoryRecallInput(query=query, limit=5))
        return {"action": "memory_recall", "query": query, "results": [r.key for r in results]}

    elif any(w in command for w in ["chat", "ask", "tell me"]):
        import httpx
        message = command.replace("chat", "").replace("ask", "").replace("tell me", "").strip()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "http://localhost:8080/api/v1/chat",
                    json={"messages": [{"role": "user", "content": message}], "model": "tinyllama"}
                )
                if r.status_code == 200:
                    return {"action": "chat", "message": message, "response": r.json().get("content", "")}
        except Exception as e:
            return {"action": "chat", "error": str(e)}

    elif any(w in command for w in ["status", "health", "how is"]):
        metrics = await get_system_metrics()
        return {"action": "status", "metrics": metrics}

    else:
        # Send to LLM for interpretation
        return {
            "action": "unknown",
            "command": command,
            "suggestion": "Try: 'search github <query>', 'find model <query>', 'create workflow <name>', 'status'"
        }


@router.get("/dashboard/activity")
async def get_activity():
    """Get recent system activity log"""
    try:
        from ai_os.core.knowledge.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        entries = await kb.list_entries(limit=20)
        return {
            "activity": [
                {
                    "id": e.id,
                    "type": e.source,
                    "title": e.title,
                    "timestamp": e.created_at
                }
                for e in entries
            ]
        }
    except Exception as e:
        return {"activity": []}


@router.get("/dashboard/models")
async def get_available_models():
    """Get available models from Ollama"""
    import httpx
    try:
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                data = r.json()
                return {
                    "models": [
                        {
                            "name": m["name"],
                            "size_gb": round(m.get("size", 0) / (1024**3), 2),
                            "modified": m.get("modified_at", "")
                        }
                        for m in data.get("models", [])
                    ]
                }
    except Exception as e:
        return {"models": [], "error": str(e)}
