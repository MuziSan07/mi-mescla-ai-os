"""
AI-OS Agent Mesh - Specialized Agents Coordination System
Each agent specializes in different tasks: coding, chat, vision, research, analysis, diffusion
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ai_os.core.router.api_gateway import get_unified_gateway

logger = logging.getLogger(__name__)


class AgentSpecialization(str, Enum):
    """Types of agent specializations"""
    CODING = "coding"
    CHAT = "chat"
    VISION = "vision"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    DIFFUSION = "diffusion"
    PLANNING = "planning"
    TTS = "tts"
    STT = "stt"


@dataclass
class AgentCapabilities:
    """Agent capabilities"""
    specialized_tasks: List[str] = field(default_factory=list)
    max_tokens: int = 8192
    supports_stream: bool = True
    supports_vision: bool = False
    supports_tools: bool = True
    model_preference: str = "gpt-4"


@dataclass
class AgentTask:
    """Task to execute"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: str = ""
    prompt: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    tools: List[Callable] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))


@dataclass
class AgentResult:
    """Result from agent execution"""
    task_id: str
    agent_type: str
    response: str
    success: bool
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class BaseAgent:
    """Base class for specialized agents"""
    
    def __init__(
        self,
        agent_type: AgentSpecialization,
        capabilities: AgentCapabilities
    ):
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.task_count = 0
        self.success_count = 0
        self.fail_count = 0
        
    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task - override in subclass"""
        raise NotImplementedError
    
    async def can_handle(self, task: AgentTask) -> bool:
        """Check if this agent can handle the task"""
        return task.task_type in self.capabilities.specialized_tasks
    
    def get_stats(self) -> Dict:
        """Get agent statistics"""
        return {
            "type": self.agent_type.value,
            "tasks_processed": self.task_count,
            "success": self.success_count,
            "failed": self.fail_count,
        }


class CodingAgent(BaseAgent):
    """Agent specialized in coding tasks"""
    
    def __init__(self):
        caps = AgentCapabilities(
            specialized_tasks=["code", "debug", "refactor", "review", "explain", "test", "fix"],
            supports_tools=True,
            model_preference="gpt-4"
        )
        super().__init__(AgentSpecialization.CODING, caps)
        
    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute coding task"""
        start = datetime.now()
        self.task_count += 1
        
        gateway = get_unified_gateway()
        
        # Build coding-specific prompt
        prompt = self._build_coding_prompt(task)
        
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await gateway.chat(
                model=self.capabilities.model_preference,
                messages=messages,
                temperature=0.2,
                max_tokens=self.capabilities.max_tokens
            )
            
            response = result.choices[0].get("message", {}).get("content", "") if result.choices else ""
            self.success_count += 1
            
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response=response,
                success=True,
                metadata={"model": result.model, "provider": result.provider},
                execution_time=(datetime.now() - start).total_seconds()
            )
        except Exception as e:
            self.fail_count += 1
            logger.error(f"Coding agent error: {e}")
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start).total_seconds()
            )
    
    def _get_system_prompt(self) -> str:
        return """You are an expert coding assistant. You specialize in writing, debugging, refactoring, and explaining code across multiple programming languages."""
    
    def _build_coding_prompt(self, task: AgentTask) -> str:
        prompt = task.prompt
        
        if task.task_type == "debug":
            prompt = f"Debug this code and explain the issue:\n\n{task.prompt}"
        elif task.task_type == "refactor":
            prompt = f"Refactor this code to be cleaner and more efficient:\n\n{task.prompt}"
        elif task.task_type == "explain":
            prompt = f"Explain this code in detail:\n\n{task.prompt}"
        elif task.task_type == "test":
            prompt = f"Write unit tests for this code:\n\n{task.prompt}"
        elif task.task_type == "fix":
            prompt = f"Fix the bugs in this code:\n\n{task.prompt}"
        
        return prompt


