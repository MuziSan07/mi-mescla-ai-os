"""AI Operating System - Tools API Route (secured)"""

import asyncio, logging, shlex, time, re as _re
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from ai_os.models import ToolExecutionInput, ToolResult, TokenData
from ai_os.core.security.dependencies import require_auth
from ai_os.core.security.production import InputSanitizer

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_COMMANDS = {"ls","pwd","echo","cat","head","tail","grep","find","wc","sort","uniq",
                     "date","env","df","du","ps","uname","hostname","whoami","id","uptime"}
_FS_BASE_DIR = "/app"
_ALLOWED_DOCKER_OPS = {"ps","images","stats","inspect","logs","version","info"}
_ALLOWED_GIT_OPS = {"status","log","diff","branch","remote","show","tag"}
_SAFE_ARG = _re.compile(r"^[\w\-./]+$")

TOOLS = {
    "terminal":   {"name":"terminal","description":"Run whitelisted shell commands","parameters":{"command":{"type":"string"}}},
    "filesystem": {"name":"filesystem","description":"File ops scoped to /app","parameters":{"operation":{"type":"string"},"path":{"type":"string"},"content":{"type":"string","required":False}}},
    "browser":    {"name":"browser","description":"HTTP fetch (public URLs only)","parameters":{"url":{"type":"string"},"operation":{"type":"string"}}},
    "docker":     {"name":"docker","description":"Read-only Docker status","parameters":{"operation":{"type":"string"}}},
    "git":        {"name":"git","description":"Read-only Git inspection","parameters":{"operation":{"type":"string"},"args":{"type":"array","required":False}}},
    "diffusion":  {"name":"diffusion","description":"Image generation via SD","parameters":{"prompt":{"type":"string"}}},
}

@router.get("/")
async def list_tools(user: TokenData = Depends(require_auth)):
    return [{"name": n, **i} for n, i in TOOLS.items()]

@router.get("/{tool_name}")
async def get_tool(tool_name: str, user: TokenData = Depends(require_auth)):
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"name": tool_name, **TOOLS[tool_name]}

@router.post("/execute", response_model=ToolResult)
async def execute_tool(input_data: ToolExecutionInput, user: TokenData = Depends(require_auth)):
    tool_name = input_data.tool_name
    params = input_data.parameters
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    start = time.time()
    try:
        if tool_name == "terminal":   result = await _terminal(params)
        elif tool_name == "filesystem": result = await _filesystem(params)
        elif tool_name == "browser":  result = await _browser(params)
        elif tool_name == "docker":   result = await _docker(params)
        elif tool_name == "git":      result = await _git(params)
        elif tool_name == "diffusion": result = await _diffusion(params)
        else:                         result = {"error": "not implemented"}
        return ToolResult(tool_name=tool_name, success=True, result=result, execution_time=time.time()-start)
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Tool %s error: %s", tool_name, e)
        return ToolResult(tool_name=tool_name, success=False, result=None, error=str(e), execution_time=time.time()-start)

