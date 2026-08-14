"""
AI-OS Setup API (Phase 6) — first-run token wizard.

Collects OPTIONAL API keys (all skippable, free-first) and persists them to the
app's .env, applying them to the running process immediately. Nothing here is
required — with no keys the box runs fully local.

Security: only known key names (allowlist) are accepted; stored values are never
echoed back — status reports only whether each is configured.

Endpoints (mounted at /api/v1/setup):
  GET  /status   which keys are configured + what's usable now
  POST /save      {values:{NAME:secret}} -> persist + activate; returns masked result
"""

import os
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict

from ai_os.core.router.api_gateway import get_unified_gateway

router = APIRouter(tags=["setup"])  # prefix supplied by main.py (/api/v1/setup)
logger = logging.getLogger(__name__)

# The only env names the wizard is allowed to write.
KEYS = [
    {"name": "GROQ_API_KEY",       "label": "Groq",           "free": True,  "url": "https://console.groq.com",              "unlocks": "Fast free cloud inference"},
    {"name": "GOOGLE_API_KEY",     "label": "Google Gemini",  "free": True,  "url": "https://aistudio.google.com",           "unlocks": "Free cloud LLM + vision"},
    {"name": "HUGGING_FACE_TOKEN", "label": "HuggingFace",     "free": True,  "url": "https://huggingface.co/settings/tokens","unlocks": "HF models + inference"},
    {"name": "OPENROUTER_API_KEY", "label": "OpenRouter",      "free": True,  "url": "https://openrouter.ai",                 "unlocks": "Many models, some free"},
    {"name": "GITHUB_TOKEN",       "label": "GitHub",          "free": True,  "url": "https://github.com/settings/tokens",    "unlocks": "Repo read/write, code research"},
    {"name": "OPENAI_API_KEY",     "label": "OpenAI",          "free": False, "url": "https://platform.openai.com",           "unlocks": "Top-tier cloud models"},
    {"name": "ANTHROPIC_API_KEY",  "label": "Anthropic",       "free": False, "url": "https://console.anthropic.com",         "unlocks": "Claude models"},
]
_ALLOWED = {k["name"] for k in KEYS}


class SaveRequest(BaseModel):
    values: Dict[str, str]


def _env_path() -> str:
    override = os.getenv("AIOS_ENV_FILE")
    if override:
        return override
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    return os.path.join(repo_root, ".env")


def _write_env(updates: Dict[str, str]) -> None:
    """Update or append KEY=value lines in .env, preserving everything else."""
    path = _env_path()
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    for key, val in remaining.items():
        lines.append(f"{key}={val}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


@router.get("/status")
async def setup_status():
    keys = [
        {**k, "configured": bool(os.getenv(k["name"]))}
        for k in KEYS
    ]
    gw = get_unified_gateway()
    usable = [n for n, s in gw.provider_status().items() if s["available"]]
    return {
        "keys": keys,
        "usable_providers": usable,
        "mode": "hybrid" if any(gw.provider_status()[p]["available"] and
                                gw.provider_status()[p]["type"] == "cloud"
                                for p in gw.provider_status()) else "local-only",
        "note": "All keys are optional. With none set, the box runs fully local.",
    }


@router.post("/save")
async def setup_save(req: SaveRequest):
    """Persist provided keys (allowlisted) and activate them immediately."""
    updates = {}
    for name, value in req.values.items():
        if name not in _ALLOWED:
            raise HTTPException(400, f"Unknown key: {name}")
        value = (value or "").strip()
        if value:  # ignore blanks (user left it empty = skip)
            updates[name] = value

    if updates:
        try:
            _write_env(updates)
        except Exception as e:
            logger.exception("Failed to write .env")
            raise HTTPException(500, f"Could not save: {e}")
        for name, value in updates.items():
            os.environ[name] = value  # activate for the running process

    gw = get_unified_gateway()
    return {
        "saved": sorted(updates.keys()),
        "usable_providers": [n for n, s in gw.provider_status().items() if s["available"]],
    }