class ChatAgent(BaseAgent):
    """General conversational agent"""
    
    def __init__(self):
        caps = AgentCapabilities(
            specialized_tasks=["conversation", "general", "creative", "summary"],
            supports_tools=True,
            model_preference="gpt-3.5-turbo"
        )
        super().__init__(AgentSpecialization.CHAT, caps)
    
    async def execute(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        self.task_count += 1
        
        gateway = get_unified_gateway()
        
        messages = [
            {"role": "system", "content": "You are a helpful, friendly AI assistant."},
            {"role": "user", "content": task.prompt}
        ]
        
        try:
            result = await gateway.chat(
                model=self.capabilities.model_preference,
                messages=messages,
                temperature=0.7,
                max_tokens=self.capabilities.max_tokens
            )
            
            response = result.choices[0].get("message", {}).get("content", "") if result.choices else ""
            self.success_count += 1
            
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response=response,
                success=True,
                metadata={"model": result.model},
                execution_time=(datetime.now() - start).total_seconds()
            )
        except Exception as e:
            self.fail_count += 1
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start).total_seconds()
            )


class VisionAgent(BaseAgent):
    """Agent specialized in image/vision tasks"""
    
    def __init__(self):
        caps = AgentCapabilities(
            specialized_tasks=["image", "ocr", "analyze", "describe", "extract"],
            supports_vision=True,
            model_preference="gpt-4-turbo"
        )
        super().__init__(AgentSpecialization.VISION, caps)
    
    async def execute(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        self.task_count += 1
        
        gateway = get_unified_gateway()
        
        messages = [
            {"role": "system", "content": "You are a vision expert. Analyze images carefully."},
            {"role": "user", "content": [
                {"type": "text", "text": task.prompt},
                *[
                    {"type": "image_url", "image_url": {"url": f"data:image;base64,{file}"}}
                    for file in task.files
                ]
            ]}
        ]
        
        try:
            result = await gateway.chat(
                model=self.capabilities.model_preference,
                messages=messages,
                temperature=0.3
            )
            
            response = result.choices[0].get("message", {}).get("content", "") if result.choices else ""
            self.success_count += 1
            
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response=response,
                success=True,
                metadata={"model": result.model},
                execution_time=(datetime.now() - start).total_seconds()
            )
        except Exception as e:
            self.fail_count += 1
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start).total_seconds()
            )


class ResearchAgent(BaseAgent):
    """Agent specialized in research/search"""
    
    def __init__(self):
        caps = AgentCapabilities(
            specialized_tasks=["search", "research", "gather", "summarize"],
            supports_tools=True,
            model_preference="gpt-4"
        )
        super().__init__(AgentSpecialization.RESEARCH, caps)
    
    async def execute(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        self.task_count += 1
        
        gateway = get_unified_gateway()
        
        messages = [
            {"role": "system", "content": "You are a research assistant. Gather accurate information and cite sources."},
            {"role": "user", "content": f"Research and provide detailed information about: {task.prompt}"}
        ]
        
        try:
            result = await gateway.chat(
                model=self.capabilities.model_preference,
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )
            
            response = result.choices[0].get("message", {}).get("content", "") if result.choices else ""
            self.success_count += 1
            
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response=response,
                success=True,
                metadata={"model": result.model},
                execution_time=(datetime.now() - start).total_seconds()
            )
        except Exception as e:
            self.fail_count += 1
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start).total_seconds()
            )


class AnalysisAgent(BaseAgent):
    """Agent specialized in data analysis"""
    
    def __init__(self):
        caps = AgentCapabilities(
            specialized_tasks=["analyze", "data", "stats", "visualize"],
            supports_tools=True,
            model_preference="gpt-4"
        )
        super().__init__(AgentSpecialization.ANALYSIS, caps)
    
    async def execute(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        self.task_count += 1
        
        gateway = get_unified_gateway()
        
        messages = [
            {"role": "system", "content": "You are a data analysis expert. Analyze data carefully and provide insights."},
            {"role": "user", "content": f"Analyze this data and provide insights: {task.prompt}"}
        ]
        
        try:
            result = await gateway.chat(
                model=self.capabilities.model_preference,
                messages=messages,
                temperature=0.3,
                max_tokens=4096
            )
            
            response = result.choices[0].get("message", {}).get("content", "") if result.choices else ""
            self.success_count += 1
            
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response=response,
                success=True,
                execution_time=(datetime.now() - start).total_seconds()
            )
        except Exception as e:
            self.fail_count += 1
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start).total_seconds()
            )


