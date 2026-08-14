"""
AI-OS Developer Agent (Phase 4) — autonomously build software from a goal.

Given a goal ("build a FastAPI todo API"), it:
  1. plans a project (file manifest + run command) via the hybrid LLM gateway,
  2. generates each file's contents,
  3. writes them into an isolated workspace (with path-safety checks),
  4. safely *verifies* generated Python by syntax-compiling it (never executes
     untrusted generated commands),
  5. returns what it built + how to run it.

Backends:
  - "builtin" (default): the generator above — fully local/free, works offline.
  - "openhands": if DEV_BACKEND=openhands and an OpenHands server is configured,
    delegate to it (see openhands_client.py). Heavy, optional, external.

Safety: files are confined to the workspace; the suggested run command is
returned for the user to run, never auto-executed.
"""

import os
import re
import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from ai_os.core.router.api_gateway import get_unified_gateway

logger = logging.getLogger(__name__)

MAX_FILES = 10

PLAN_SYSTEM = (
    "You are a senior software engineer. Design a minimal, working project for the "
    "user's goal. Respond with ONLY valid JSON, no prose:\n"
    '{"project_name":"kebab-case-name","language":"python","description":"...",'
    '"files":[{"path":"relative/path.ext","purpose":"short"}],'
    '"run_command":"how to run it"}\n'
    "Keep it to the fewest files that actually work (<=10). Use relative paths only."
)

FILE_SYSTEM = (
    "You are a senior engineer. Output ONLY the raw, complete contents of the "
    "requested file — no markdown fences, no commentary. Production-quality, "
    "consistent with the rest of the project."
)


@dataclass
class BuildResult:
    goal: str
    backend: str
    project_name: str = ""
    project_dir: str = ""
    description: str = ""
    language: str = ""
    run_command: str = ""
    files: List[str] = field(default_factory=list)
    verify: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


def _workspace_root() -> str:
    return os.getenv(
        "AIOS_WORKSPACE",
        "/opt/aios/workspace" if os.path.isdir("/opt/aios") else "workspace",
    )


def _safe_join(root: str, rel: str) -> Optional[str]:
    """Join rel under root, rejecting absolute paths or traversal."""
    rel = rel.strip().lstrip("/\\")
    if not rel or os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
        return None
    full = os.path.normpath(os.path.join(root, rel))
    if os.path.commonpath([os.path.abspath(full), os.path.abspath(root)]) != os.path.abspath(root):
        return None
    return full


