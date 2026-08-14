"""
AI-OS Manus Desktop Equivalent
================================
Provides desktop-like capabilities:
- File system access and management
- CLI command execution
- Process management
- Local automation
- GPU usage monitoring
- Screenshot and screen interaction
"""

import os
import asyncio
import subprocess
import shutil
import logging
import json
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Safety: restrict file access to these base paths
ALLOWED_BASE_PATHS = [
    "/app",
    "/tmp",
    "/home",
    os.path.expanduser("~")
]

MAX_OUTPUT_SIZE = 50_000  # 50KB max command output
COMMAND_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    name: str
    path: str
    type: str  # file, directory, symlink
    size: int
    modified: str
    permissions: str
    extension: str = ""


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProcessInfo:
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_mb: float
    created: str


@dataclass
class AutomationTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    results: List[Any] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# File System Manager
# ---------------------------------------------------------------------------

class FileSystemManager:
    """File system operations with safety restrictions"""

    def _is_safe_path(self, path: str) -> bool:
        """Check if path is within allowed directories"""
        abs_path = os.path.abspath(path)
        return any(abs_path.startswith(base) for base in ALLOWED_BASE_PATHS)

    def list_directory(self, path: str = "/app") -> List[FileInfo]:
        """List directory contents"""
        if not self._is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")

        items = []
        try:
            for entry in os.scandir(path):
                stat = entry.stat()
                items.append(FileInfo(
                    name=entry.name,
                    path=entry.path,
                    type="directory" if entry.is_dir() else "file",
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    permissions=oct(stat.st_mode)[-3:],
                    extension=Path(entry.name).suffix if entry.is_file() else ""
                ))
        except PermissionError:
            pass

        return sorted(items, key=lambda x: (x.type == "file", x.name.lower()))

    def read_file(self, path: str, max_bytes: int = 50_000) -> str:
        """Read a file's contents"""
        if not self._is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")

        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        if os.path.getsize(path) > max_bytes:
            with open(path, 'r', errors='replace') as f:
                return f.read(max_bytes) + f"\n... [truncated, file is {os.path.getsize(path)} bytes]"

        with open(path, 'r', errors='replace') as f:
            return f.read()

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file"""
        if not self._is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return True

    def delete_file(self, path: str) -> bool:
        """Delete a file or directory"""
        if not self._is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")

        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            raise FileNotFoundError(f"Not found: {path}")
        return True

    def create_directory(self, path: str) -> bool:
        """Create a directory"""
        if not self._is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")
        os.makedirs(path, exist_ok=True)
        return True

    def move_file(self, src: str, dst: str) -> bool:
        """Move/rename a file"""
        if not self._is_safe_path(src) or not self._is_safe_path(dst):
            raise PermissionError("Access denied")
        shutil.move(src, dst)
        return True

    def copy_file(self, src: str, dst: str) -> bool:
        """Copy a file"""
        if not self._is_safe_path(src) or not self._is_safe_path(dst):
            raise PermissionError("Access denied")
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return True

    def search_files(self, directory: str, pattern: str, content: str = None) -> List[str]:
        """Search for files by name pattern or content"""
        if not self._is_safe_path(directory):
            raise PermissionError(f"Access denied: {directory}")

        import fnmatch
        results = []
        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in files:
                if fnmatch.fnmatch(filename, pattern):
                    filepath = os.path.join(root, filename)
                    if content:
                        try:
                            with open(filepath, 'r', errors='ignore') as f:
                                if content.lower() in f.read().lower():
                                    results.append(filepath)
                        except Exception:
                            pass
                    else:
                        results.append(filepath)
            if len(results) >= 100:
                break
        return results

    def get_file_info(self, path: str) -> FileInfo:
        """Get detailed info about a file"""
        if not self._is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")

        stat = os.stat(path)
        return FileInfo(
            name=os.path.basename(path),
            path=path,
            type="directory" if os.path.isdir(path) else "file",
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            permissions=oct(stat.st_mode)[-3:],
            extension=Path(path).suffix
        )


# ---------------------------------------------------------------------------
# CLI Executor
# ---------------------------------------------------------------------------

class CLIExecutor:
    """Safe CLI command execution"""

    # Blocked dangerous commands
    BLOCKED_COMMANDS = {
        "rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:",
        "chmod -R 777 /", "chown -R", "sudo rm", "shutdown", "reboot",
        "halt", "poweroff", "init 0", "init 6"
    }

    # Allowed command prefixes in restricted mode
    SAFE_PREFIXES = {
        "ls", "cat", "echo", "pwd", "whoami", "date", "ps", "top",
        "df", "du", "find", "grep", "head", "tail", "wc", "sort",
        "python", "python3", "pip", "pip3", "git", "curl", "wget",
        "mkdir", "touch", "cp", "mv", "chmod", "chown",
        "docker", "docker-compose", "npm", "node", "yarn"
    }

    def _is_safe_command(self, command: str) -> tuple:
        """Check if command is safe to execute"""
        cmd_lower = command.lower().strip()

        for blocked in self.BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return False, f"Blocked command: {blocked}"

        return True, ""

    async def execute(
        self,
        command: str,
        cwd: str = "/app",
        timeout: float = COMMAND_TIMEOUT,
        env: Dict[str, str] = None
    ) -> CommandResult:
        """Execute a CLI command"""
        safe, reason = self._is_safe_command(command)
        if not safe:
            return CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr=f"Command blocked: {reason}",
                duration_ms=0
            )

        start = asyncio.get_event_loop().time()
        try:
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd if os.path.exists(cwd) else "/app",
                env=exec_env
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return CommandResult(
                    command=command,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    duration_ms=(asyncio.get_event_loop().time() - start) * 1000
                )

            duration = (asyncio.get_event_loop().time() - start) * 1000
            stdout_str = stdout.decode('utf-8', errors='replace')[:MAX_OUTPUT_SIZE]
            stderr_str = stderr.decode('utf-8', errors='replace')[:MAX_OUTPUT_SIZE]

            logger.info(f"Command executed: {command[:50]} (exit={process.returncode})")

            return CommandResult(
                command=command,
                exit_code=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_ms=round(duration, 2)
            )

        except Exception as e:
            return CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=(asyncio.get_event_loop().time() - start) * 1000
            )

    async def execute_python(self, code: str, timeout: float = 30.0) -> CommandResult:
        """Execute Python code"""
        tmp_file = f"/tmp/aios_script_{uuid.uuid4().hex[:8]}.py"
        try:
            with open(tmp_file, 'w') as f:
                f.write(code)
            result = await self.execute(f"python3 {tmp_file}", timeout=timeout)
            return result
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    async def get_processes(self) -> List[ProcessInfo]:
        """Get list of running processes"""
        import psutil
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                info = proc.info
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    status=info['status'],
                    cpu_percent=info['cpu_percent'] or 0.0,
                    memory_mb=round((info['memory_info'].rss if info['memory_info'] else 0) / (1024**2), 2),
                    created=datetime.fromtimestamp(info['create_time']).isoformat()
                ))
            except Exception:
                pass
        return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)[:50]


# ---------------------------------------------------------------------------
# Automation Engine
# ---------------------------------------------------------------------------

class AutomationEngine:
    """
    Run multi-step automation tasks.
    Each step can be: shell command, python code, file op, API call, LLM call.
    """

    def __init__(self):
        self.fs = FileSystemManager()
        self.cli = CLIExecutor()
        self._running_tasks: Dict[str, AutomationTask] = {}

    async def run_task(self, task: AutomationTask) -> AutomationTask:
        """Execute an automation task step by step"""
        task.status = "running"
        self._running_tasks[task.id] = task

        for i, step in enumerate(task.steps):
            step_type = step.get("type", "shell")
            logger.info(f"Task {task.id} step {i+1}/{len(task.steps)}: {step_type}")

            try:
                result = await self._execute_step(step)
                task.results.append({"step": i+1, "type": step_type, "success": True, "result": result})
            except Exception as e:
                task.results.append({"step": i+1, "type": step_type, "success": False, "error": str(e)})
                if step.get("stop_on_error", True):
                    task.status = "failed"
                    self._running_tasks.pop(task.id, None)
                    return task

        task.status = "completed"
        self._running_tasks.pop(task.id, None)
        return task

    async def _execute_step(self, step: Dict[str, Any]) -> Any:
        """Execute a single automation step"""
        step_type = step.get("type", "shell")

        if step_type == "shell":
            result = await self.cli.execute(
                step["command"],
                cwd=step.get("cwd", "/app"),
                timeout=step.get("timeout", COMMAND_TIMEOUT)
            )
            if result.exit_code != 0 and step.get("stop_on_error", True):
                raise RuntimeError(f"Command failed: {result.stderr}")
            return {"stdout": result.stdout, "exit_code": result.exit_code}

        elif step_type == "python":
            result = await self.cli.execute_python(step["code"])
            return {"output": result.stdout, "exit_code": result.exit_code}

        elif step_type == "write_file":
            self.fs.write_file(step["path"], step["content"])
            return {"written": step["path"]}

        elif step_type == "read_file":
            content = self.fs.read_file(step["path"])
            return {"content": content}

        elif step_type == "http":
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                method = step.get("method", "GET").upper()
                r = await client.request(method, step["url"], json=step.get("body"), headers=step.get("headers", {}))
                return {"status": r.status_code, "body": r.text[:5000]}

        elif step_type == "llm":
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "http://localhost:8080/api/v1/chat",
                    json={"messages": [{"role": "user", "content": step["prompt"]}], "model": step.get("model", "tinyllama")}
                )
                if r.status_code == 200:
                    return {"response": r.json().get("content", "")}
                return {"error": f"LLM call failed: {r.status_code}"}

        elif step_type == "wait":
            await asyncio.sleep(step.get("seconds", 1))
            return {"waited": step.get("seconds", 1)}

        else:
            raise ValueError(f"Unknown step type: {step_type}")

    def get_task_status(self, task_id: str) -> Optional[AutomationTask]:
        return self._running_tasks.get(task_id)


# ---------------------------------------------------------------------------
# GPU Monitor
# ---------------------------------------------------------------------------

class GPUMonitor:
    """Monitor GPU usage via nvidia-smi"""

    async def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information"""
        try:
            result = await CLIExecutor().execute(
                "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu "
                "--format=csv,noheader,nounits",
                timeout=5
            )
            if result.exit_code == 0:
                gpus = []
                for line in result.stdout.strip().split('\n'):
                    if not line.strip():
                        continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 6:
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "utilization_percent": float(parts[2]),
                            "memory_used_mb": float(parts[3]),
                            "memory_total_mb": float(parts[4]),
                            "temperature_c": float(parts[5])
                        })
                return gpus
        except Exception as e:
            logger.debug(f"nvidia-smi failed: {e}")
        return [{"error": "No GPU detected or nvidia-smi not available"}]


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_fs_manager: Optional[FileSystemManager] = None
_cli_executor: Optional[CLIExecutor] = None
_automation_engine: Optional[AutomationEngine] = None
_gpu_monitor: Optional[GPUMonitor] = None


def get_fs_manager() -> FileSystemManager:
    global _fs_manager
    if _fs_manager is None:
        _fs_manager = FileSystemManager()
    return _fs_manager


def get_cli_executor() -> CLIExecutor:
    global _cli_executor
    if _cli_executor is None:
        _cli_executor = CLIExecutor()
    return _cli_executor


def get_automation_engine() -> AutomationEngine:
    global _automation_engine
    if _automation_engine is None:
        _automation_engine = AutomationEngine()
    return _automation_engine


def get_gpu_monitor() -> GPUMonitor:
    global _gpu_monitor
    if _gpu_monitor is None:
        _gpu_monitor = GPUMonitor()
    return _gpu_monitor
