"""
Conductor backend registry (Phase 6) — pluggable orchestration frameworks.

The Conductor ships with a lightweight built-in LLM planner (always available,
fully local). Heavier multi-agent frameworks can be plugged in as alternative
backends when the user installs them:

    CrewAI     — role-based agent crews
    LangGraph  — graph/state-machine agent flows
    AutoGen    — Microsoft's conversational multi-agent framework

Select one with CONDUCTOR_BACKEND=builtin|crewai|langgraph|autogen. If the chosen
framework isn't installed, the Conductor falls back to the built-in planner.

This module only *detects* availability (no heavy imports). Wiring a framework's
execution is a documented extension point in conductor.py.
"""

import os
import importlib.util
from typing import Dict, Any

FRAMEWORKS = {
    "builtin": {"module": None, "purpose": "Lightweight local LLM planner (default, no deps)"},
    "crewai": {"module": "crewai", "purpose": "Role-based agent crews"},
    "langgraph": {"module": "langgraph", "purpose": "Graph / state-machine agent flows"},
    "autogen": {"module": "autogen", "purpose": "Microsoft AutoGen multi-agent"},
}


def _installed(module: str) -> bool:
    if module is None:
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def available_backends() -> Dict[str, Dict[str, Any]]:
    """Report each framework: installed? + purpose."""
    return {
        name: {"installed": _installed(info["module"]), "purpose": info["purpose"]}
        for name, info in FRAMEWORKS.items()
    }


def selected_backend() -> str:
    """The configured backend, falling back to builtin if unavailable."""
    choice = os.getenv("CONDUCTOR_BACKEND", "builtin").lower()
    info = FRAMEWORKS.get(choice)
    if not info or not _installed(info["module"]):
        return "builtin"
    return choice
