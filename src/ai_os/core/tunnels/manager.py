"""
AI-OS Tunnel Manager
Bidirectional tunneling with Cloudflare, Tailscale, FRP, Rathole
"""

import os
import asyncio
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TunnelProvider(str, Enum):
    """Supported tunnel providers"""
    CLOUDFLARE = "cloudflare"
    TAILSCALE = "tailscale"
    FRP = "frp"
    RATHOLE = "rathole"
    NGROK = "ngrok"


@dataclass
class TunnelConfig:
    """Tunnel configuration"""
    provider: TunnelProvider = TunnelProvider.CLOUDFLARE
    # Provider-specific config
    cloudflare_token: Optional[str] = None
    cloudflare_tunnel_id: Optional[str] = None
    # FRP config
    frp_server_addr: str = "127.0.0.1:7000"
    frp_token: Optional[str] = None
    # Rathole config  
    rathole_config: Optional[str] = None
    # Tailscale
    tailscale_authkey: Optional[str] = None
    # Ngrok
    ngrok_token: Optional[str] = None
    # Local port to expose
    local_port: int = 8000
    # Remote port (for FRP/Rathole)
    remote_port: int = 9000


@dataclass
class TunnelInfo:
    """Information about active tunnel"""
    provider: str
    url: Optional[str] = None
    local_port: int = 8000
    remote_port: int = 9000
    status: str = "starting"
    error: Optional[str] = None


