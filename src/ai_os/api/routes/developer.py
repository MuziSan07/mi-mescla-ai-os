"""
AI-OS Developer API (Phase 4) — build software from a goal.

Endpoints (mounted at /api/v1/developer):
  GET  /status                 backend + workspace
  POST /build                  {goal, project_name?} -> scaffolds a project on disk
  GET  /projects               list built projects
  GET  /projects/{name}/files  list a project's files
  GET  /projects/{name}/file   ?path=... -> a file's contents
"""

import os
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ai_os.core.dev.developer import get_developer, _workspace_root, _safe_join

router = APIRouter(tags=["developer"])  # prefix supplied by main.py (/api/v1/developer)
logger = logging.getLogger(__name__)


class BuildRequest(BaseModel):
    goal: str
    project_name: str | None = None
    model: str | None = None


@router.get("/status")
async def developer_status():
    return get_developer().status()


@router.post("/build")
async def developer_build(request: BuildRequest):
    if not request.goal.strip():
        raise HTTPException(422, "Empty goal.")
    dev = get_developer()
    try:
        result = await dev.build(request.goal, project_name=request.project_name,
                                 model=request.model)
    except Exception as e:
        logger.exception("Developer build failed")
        raise HTTPException(500, f"Build failed: {e}")
    return result.to_dict()


@router.get("/projects")
async def list_projects():
    root = _workspace_root()
    if not os.path.isdir(root):
        return {"workspace": os.path.abspath(root), "projects": []}
    projects = sorted(
        d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))
    )
    return {"workspace": os.path.abspath(root), "projects": projects}


@router.get("/projects/{name}/files")
async def list_project_files(name: str):
    proj = _safe_join(_workspace_root(), name)
    if not proj or not os.path.isdir(proj):
        raise HTTPException(404, "Project not found.")
    files = []
    for base, _dirs, names in os.walk(proj):
        for n in names:
            files.append(os.path.relpath(os.path.join(base, n), proj).replace("\\", "/"))
    return {"project": name, "files": sorted(files)}


@router.get("/projects/{name}/file")
async def get_project_file(name: str, path: str = Query(...)):
    proj = _safe_join(_workspace_root(), name)
    if not proj:
        raise HTTPException(404, "Project not found.")
    full = _safe_join(proj, path)
    if not full or not os.path.isfile(full):
        raise HTTPException(404, "File not found.")
    with open(full, encoding="utf-8", errors="replace") as f:
        return {"project": name, "path": path, "content": f.read()}
