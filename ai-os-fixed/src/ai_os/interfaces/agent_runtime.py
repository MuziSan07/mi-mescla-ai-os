"""IAgentRuntime - Agent Runtime Contract"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time


class AgentState(Enum):
    """Agent lifecycle states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class AgentConfig:
    """Agent configuration"""
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: str = ""
    max_steps: int = 100
    timeout: float = 300.0
    tools: List[str] = field(default_factory=list)
    memory_limit: int = 1024 * 1024  # 1MB


@dataclass
class AgentOutput:
    """Agent execution output"""
    agent_id: str
    state: AgentState
    result: Optional[Dict] = None
    error: Optional[str] = None
    events: List[Dict] = field(default_factory=list)
    steps_executed: int = 0


class IAgentRuntime(ABC):
    """Agent runtime contract"""
    
    @abstractmethod
    async def create_agent(self, config: AgentConfig) -> str:
        """Create agent"""
        pass
    
    @abstractmethod
    async def execute(self, agent_id: str, input: Dict) -> AgentOutput:
        """Execute agent fully"""
        pass
    
    @abstractmethod
    async def step(self, agent_id: str) -> AgentOutput:
        """Single step"""
        pass
    
    @abstractmethod
    async def get_state(self, agent_id: str) -> AgentState:
        """Get state"""
        pass
    
    @abstractmethod
    async def terminate(self, agent_id: str) -> bool:
        """Terminate agent"""
        pass
    
    @abstractmethod
    async def list_agents(self) -> List[str]:
        """List agent IDs"""
        pass