def _strip_fences(text: str) -> str:
    """Remove ``` fences a model may wrap file contents in."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", t)
        if t.endswith("```"):
            t = t[: t.rfind("```")]
    return t.rstrip() + "\n"


class DeveloperAgent:
    """Autonomous project builder."""

    def __init__(self) -> None:
        self.gateway = get_unified_gateway()
        self.backend = os.getenv("DEV_BACKEND", "builtin").lower()

    def status(self) -> Dict[str, Any]:
        from ai_os.core.dev.openhands_client import OpenHandsClient
        oh = OpenHandsClient()
        return {
            "backend": self.backend,
            "openhands_available": oh.is_available(),
            "openhands_url": oh.url,
            "workspace": os.path.abspath(_workspace_root()),
        }

    async def build(self, goal: str, project_name: Optional[str] = None,
                    model: Optional[str] = None) -> BuildResult:
        # Optional delegation to a real OpenHands server.
        if self.backend == "openhands":
            from ai_os.core.dev.openhands_client import OpenHandsClient
            oh = OpenHandsClient()
            if oh.is_available():
                return await oh.build(goal, project_name=project_name)
            logger.warning("DEV_BACKEND=openhands but no server reachable — using builtin.")

        model = model or os.getenv("DEFAULT_LOCAL_MODEL", "llama3.2")
        result = BuildResult(goal=goal, backend="builtin")

        spec = await self._plan(goal, model)
        if not spec.get("files"):
            result.error = "Could not produce a project plan."
            return result

        result.project_name = project_name or spec.get("project_name") or "project"
        result.description = spec.get("description", "")
        result.language = spec.get("language", "")
        result.run_command = spec.get("run_command", "")

        root = _workspace_root()
        proj_dir = _safe_join(root, result.project_name)
        if not proj_dir:
            result.error = "Invalid project name."
            return result
        os.makedirs(proj_dir, exist_ok=True)
        result.project_dir = os.path.abspath(proj_dir)

        for f in spec["files"][:MAX_FILES]:
            rel = f.get("path", "")
            dest = _safe_join(proj_dir, rel)
            if not dest:
                logger.warning("Skipping unsafe path: %s", rel)
                continue
            content = await self._gen_file(goal, spec, rel, f.get("purpose", ""), model)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(content)
            result.files.append(rel)

        # README with run instructions.
        self._write_readme(proj_dir, result)
        result.files.append("README.md")

        # Safe verify: syntax-check generated Python (never runs it).
        result.verify = self._verify_python(proj_dir, result.files)
        return result

    # -- steps --------------------------------------------------------------
    async def _plan(self, goal: str, model: str) -> Dict[str, Any]:
        try:
            r = await self.gateway.chat(
                model=model,
                messages=[{"role": "system", "content": PLAN_SYSTEM},
                          {"role": "user", "content": goal}],
                temperature=0.2, max_tokens=700,
            )
            raw = r.choices[0]["message"]["content"] if r.choices else ""
            s = raw.find("{")
            if s == -1:
                return {}
            # Decode only the FIRST complete JSON object; models often append extra
            # blocks (e.g. per-file content) after the plan, which json.loads rejects.
            obj, _end = json.JSONDecoder().raw_decode(raw[s:])
            return obj
        except Exception as ex:
            logger.warning("Dev planning failed: %s", ex)
            return {}

    async def _gen_file(self, goal: str, spec: Dict, path: str, purpose: str, model: str) -> str:
        prompt = (
            f"Project goal: {goal}\n"
            f"Project: {spec.get('project_name')} — {spec.get('description')}\n"
            f"All files: {[f.get('path') for f in spec.get('files', [])]}\n\n"
            f"Write the complete contents of: {path}  ({purpose})"
        )
        try:
            r = await self.gateway.chat(
                model=model,
                messages=[{"role": "system", "content": FILE_SYSTEM},
                          {"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=1500,
            )
            raw = r.choices[0]["message"]["content"] if r.choices else ""
            return _strip_fences(raw)
        except Exception as ex:
            return f"# generation failed for {path}: {ex}\n"

    def _write_readme(self, proj_dir: str, r: BuildResult) -> None:
        with open(os.path.join(proj_dir, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(
                f"# {r.project_name}\n\n{r.description}\n\n"
                f"_Generated by AI-OS Developer agent from the goal:_\n> {r.goal}\n\n"
                f"## Run\n```\n{r.run_command or 'see files'}\n```\n\n"
                f"## Files\n" + "".join(f"- `{p}`\n" for p in r.files) + "\n"
                "> Review generated code before running it.\n"
            )

    def _verify_python(self, proj_dir: str, files: List[str]) -> Dict[str, Any]:
        """Syntax-compile generated .py files. Does NOT execute them."""
        py = [f for f in files if f.endswith(".py")]
        if not py:
            return {"python_files": 0, "ok": True, "checked": []}
        checked, all_ok = [], True
        for rel in py:
            full = _safe_join(proj_dir, rel)
            if not full or not os.path.exists(full):
                continue
            proc = subprocess.run(
                ["python", "-m", "py_compile", full], capture_output=True, text=True
            )
            ok = proc.returncode == 0
            all_ok = all_ok and ok
            checked.append({"file": rel, "compiles": ok,
                            "error": (proc.stderr.strip()[:200] or None) if not ok else None})
        return {"python_files": len(py), "ok": all_ok, "checked": checked}


_developer: Optional[DeveloperAgent] = None


def get_developer() -> DeveloperAgent:
    global _developer
    if _developer is None:
        _developer = DeveloperAgent()
    return _developer
