"""
AI-OS Conductor (Phase 3) — the agent that manages agents.

Takes a natural-language goal, uses an LLM to break it into steps, delegates each
step to a specialist agent (developer / researcher / analyst / writer), feeds each
step the results of the ones before it, and synthesizes a final answer — the same
"one brain assigns work to many" pattern Claude Code uses.

Everything runs through the hybrid gateway, so it works fully local (Ollama) and
uses free cloud only if keys are present.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from ai_os.core.router.api_gateway import get_unified_gateway
from ai_os.core.orchestrator.agent_mesh import get_agent_coordinator, AgentTask

logger = logging.getLogger(__name__)

# Specialist -> the task_type keyword the AgentCoordinator routes on.
SPECIALIST_ROUTING = {
    "developer": "code",       # -> CodingAgent
    "researcher": "research",  # -> ResearchAgent
    "analyst": "analyze",      # -> AnalysisAgent
    "writer": "write",         # -> ChatAgent (writing/prose)
    "general": "chat",         # -> ChatAgent
}
VALID_SPECIALISTS = list(SPECIALIST_ROUTING.keys())

PLAN_SYSTEM_PROMPT = (
    "You are the Conductor of a team of AI agents. Break the user's goal into a "
    "short ordered list of steps (1-5). Assign each step to ONE specialist from: "
    + ", ".join(VALID_SPECIALISTS) + ". Keep it minimal — a simple request is ONE "
    "step. Respond with ONLY valid JSON, no prose, in exactly this shape:\n"
    '{"steps":[{"specialist":"researcher","instruction":"..."}]}'
)

SYNTH_SYSTEM_PROMPT = (
    "You are the Conductor. Using the results your agents produced, write the final "
    "answer to the user's goal. Be clear and concise; natural spoken style; no "
    "mention of 'steps' or 'agents'."
)

MAX_STEPS = 5
CONTEXT_CHARS = 600  # how much of each step's output to carry forward


@dataclass
class ConductorStep:
    specialist: str
    instruction: str
    output: str = ""
    agent_used: str = ""
    success: bool = False


@dataclass
class ConductorResult:
    goal: str
    steps: List[ConductorStep] = field(default_factory=list)
    answer: str = ""
    single_step: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "answer": self.answer,
            "single_step": self.single_step,
            "steps": [
                {
                    "specialist": s.specialist,
                    "instruction": s.instruction,
                    "agent_used": s.agent_used,
                    "success": s.success,
                    "output": s.output,
                }
                for s in self.steps
            ],
        }


class Conductor:
    """Plans a goal, delegates steps to specialist agents, synthesizes the result."""

    def __init__(self) -> None:
        self.gateway = get_unified_gateway()
        self.coordinator = get_agent_coordinator()

    # -- planning -----------------------------------------------------------
    async def _plan(self, goal: str, model: str) -> List[ConductorStep]:
        try:
            result = await self.gateway.chat(
                model=model,
                messages=[
                    {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": goal},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            raw = result.choices[0]["message"]["content"] if result.choices else ""
            steps = self._parse_plan(raw)
            if steps:
                return steps[:MAX_STEPS]
        except Exception as e:
            logger.warning("Planning failed, using single-step fallback: %s", e)
        # Fallback: treat the whole goal as one general step.
        return [ConductorStep(specialist="general", instruction=goal)]

    @staticmethod
    def _parse_plan(raw: str) -> List[ConductorStep]:
        """Robustly extract the steps array from a possibly-messy LLM response."""
        text = raw.strip()
        if "```" in text:  # strip code fences
            text = text.split("```")[1] if text.count("```") >= 2 else text
            text = text.replace("json", "", 1).strip()
        start = text.find("{")
        if start == -1:
            return []
        try:
            # Decode only the first complete JSON object (models sometimes append
            # extra text/blocks after it, which json.loads would reject).
            data, _end = json.JSONDecoder().raw_decode(text[start:])
        except Exception:
            return []
        steps = []
        for item in data.get("steps", []):
            spec = str(item.get("specialist", "general")).lower().strip()
            if spec not in SPECIALIST_ROUTING:
                spec = "general"
            instruction = str(item.get("instruction", "")).strip()
            if instruction:
                steps.append(ConductorStep(specialist=spec, instruction=instruction))
        return steps

    # -- execution ----------------------------------------------------------
    async def run(self, goal: str, model: Optional[str] = None) -> ConductorResult:
        import os
        model = model or os.getenv("DEFAULT_LOCAL_MODEL", "llama3.2")

        steps = await self._plan(goal, model)
        logger.info("Conductor plan: %s", [(s.specialist, s.instruction[:50]) for s in steps])

        context = ""
        for step in steps:
            task_type = SPECIALIST_ROUTING.get(step.specialist, "chat")
            prompt = step.instruction
            if context:
                prompt = f"Results so far:\n{context}\n\nYour task: {step.instruction}"
            try:
                res = await self.coordinator.execute_task(
                    AgentTask(task_type=task_type, prompt=prompt)
                )
                step.output = (res.response or "").strip()
                step.agent_used = res.agent_type
                step.success = res.success
            except Exception as e:
                logger.warning("Step failed (%s): %s", step.specialist, e)
                step.output = f"(step failed: {e})"
            context += f"\n[{step.specialist}] {step.output[:CONTEXT_CHARS]}"

        # A single step needs no synthesis — its output IS the answer.
        if len(steps) == 1:
            return ConductorResult(goal=goal, steps=steps, answer=steps[0].output, single_step=True)

        answer = await self._synthesize(goal, steps, model)
        return ConductorResult(goal=goal, steps=steps, answer=answer)

    # -- synthesis ----------------------------------------------------------
    async def _synthesize(self, goal: str, steps: List[ConductorStep], model: str) -> str:
        digest = "\n\n".join(
            f"{s.specialist} ({s.agent_used}):\n{s.output[:CONTEXT_CHARS]}" for s in steps
        )
        try:
            result = await self.gateway.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYNTH_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Goal: {goal}\n\nAgent results:\n{digest}"},
                ],
                temperature=0.5,
                max_tokens=400,
            )
            if result.choices:
                return (result.choices[0]["message"]["content"] or "").strip()
        except Exception as e:
            logger.warning("Synthesis failed: %s", e)
        # Fallback: concatenate the step outputs.
        return "\n\n".join(s.output for s in steps if s.output)


_conductor: Optional[Conductor] = None


def get_conductor() -> Conductor:
    """Get the Conductor singleton."""
    global _conductor
    if _conductor is None:
        _conductor = Conductor()
    return _conductor
