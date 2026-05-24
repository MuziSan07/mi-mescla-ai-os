"""
AI-OS Tunnel API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from ai_os.core.tunnels.manager import (
    get_tunnel_manager,
    TunnelManager,
    TunnelConfig,
    TunnelProvider
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tunnels", tags=["tunnels"])


class CreateTunnelRequest(BaseModel):
    """Request to create a tunnel"""
    provider: Optional[str] = None
    local_port: int = 8000
    remote_port: int = 9000
    cloudflare_token: Optional[str] = None
    tailscale_authkey: Optional[str] = None


class TunnelResponse(BaseModel):
    """Tunnel information"""
    provider: str
    url: Optional[str]
    local_port: int
    remote_port: int
    status: str


@router.post("/create", response_model=TunnelResponse)
async def create_tunnel(request: CreateTunnelRequest):
    """Create a tunnel"""
    try:
        manager = get_tunnel_manager()
        
        config = TunnelConfig(
            local_port=request.local_port,
            remote_port=request.remote_port,
            cloudflare_token=request.cloudflare_token,
            tailscale_authkey=request.tailscale_authkey
        )
        
        if request.provider:
            config.provider = TunnelProvider(request.provider)
        
        result = await manager.create_tunnel(config)
        
        return TunnelResponse(
            provider=result.provider,
            url=result.url,
            local_port=result.local_port,
            remote_port=result.remote_port,
            status=result.status
        )
        
    except Exception as e:
        logger.error(f"Tunnel creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_tunnel_status():
    """Get current tunnel status"""
    try:
        manager = get_tunnel_manager()
        return manager.get_info()
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/failover")
async def trigger_failover():
    """Manually trigger failover to another provider"""
    try:
        manager = get_tunnel_manager()
        result = await manager.failover()
        
        return TunnelResponse(
            provider=result.provider,
            url=result.url,
            local_port=result.local_port,
            remote_port=result.remote_port,
            status=result.status
        )
        
    except Exception as e:
        logger.error(f"Failover error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/close")
async def close_tunnel():
    """Close the active tunnel"""
    try:
        manager = get_tunnel_manager()
        await manager.close()
        
        return {"message": "Tunnel closed"}
        
    except Exception as e:
        logger.error(f"Close error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def tunnel_health():
    """Tunnel service health check"""
    return {"status": "healthy"}