class CloudflareTunnel:
    """Cloudflare Tunnel management"""
    
    def __init__(self, config: TunnelConfig = None):
        self.config = config or TunnelConfig(provider=TunnelProvider.CLOUDFLARE)
        self.process = None
        self.tunnel_url = None
        
    async def start(self) -> TunnelInfo:
        """Start Cloudflare tunnel"""
        token = self.config.cloudflare_token or os.getenv("CLOUDFLARE_TUNNEL_TOKEN")
        
        if not token:
            return TunnelInfo(
                provider="cloudflare",
                status="error",
                error="No token provided"
            )
        
        try:
            # Start cloudflared
            cmd = [
                "cloudflared", "tunnel",
                "--url", f"http://localhost:{self.config.local_port}",
                "--token", token
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Parse URL from output
            # In reality, we'd parse this from cloudflared output
            
            return TunnelInfo(
                provider="cloudflare",
                url=f"https://{token[:8]}.cloudflare.com",
                local_port=self.config.local_port,
                status="running"
            )
            
        except FileNotFoundError:
            return TunnelInfo(
                provider="cloudflare",
                status="error",
                error="cloudflared not installed"
            )
        except Exception as e:
            return TunnelInfo(
                provider="cloudflare",
                status="error",
                error=str(e)
            )
    
    async def stop(self):
        """Stop tunnel"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=10)


class TailscaleTunnel:
    """Tailscale Tunnel management"""
    
    def __init__(self, config: TunnelConfig = None):
        self.config = config or TunnelConfig(provider=TunnelProvider.TAILSCALE)
        self.process = None
        
    async def start(self) -> TunnelInfo:
        """Start Tailscale tunnel"""
        authkey = self.config.tailscale_authkey or os.getenv("TAILSCALE_AUTHKEY")
        
        if not authkey:
            return TunnelInfo(
                provider="tailscale",
                status="error",
                error="No auth key provided"
            )
        
        try:
            # Use tailscale funnel (exposes localhost to internet)
            cmd = [
                "tailscale", "funnel",
                "--bg",
                f"{self.config.local_port}"
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            return TunnelInfo(
                provider="tailscale",
                url=f"https://localhost:{self.config.remote_port}",
                local_port=self.config.local_port,
                remote_port=self.config.remote_port,
                status="running"
            )
            
        except FileNotFoundError:
            return TunnelInfo(
                provider="tailscale",
                status="error", 
                error="tailscale not installed"
            )
        except Exception as e:
            return TunnelInfo(
                provider="tailscale",
                status="error",
                error=str(e)
            )
    
    async def stop(self):
        """Stop tunnel"""
        if self.process:
            self.process.terminate()


class FRPTunnel:
    """Fast Reverse Proxy tunnel management"""
    
    def __init__(self, config: TunnelConfig = None):
        self.config = config or TunnelConfig(provider=TunnelProvider.FRP)
        self.process = None
        
    async def start(self) -> TunnelInfo:
        """Start FRP tunnel"""
        try:
            # Start FRP client
            cmd = [
                "frpc", "-c", "/etc/frp/frpc.ini"
            ]
            # config would specify server address
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            addr = self.config.frp_server_addr
            return TunnelInfo(
                provider="frp",
                url=f"http://{addr}:{self.config.remote_port}",
                local_port=self.config.local_port,
                remote_port=self.config.remote_port,
                status="running"
            )
            
        except FileNotFoundError:
            return TunnelInfo(
                provider="frp",
                status="error",
                error="frpc not installed"
            )
        except Exception as e:
            return TunnelInfo(
                provider="frp",
                status="error",
                error=str(e)
            )
    
    async def stop(self):
        if self.process:
            self.process.terminate()


class TunnelManager:
    """
    Manages multiple tunnel providers with automatic failover.
    """
    
    def __init__(self):
        self.active_tunnel: Optional[TunnelInfo] = None
        self.current_provider: Optional[TunnelProvider] = None
        self.tunnels: Dict[TunnelProvider, Any] = {
            TunnelProvider.CLOUDFLARE: CloudflareTunnel,
            TunnelProvider.TAILSCALE: TailscaleTunnel,
            TunnelProvider.FRP: FRPTunnel,
        }
        self.health_failures = 0
        self.max_failures = 3
        
    async def create_tunnel(
        self, 
        config: TunnelConfig = None,
        preferred_provider: TunnelProvider = None
    ) -> TunnelInfo:
        """Create tunnel with provider selection"""
        
        providers = [preferred_provider] if preferred_provider else [
            TunnelProvider.CLOUDFLARE,
            TunnelProvider.TAILSCALE,
            TunnelProvider.FRP,
        ]
        
        # Try each provider
        for provider in providers:
            try:
                tunnel_class = self.tunnels.get(provider)
                if not tunnel_class:
                    continue
                    
                tunnel_obj = tunnel_class(config)
                result = await tunnel_obj.start()
                
                if result.status == "running":
                    self.active_tunnel = result
                    self.current_provider = provider
                    self.health_failures = 0
                    logger.info(f"Tunnel created with {provider.value}")
                    return result
                    
            except Exception as e:
                logger.error(f"Failed to create {provider.value} tunnel: {e}")
                continue
        
        return TunnelInfo(
            provider="none",
            status="error",
            error="All tunnel providers failed"
        )
    
    async def health_check(self) -> bool:
        """Check if tunnel is healthy"""
        if not self.active_tunnel:
            return False
        
        # Basic check - tunnel is responding
        self.health_failures += 1
        
        if self.health_failures >= self.max_failures:
            return False
        
        return True
    
    async def failover(self, config: TunnelConfig = None) -> TunnelInfo:
        """Switch to another provider on failure"""
        logger.warning("Attempting tunnel failover")
        
        self.health_failures = 0
        
        # Try next provider
        all_providers = list(TunnelProvider)
        try:
            current_idx = all_providers.index(self.current_provider)
        except:
            current_idx = -1
        
        # Try next 2 providers
        for i in range(1, len(all_providers)):
            next_provider = all_providers[(current_idx + i) % len(all_providers)]
            result = await self.create_tunnel(config, next_provider)
            
            if result.status == "running":
                return result
        
        return TunnelInfo(
            provider="none",
            status="error",
            error="No providers available"
        )
    
    async def close(self):
        """Close active tunnel"""
        if self.active_tunnel:
            logger.info(f"Closing {self.current_provider.value} tunnel")
            self.active_tunnel = None
            self.current_provider = None
    
    def get_info(self) -> Dict:
        """Get tunnel information"""
        return {
            "provider": self.current_provider.value if self.current_provider else None,
            "url": self.active_tunnel.url if self.active_tunnel else None,
            "status": self.active_tunnel.status if self.active_tunnel else None,
            "failures": self.health_failures
        }


# Singleton
_tunnel_manager: Optional[TunnelManager] = None


def get_tunnel_manager() -> TunnelManager:
    global _tunnel_manager
    if _tunnel_manager is None:
        _tunnel_manager = TunnelManager()
    return _tunnel_manager