"""
AI-OS Manus Desktop API Routes
File system, CLI, automation, and GPU endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["desktop"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class ListDirRequest(BaseModel):
    path: str = "/app/src"


class ReadFileRequest(BaseModel):
    path: str


class WriteFileRequest(BaseModel):
    path: str
    content: str


class DeleteRequest(BaseModel):
    path: str


class MoveRequest(BaseModel):
    src: str
    dst: str


class SearchRequest(BaseModel):
    directory: str = "/app/src"
    pattern: str = "*.py"
    content: Optional[str] = None


class CommandRequest(BaseModel):
    command: str
    cwd: str = "/app"
    timeout: float = 30.0
    env: Optional[Dict[str, str]] = None


class PythonRequest(BaseModel):
    code: str
    timeout: float = 30.0


class AutomationRequest(BaseModel):
    name: str
    steps: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# File System Endpoints
# ---------------------------------------------------------------------------

@router.get("/desktop/fs/list")
async def list_directory(path: str = "/app/src"):
    """List directory contents"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        items = fs.list_directory(path)
        return {
            "path": path,
            "count": len(items),
            "items": [
                {
                    "name": f.name,
                    "path": f.path,
                    "type": f.type,
                    "size": f.size,
                    "modified": f.modified,
                    "extension": f.extension
                }
                for f in items
            ]
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/desktop/fs/read")
async def read_file(path: str):
    """Read a file's contents"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        content = fs.read_file(path)
        return {"path": path, "content": content, "size": len(content)}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/desktop/fs/write")
async def write_file(request: WriteFileRequest):
    """Write content to a file"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        fs.write_file(request.path, request.content)
        return {"path": request.path, "written": True, "size": len(request.content)}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/desktop/fs/delete")
async def delete_file(path: str):
    """Delete a file or directory"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        fs.delete_file(path)
        return {"path": path, "deleted": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/desktop/fs/move")
async def move_file(request: MoveRequest):
    """Move or rename a file"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        fs.move_file(request.src, request.dst)
        return {"src": request.src, "dst": request.dst, "moved": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/desktop/fs/search")
async def search_files(request: SearchRequest):
    """Search for files by name pattern or content"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        results = fs.search_files(request.directory, request.pattern, request.content)
        return {
            "directory": request.directory,
            "pattern": request.pattern,
            "count": len(results),
            "files": results
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/desktop/fs/info")
async def file_info(path: str):
    """Get detailed info about a file"""
    try:
        from ai_os.utils.manus_desktop import get_fs_manager
        fs = get_fs_manager()
        info = fs.get_file_info(path)
        return {
            "name": info.name,
            "path": info.path,
            "type": info.type,
            "size": info.size,
            "modified": info.modified,
            "permissions": info.permissions,
            "extension": info.extension
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# CLI Endpoints
# ---------------------------------------------------------------------------

@router.post("/desktop/cli/execute")
async def execute_command(request: CommandRequest):
    """Execute a CLI command"""
    try:
        from ai_os.utils.manus_desktop import get_cli_executor
        cli = get_cli_executor()
        result = await cli.execute(
            request.command,
            cwd=request.cwd,
            timeout=request.timeout,
            env=request.env
        )
        return {
            "command": result.command,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
            "success": result.exit_code == 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/desktop/cli/python")
async def execute_python(request: PythonRequest):
    """Execute Python code"""
    try:
        from ai_os.utils.manus_desktop import get_cli_executor
        cli = get_cli_executor()
        result = await cli.execute_python(request.code, timeout=request.timeout)
        return {
            "exit_code": result.exit_code,
            "output": result.stdout,
            "error": result.stderr,
            "success": result.exit_code == 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/desktop/cli/processes")
async def list_processes():
    """List running processes"""
    try:
        from ai_os.utils.manus_desktop import get_cli_executor
        cli = get_cli_executor()
        processes = await cli.get_processes()
        return {
            "count": len(processes),
            "processes": [
                {
                    "pid": p.pid,
                    "name": p.name,
                    "status": p.status,
                    "cpu_percent": p.cpu_percent,
                    "memory_mb": p.memory_mb
                }
                for p in processes
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Automation Endpoints
# ---------------------------------------------------------------------------

@router.post("/desktop/automation/run")
async def run_automation(request: AutomationRequest):
    """
    Run a multi-step automation task.

    Step types:
    - shell: {"type": "shell", "command": "ls -la", "cwd": "/app"}
    - python: {"type": "python", "code": "print('hello')"}
    - write_file: {"type": "write_file", "path": "/tmp/test.txt", "content": "hello"}
    - read_file: {"type": "read_file", "path": "/tmp/test.txt"}
    - http: {"type": "http", "url": "https://api.example.com", "method": "GET"}
    - llm: {"type": "llm", "prompt": "Summarize this", "model": "tinyllama"}
    - wait: {"type": "wait", "seconds": 2}
    """
    try:
        from ai_os.utils.manus_desktop import get_automation_engine, AutomationTask
        engine = get_automation_engine()
        task = AutomationTask(name=request.name, steps=request.steps)
        result = await engine.run_task(task)
        return {
            "task_id": result.id,
            "name": result.name,
            "status": result.status,
            "steps_completed": len(result.results),
            "results": result.results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/desktop/automation/examples")
async def automation_examples():
    """Get example automation task definitions"""
    return {
        "examples": [
            {
                "name": "Check Python version and list files",
                "steps": [
                    {"type": "shell", "command": "python3 --version"},
                    {"type": "shell", "command": "ls -la /app/src/ai_os/"},
                    {"type": "python", "code": "import sys; print(f'Python {sys.version}')"}
                ]
            },
            {
                "name": "Create and write a file",
                "steps": [
                    {"type": "write_file", "path": "/tmp/aios_test.txt", "content": "Hello from AI-OS!"},
                    {"type": "shell", "command": "cat /tmp/aios_test.txt"},
                    {"type": "read_file", "path": "/tmp/aios_test.txt"}
                ]
            },
            {
                "name": "Search and analyze code",
                "steps": [
                    {"type": "shell", "command": "find /app/src -name '*.py' | wc -l"},
                    {"type": "python", "code": "import os; files = list(os.walk('/app/src')); print(f'Directories: {len(files)}')"},
                    {"type": "llm", "prompt": "What is FastAPI used for?", "model": "tinyllama"}
                ]
            }
        ]
    }


# ---------------------------------------------------------------------------
# GPU Endpoints
# ---------------------------------------------------------------------------

@router.get("/desktop/gpu")
async def get_gpu_info():
    """Get GPU information and usage"""
    try:
        from ai_os.utils.manus_desktop import get_gpu_monitor
        monitor = get_gpu_monitor()
        gpus = await monitor.get_gpu_info()
        return {"gpus": gpus, "count": len(gpus)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/desktop/health")
async def desktop_health():
    """Desktop subsystem health check"""
    import os
    return {
        "status": "online",
        "file_system": "available",
        "cli": "available",
        "automation": "available",
        "working_directory": os.getcwd(),
        "python_path": os.environ.get("PYTHONPATH", "not set")
    }
