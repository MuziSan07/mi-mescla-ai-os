"""AI Operating System - Tools API Route"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from ai_os.models.schemas import ToolExecutionInput, ToolResult

router = APIRouter()


# Registry of available tools
TOOLS = {
    "terminal": {
        "name": "terminal",
        "description": "Execute shell commands",
        "parameters": {
            "command": {"type": "string", "description": "Command to execute"}
        }
    },
    "filesystem": {
        "name": "filesystem",
        "description": "File system operations",
        "parameters": {
            "operation": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string", "required": False}
        }
    },
    "browser": {
        "name": "browser",
        "description": "Web browser operations",
        "parameters": {
            "url": {"type": "string"},
            "operation": {"type": "string"}
        }
    },
    "docker": {
        "name": "docker",
        "description": "Docker container management",
        "parameters": {
            "operation": {"type": "string"},
            "container": {"type": "string", "required": False}
        }
    },
    "git": {
        "name": "git",
        "description": "Version control operations",
        "parameters": {
            "operation": {"type": "string"},
            "args": {"type": "array", "required": False}
        }
    },
    "diffusion": {
        "name": "diffusion",
        "description": "Generate images with Stable Diffusion",
        "parameters": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "required": False},
            "steps": {"type": "integer", "required": False}
        }
    }
}


@router.get("/")
async def list_tools():
    """List all available tools"""
    return [{"name": name, **info} for name, info in TOOLS.items()]


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """Get tool definition"""
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return {"name": tool_name, **TOOLS[tool_name]}


@router.post("/execute", response_model=ToolResult)
async def execute_tool(input_data: ToolExecutionInput):
    """Execute a tool"""
    import time
    import asyncio
    
    tool_name = input_data.tool_name
    params = input_data.parameters
    
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    start_time = time.time()
    
    try:
        # Execute tool based on type
        if tool_name == "terminal":
            result = await _execute_terminal(params)
        elif tool_name == "filesystem":
            result = await _execute_filesystem(params)
        elif tool_name == "browser":
            result = await _execute_browser(params)
        elif tool_name == "docker":
            result = await _execute_docker(params)
        elif tool_name == "git":
            result = await _execute_git(params)
        elif tool_name == "diffusion":
            result = await _execute_diffusion(params)
        else:
            result = {"error": "Not implemented"}
        
        execution_time = time.time() - start_time
        
        return ToolResult(
            tool_name=tool_name,
            success=True,
            result=result,
            execution_time=execution_time
        )
    
    except Exception as e:
        execution_time = time.time() - start_time
        return ToolResult(
            tool_name=tool_name,
            success=False,
            result=None,
            error=str(e),
            execution_time=execution_time
        )


async def _execute_terminal(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute terminal command"""
    import subprocess
    import asyncio
    
    command = params.get("command", "")
    if not command:
        raise ValueError("Command required")
    
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode() if stdout else "",
        "stderr": stderr.decode() if stderr else ""
    }


async def _execute_filesystem(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute filesystem operation"""
    from pathlib import Path
    import os
    
    operation = params.get("operation", "read")
    path = params.get("path", "")
    
    if not path:
        raise ValueError("Path required")
    
    p = Path(path)
    
    if operation == "read":
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return {"content": p.read_text()}
    
    elif operation == "write":
        content = params.get("content", "")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"status": "written"}
    
    elif operation == "delete":
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            p.rmdir()
        return {"status": "deleted"}
    
    elif operation == "list":
        if not p.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        return {"files": [f.name for f in p.iterdir()]}
    
    return {}


async def _execute_browser(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute browser operation using httpx for basic fetch operations"""
    import httpx
    operation = params.get("operation", "get")
    url = params.get("url", "")

    if not url:
        return {"status": "error", "error": "url is required"}

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if operation in ("get", "fetch", "navigate"):
                response = await client.get(url)
                return {
                    "status": "ok",
                    "url": str(response.url),
                    "http_status": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "body_preview": response.text[:2000]
                }
            elif operation == "post":
                data = params.get("data", {})
                response = await client.post(url, json=data)
                return {
                    "status": "ok",
                    "http_status": response.status_code,
                    "body_preview": response.text[:2000]
                }
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _execute_docker(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute docker operation"""
    import subprocess
    
    operation = params.get("operation", "ps")
    
    result = subprocess.run(
        ["docker", operation] + params.get("args", []),
        capture_output=True
    )
    
    return {
        "returncode": result.returncode,
        "output": result.stdout.decode()
    }


async def _execute_git(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute git operation"""
    import subprocess
    
    operation = params.get("operation", "status")
    args = params.get("args", [])
    
    result = subprocess.run(
        ["git", operation] + args,
        capture_output=True
    )
    
    return {
        "returncode": result.returncode,
        "output": result.stdout.decode()
    }


async def _execute_diffusion(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute diffusion operation via Automatic1111 or Ollama-compatible endpoint"""
    import httpx
    prompt = params.get("prompt", "")
    negative_prompt = params.get("negative_prompt", "")
    steps = params.get("steps", 20)
    sd_endpoint = params.get("endpoint", "http://localhost:7860")

    if not prompt:
        return {"status": "error", "error": "prompt is required"}

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "width": params.get("width", 512),
        "height": params.get("height", 512),
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{sd_endpoint}/sdapi/v1/txt2img",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            images = data.get("images", [])
            return {
                "status": "ok",
                "images_base64": images,
                "image_count": len(images)
            }
    except httpx.ConnectError:
        return {
            "status": "error",
            "error": "Stable Diffusion API not reachable. Start Automatic1111 with --api flag."
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}