async def _terminal(params):
    raw = params.get("command","").strip()
    if not raw: raise ValueError("Command required")
    try: parts = shlex.split(raw)
    except ValueError as e: raise ValueError(f"Invalid command syntax: {e}")
    if not parts or parts[0] not in _ALLOWED_COMMANDS:
        raise PermissionError(f"'{parts[0] if parts else ''}' not in allowlist: {sorted(_ALLOWED_COMMANDS)}")
    proc = await asyncio.create_subprocess_exec(*parts, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try: stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError: proc.kill(); raise ValueError("Command timed out")
    return {"returncode": proc.returncode, "stdout": stdout.decode("utf-8","replace"), "stderr": stderr.decode("utf-8","replace")}

async def _filesystem(params):
    s = InputSanitizer()
    op = params.get("operation","read")
    raw_path = params.get("path","")
    if not raw_path: raise ValueError("Path required")
    try: safe = s.sanitize_path(raw_path, base_dir=_FS_BASE_DIR)
    except ValueError as e: raise PermissionError(str(e))
    p = Path(safe)
    if op == "read":
        if not p.exists(): raise FileNotFoundError(f"Not found: {raw_path}")
        if p.stat().st_size > 10*1024*1024: raise ValueError("File too large (>10 MB)")
        return {"content": p.read_text(errors="replace")}
    elif op == "write":
        content = params.get("content","")
        if len(content.encode()) > 10*1024*1024: raise ValueError("Content too large (>10 MB)")
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
        return {"status":"written","path":str(p)}
    elif op == "delete":
        if p.is_file(): p.unlink()
        elif p.is_dir(): p.rmdir()
        else: raise FileNotFoundError(f"Not found: {raw_path}")
        return {"status":"deleted"}
    elif op == "list":
        if not p.is_dir(): raise NotADirectoryError(f"Not a dir: {raw_path}")
        return {"files":[{"name":f.name,"type":"dir" if f.is_dir() else "file","size":f.stat().st_size if f.is_file() else 0} for f in sorted(p.iterdir())]}
    raise ValueError(f"Unknown operation: {op}")

async def _browser(params):
    import httpx
    url = params.get("url","")
    if not url: return {"status":"error","error":"url required"}
    if not InputSanitizer.validate_url(url):
        return {"status":"error","error":"URL blocked (private/non-http)"}
    op = params.get("operation","get")
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if op in ("get","fetch","navigate"):
                r = await client.get(url)
                return {"status":"ok","url":str(r.url),"http_status":r.status_code,"body_preview":r.text[:50_000]}
            elif op == "post":
                r = await client.post(url, json=params.get("data",{}))
                return {"status":"ok","http_status":r.status_code,"body_preview":r.text[:50_000]}
            return {"status":"error","error":f"Unknown op: {op}"}
    except Exception as e:
        return {"status":"error","error":str(e)}

async def _docker(params):
    op = params.get("operation","ps")
    if op not in _ALLOWED_DOCKER_OPS:
        raise PermissionError(f"Docker op '{op}' not allowed. Allowed: {sorted(_ALLOWED_DOCKER_OPS)}")
    proc = await asyncio.create_subprocess_exec("docker", op, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try: stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError: proc.kill(); raise ValueError("Docker timed out")
    return {"returncode":proc.returncode,"output":stdout.decode("utf-8","replace")}

async def _git(params):
    op = params.get("operation","status")
    if op not in _ALLOWED_GIT_OPS:
        raise PermissionError(f"Git op '{op}' not allowed. Allowed: {sorted(_ALLOWED_GIT_OPS)}")
    safe_args = []
    for a in (params.get("args",[]) or [])[:10]:
        a = str(a)
        if not _SAFE_ARG.match(a): raise ValueError(f"Unsafe git arg: {a!r}")
        safe_args.append(a)
    proc = await asyncio.create_subprocess_exec("git", op, *safe_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try: stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError: proc.kill(); raise ValueError("Git timed out")
    return {"returncode":proc.returncode,"output":stdout.decode("utf-8","replace")}

async def _diffusion(params):
    import httpx
    prompt = params.get("prompt","")
    if not prompt: return {"status":"error","error":"prompt required"}
    endpoint = params.get("endpoint","http://localhost:7860")
    if not InputSanitizer.validate_url(endpoint):
        return {"status":"error","error":"SD endpoint URL not allowed"}
    payload = {"prompt": InputSanitizer.sanitize_html(prompt),
               "negative_prompt": InputSanitizer.sanitize_html(params.get("negative_prompt","")),
               "steps": min(int(params.get("steps",20)),150),
               "width": min(int(params.get("width",512)),1024),
               "height": min(int(params.get("height",512)),1024)}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{endpoint}/sdapi/v1/txt2img", json=payload)
            r.raise_for_status()
            images = r.json().get("images",[])
            return {"status":"ok","images_base64":images,"image_count":len(images)}
    except httpx.ConnectError:
        return {"status":"error","error":"Stable Diffusion not reachable"}
    except Exception as e:
        return {"status":"error","error":str(e)}
