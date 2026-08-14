"""AI-OS Dashboard API — real-time metrics with authenticated WebSocket"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio, logging, psutil, os
from datetime import datetime

from ai_os.core.security.dependencies import require_auth, _decode_token
from ai_os.models import TokenData

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active_connections:
            try: await ws.send_json(data)
            except Exception: dead.append(ws)
        for d in dead: self.disconnect(d)

manager = ConnectionManager()


class NaturalLanguageCommand(BaseModel):
    command: str
    context: Optional[Dict[str, Any]] = None


async def _get_system_metrics() -> Dict[str, Any]:
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    services = await _get_service_status()
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {"percent": cpu, "cores": psutil.cpu_count()},
        "memory": {"percent": mem.percent, "used_gb": round(mem.used/1024**3,2),
                   "total_gb": round(mem.total/1024**3,2)},
        "disk": {"percent": disk.percent, "used_gb": round(disk.used/1024**3,2),
                 "total_gb": round(disk.total/1024**3,2)},
        "services": services,
    }

async def _get_service_status() -> Dict[str, Any]:
    import httpx
    checks = {
        "ollama": os.getenv("OLLAMA_BASE_URL","http://ollama:11434") + "/api/tags",
        "n8n": os.getenv("N8N_BASE_URL","http://localhost:5678") + "/healthz",
        "comfyui": os.getenv("COMFYUI_BASE_URL","http://localhost:8188") + "/system_stats",
    }
    services = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in checks.items():
            try: r = await client.get(url); services[name] = {"status":"online","code":r.status_code}
            except Exception: services[name] = {"status":"offline"}
    return services


@router.get("/dashboard/metrics")
async def get_metrics(user: TokenData = Depends(require_auth)):
    return await _get_system_metrics()


@router.websocket("/dashboard/ws")
async def websocket_metrics(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    """
    Authenticated WebSocket. Pass JWT as ?token=<value>.
    Connection rejected with code 1008 if token is missing or invalid.
    """
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    token_data = await _decode_token(token)
    if not token_data:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    await manager.connect(websocket)
    logger.info("Dashboard WS connected: user=%s", token_data.username)
    try:
        while True:
            await websocket.send_json(await _get_system_metrics())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("Dashboard WS error: %s", e)
        manager.disconnect(websocket)


@router.post("/dashboard/command")
async def natural_language_command(
    request: NaturalLanguageCommand, user: TokenData = Depends(require_auth)
):
    command = request.command.lower().strip()
    if any(w in command for w in ["search github","find repo","github"]):
        from ai_os.utils.github_research_agent import get_github_research_agent
        query = command.replace("search github","").replace("find repo","").replace("github","").strip()
        agent = get_github_research_agent()
        report = await agent.research(query, limit=5)
        return {"action":"github_search","query":query,"result":report.summary}
    if any(w in command for w in ["search huggingface","find model","huggingface","hf"]):
        from ai_os.utils.huggingface_research_agent import get_hf_research_agent
        query = command.replace("search huggingface","").replace("find model","").replace("huggingface","").replace("hf","").strip()
        agent = get_hf_research_agent()
        report = await agent.research(query, limit=5)
        return {"action":"hf_search","query":query,"result":report.summary}
    return {"action":"unknown","message":f"Command not recognised: {request.command!r}"}


@router.get("/dashboard/health")
async def dashboard_health():
    return {"status": "healthy"}