class DiffusionAgent(BaseAgent):
    """Agent for image generation via Stable Diffusion API"""

    def __init__(self):
        import os
        caps = AgentCapabilities(
            specialized_tasks=["generate", "edit", "create"],
            model_preference="stable-diffusion"
        )
        super().__init__(AgentSpecialization.DIFFUSION, caps)
        self._sd_url = os.getenv("SD_BASE_URL", "http://localhost:7860")

    async def execute(self, task: AgentTask) -> AgentResult:
        import httpx
        start = datetime.now()
        self.task_count += 1

        prompt = task.prompt or task.context.get("prompt", "")
        negative_prompt = task.context.get("negative_prompt", "")
        steps = task.context.get("steps", 20)
        width = task.context.get("width", 512)
        height = task.context.get("height", 512)

        if not prompt:
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error="prompt is required for image generation",
                execution_time=(datetime.now() - start).total_seconds()
            )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self._sd_url}/sdapi/v1/txt2img",
                    json={
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "steps": steps,
                        "width": width,
                        "height": height,
                    }
                )
                response.raise_for_status()
                data = response.json()
                images = data.get("images", [])
                return AgentResult(
                    task_id=task.id,
                    agent_type=self.agent_type.value,
                    response=f"Generated {len(images)} image(s) for prompt: {prompt}",
                    success=True,
                    result={"images_base64": images, "count": len(images)},
                    execution_time=(datetime.now() - start).total_seconds()
                )
        except httpx.ConnectError:
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=f"Stable Diffusion not reachable at {self._sd_url}. Start with --api flag.",
                execution_time=(datetime.now() - start).total_seconds()
            )
        except Exception as e:
            return AgentResult(
                task_id=task.id,
                agent_type=self.agent_type.value,
                response="",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start).total_seconds()
            )


class AgentCoordinator:
    """Coordinates multiple specialized agents"""
    
    def __init__(self):
        self.agents: Dict[AgentSpecialization, BaseAgent] = {
            AgentSpecialization.CODING: CodingAgent(),
            AgentSpecialization.CHAT: ChatAgent(),
            AgentSpecialization.VISION: VisionAgent(),
            AgentSpecialization.RESEARCH: ResearchAgent(),
            AgentSpecialization.ANALYSIS: AnalysisAgent(),
            AgentSpecialization.DIFFUSION: DiffusionAgent(),
        }
        self.total_tasks = 0
        self.total_time = 0.0
        
    async def route_task(self, task: AgentTask) -> BaseAgent:
        """Route task to appropriate agent"""
        task_type = task.task_type.lower()
        
        # Map task type to agent
        if any(t in task_type for t in ["code", "debug", "fix", "refactor", "implement"]):
            return self.agents[AgentSpecialization.CODING]
        elif any(t in task_type for t in ["image", "photo", "picture", "visual", "ocr"]):
            return self.agents[AgentSpecialization.VISION]
        elif any(t in task_type for t in ["search", "research", "find", "look up"]):
            return self.agents[AgentSpecialization.RESEARCH]
        elif any(t in task_type for t in ["analyze", "data", "statistic", "chart", "graph"]):
            return self.agents[AgentSpecialization.ANALYSIS]
        elif any(t in task_type for t in ["generate", "create", "draw", "design"]):
            return self.agents[AgentSpecialization.DIFFUSION]
        else:
            return self.agents[AgentSpecialization.CHAT]
    
    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute task with appropriate agent"""
        agent = await self.route_task(task)
        result = await agent.execute(task)
        
        self.total_tasks += 1
        self.total_time += result.execution_time
        
        return result
    
    async def execute_parallel(self, tasks: List[AgentTask]) -> List[AgentResult]:
        """Execute multiple tasks in parallel"""
        results = await asyncio.gather(*[self.execute_task(t) for t in tasks])
        return list(results)
    
    def get_stats(self) -> Dict:
        """Get coordinator stats"""
        return {
            "total_tasks": self.total_tasks,
            "total_time": self.total_time,
            "agents": {
                spec.value: agent.get_stats()
                for spec, agent in self.agents.items()
            }
        }


# Singleton
_coordinator: Optional[AgentCoordinator] = None


def get_agent_coordinator() -> AgentCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator()
    return _coordinator