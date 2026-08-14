"""
Optional OpenHands backend for the Developer agent.

OpenHands (https://github.com/All-Hands-AI/OpenHands) is a heavyweight autonomous
coding agent that runs code in a Docker sandbox. It is EXTERNAL and OPTIONAL: run
an OpenHands server yourself, then set:

    DEV_BACKEND=openhands
    OPENHANDS_URL=http://localhost:3000
    OPENHANDS_API_KEY=...        # if your instance requires one

The Developer agent will then kick off builds there instead of the built-in
generator. If no server is configured, everything falls back to the built-in
backend automatically.

NOTE: this adapter targets OpenHands' conversation API but is UNVERIFIED against a
live server in this project — confirm the endpoint for your OpenHands version.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OpenHandsClient:
    def __init__(self) -> None:
        self.url = os.getenv("OPENHANDS_URL", "").rstrip("/")
        self.api_key = os.getenv("OPENHANDS_API_KEY", "")

    def is_available(self) -> bool:
        """Configured and reachable (best-effort, short timeout)."""
        if not self.url:
            return False
        try:
            import httpx
            r = httpx.get(f"{self.url}/health", timeout=2.0)
            return r.status_code < 500
        except Exception:
            return False

    async def build(self, goal: str, project_name: Optional[str] = None):
        """Start an OpenHands conversation for the goal.

        Returns a BuildResult describing the started conversation. Actual code is
        produced inside OpenHands' own sandbox/workspace.
        """
        from ai_os.core.dev.developer import BuildResult
        import httpx

        result = BuildResult(goal=goal, backend="openhands", project_name=project_name or "")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.url}/api/conversations",
                    headers=headers,
                    json={"initial_user_msg": goal},
                )
                resp.raise_for_status()
                data = resp.json()
            cid = data.get("conversation_id") or data.get("id") or "unknown"
            result.description = f"Started an OpenHands build (conversation {cid})."
            result.run_command = f"Open {self.url} to watch it build and collect the output."
            result.verify = {"delegated": True, "conversation_id": cid}
        except Exception as e:
            logger.warning("OpenHands delegation failed: %s", e)
            result.error = (
                f"OpenHands server at {self.url} did not accept the build ({e}). "
                "Check OPENHANDS_URL / API version, or use DEV_BACKEND=builtin."
            )
        return result
