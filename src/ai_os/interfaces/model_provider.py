"""IModelProvider - Model Provider Contract"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class ModelCapability(Enum):
    TEXT = "text"
    CODE = "code"
    VISION = "vision"
    EMBEDDING = "embedding"
    SPEECH = "speech"


@dataclass
class ModelSpec:
    model_id: str
    provider: str  # openai, anthropic, ollama
    model_name: str
    capabilities: List[ModelCapability]
    max_tokens: int
    pricing: Dict[str, float] = field(default_factory=dict)


@dataclass
class ModelResponse:
    model_id: str
    output: str
    usage: Dict[str, int]
    latency_ms: float


class IModelProvider(ABC):
    @abstractmethod
    async def complete(self, spec: ModelSpec, prompt: str, **kwargs) -> ModelResponse:
        pass
    
    @abstractmethod
    async def chat(self, spec: ModelSpec, messages: List[Dict], **kwargs) -> ModelResponse:
        pass
    
    @abstractmethod
    async def embed(self, spec: ModelSpec, text: str) -> List[float]:
        pass
