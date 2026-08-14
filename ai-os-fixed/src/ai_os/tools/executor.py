"""ToolExecutor - Real execution engine"""

import asyncio
import logging
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool execution categories"""
    TERMINAL = "terminal"
    FILE = "file"
    HTTP = "http"
    COMPUTE = "compute"


@dataclass
class ToolResult:
    """Tool execution result"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0


class ToolExecutor:
    """
    Real tool executor with execution.
    
    Implements execution semantics from EXECUTION_SEMANTICS.md:
    - Timeout enforcement
    - Result wrapping
    - Async execution
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._register_default_tools()
        logger.info("ToolExecutor initialized")
    
    def _register_default_tools(self):
        """Register built-in tools"""
        
        async def echo_tool(args: Dict) -> ToolResult:
            """Echo tool - returns input"""
            return ToolResult(
                success=True,
                output=args.get("message", "no message")
            )
        
        async def execute_shell(args: Dict) -> ToolResult:
            """Shell command executor"""
            cmd = args.get("command", "")
            if not cmd:
                return ToolResult(success=False, error="No command provided")
            
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=args.get("timeout", 30)
                )
                return ToolResult(
                    success=proc.returncode == 0,
                    output=stdout.decode() if stdout else "",
                    error=stderr.decode() if stderr else None
                )
            except asyncio.TimeoutError:
                return ToolResult(success=False, error="Command timeout")
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        
        async def http_request(args: Dict) -> ToolResult:
            """HTTP request tool (simplified)"""
            import httpx
            method = args.get("method", "GET")
            url = args.get("url", "")
            
            if not url:
                return ToolResult(success=False, error="No URL provided")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(method, url, timeout=30)
                    return ToolResult(
                        success=response.status_code < 400,
                        output={"status": response.status_code, "body": response.text[:1000]}
                    )
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        
        # Register tools
        self._tools["echo"] = echo_tool
        self._tools["shell"] = execute_shell
        self._tools["http"] = http_request
        
        logger.info(f"Registered {len(self._tools)} tools: {list(self._tools.keys())}")
    
    async def execute(self, tool_name: str, args: Dict) -> ToolResult:
        """Execute a tool by name"""
        import time
        start = time.time()
        
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
                duration_ms=0
            )
        
        try:
            result = await tool(args)
            duration = (time.time() - start) * 1000
            return ToolResult(
                success=result.success,
                output=result.output,
                error=result.error,
                duration_ms=duration
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )
    
    def list_tools(self):
        """List available tools"""
        return list(self._tools.keys())


# Singleton
_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get tool executor singleton"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
