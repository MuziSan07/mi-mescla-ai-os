"""
AI Operating System - Intelligent Router Module

Routes requests to optimal model(s) based on task requirements,
capabilities, availability, and cost optimization.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ai_os.models.schemas import (
    ModelType, ModelInfo, ChatRequest, TaskInput
)
from .model_pool import ModelPool

logger = logging.getLogger(__name__)


class TaskClassification:
    """Classifies incoming tasks to determine optimal model"""
    
    # Keywords mapped to model types
    CLASSIFICATION_KEYWORDS = {
        ModelType.CODING: [
            "code", "programming", "function", "class", "import",
            "refactor", "bug", "fix", "implement", "algorithm"
        ],
        ModelType.REASONING: [
            "reason", "logical", "analyze", "think", "explain",
            "understand", "solve", "problem", "decision"
        ],
        ModelType.VISION: [
            "image", "visual", "picture", "photo", "see",
            "detect", "recognize", "analyze image", "screenshot"
        ],
        ModelType.UI_UX: [
            "design", "ui", "interface", "button", "layout",
            "style", "modern", "improve", "component"
        ],
        ModelType.PLANNING: [
            "plan", "schedule", "organize", "break down", "task",
            "workflow", "steps", "roadmap"
        ],
    }
    
    @classmethod
    def classify(cls, input_data: Dict[str, Any], task_type: str) -> List[ModelType]:
        """Classify task and return preferred model types"""
        text = str(input_data).lower()
        scores = {}
        
        for model_type, keywords in cls.CLASSIFICATION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[model_type] = score
        
        # If explicit task type provided, prioritize that model type
        if task_type:
            try:
                explicit_type = ModelType(task_type.lower())
                scores[explicit_type] = scores.get(explicit_type, 0) + 5
            except ValueError:
                pass
        
        # Sort by score
        sorted_types = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [mt for mt, _ in sorted_types] if sorted_types else [ModelType.CODING]


class IntelligentRouter:
    """
    Routes requests to optimal model(s) using intelligent selection
    """
    
    def __init__(self, model_pool: ModelPool):
        self.model_pool = model_pool
        self.classifier = TaskClassification()
    
    async def route_request(
        self,
        request: ChatRequest,
        preferred_model: Optional[str] = None
    ) -> ModelInfo:
        """Route a chat request to optimal model"""
        
        # Build input data from request
        input_data = {
            "messages": [m.dict() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        
        # Get task type from first message if available
        task_type = "general"
        if request.messages:
            content = request.messages[0].content.lower()
            if any(kw in content for kw in ["write code", "code", "program"]):
                task_type = "coding"
            elif any(kw in content for kw in ["image", "photo", "picture", "see"]):
                task_type = "vision"
        
        # Classify task
        model_types = self.classifier.classify(input_data, task_type)
        
        # Find best model
        if preferred_model:
            model = await self.model_pool.get_model(preferred_model)
            if model and model.is_available:
                return model
        
        # Try each preferred model type
        for model_type in model_types:
            models = await self.model_pool.list_models(model_type=model_type)
            if models:
                # Return the first available model
                model = models[0]
                if model.is_available:
                    return model
        
        # Fallback to any available model
        model = await self.model_pool.get_any_available()
        if not model:
            raise RuntimeError("No available models")
        
        return model
    
    async def route_task(
        self,
        task: TaskInput,
        preferred_model: Optional[str] = None
    ) -> ModelInfo:
        """Route a task to optimal model"""
        
        # Classify task
        model_types = self.classifier.classify(
            task.input_data,
            task.task_type
        )
        
        # Find best model
        for model_type in model_types:
            models = await self.model_pool.list_models(model_type=model_type)
            if models:
                model = models[0]
                if model.is_available:
                    return model
        
        # Fallback
        model = await self.model_pool.get_any_available()
        if not model:
            raise RuntimeError("No available models")
        
        return model
    
    async def can_parallel(
        self,
        input_data: Dict[str, Any]
    ) -> bool:
        """Determine if task can be parallelized"""
        # Check for parallelizable patterns
        text = str(input_data)
        
        # Multiple independent tasks
        if "||" in text or "then" in text.lower():
            return True
        
        # Array/object with multiple items
        if isinstance(input_data, dict):
            for value in input_data.values():
                if isinstance(value, list) and len(value) > 1:
                    return True
        
        return False


class RetryRouter:
    """Handles retry logic with fallback"""
    
    def __init__(self, model_pool: ModelPool, max_retries: int = 3):
        self.model_pool = model_pool
        self.max_retries = max_retries
    
    async def execute_with_fallback(
        self,
        request: ChatRequest,
        primary_model: Optional[str] = None
    ) -> tuple:
        """Execute request with fallback on failure"""
        
        # Try primary model first
        last_error = None
        tried_models = set()
        
        # Add primary to tried if specified
        if primary_model:
            tried_models.add(primary_model)
        
        for attempt in range(self.max_retries):
            model = None
            
            if attempt == 0 and primary_model:
                model = await self.model_pool.get_model(primary_model)
            elif attempt > 0:
                model = await self.model_pool.get_any_available(exclude=tried_models)
            
            if not model:
                if attempt == 0:
                    continue
                break
            
            tried_models.add(model.name)
            
            try:
                # Execute with model
                response = await self._execute_request(model, request)
                return response, None
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Model {model.name} failed: {e}")
        
        return None, last_error
    
    async def _execute_request(
        self,
        model: ModelInfo,
        request: ChatRequest
    ) -> Any:
        """Execute request with model - override for actual implementation"""
        raise NotImplementedError()


class CostOptimizer:
    """Optimizes for cost-performance tradeoff"""
    
    def __init__(self, model_pool: ModelPool):
        self.model_pool = model_pool
    
    async def get_optimal(
        self,
        required_capabilities: List[str],
        min_quality: float = 0.5
    ) -> Optional[ModelInfo]:
        """Get optimal model considering cost and quality"""
        
        all_models = await self.model_pool.list_models()
        
        scored = []
        for model in all_models:
            if not model.is_available:
                continue
            
            # Check capabilities
            if not all(cap in model.capabilities for cap in required_capabilities):
                continue
            
            # Score based on usage (prefer less used for cost)
            usage_score = 1.0 / (model.usage_count + 1)
            scored.append((model, usage_score))
        
        if not scored:
            return None
        
        # Return least used model
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

def get_intelligent_router(model_pool=None) -> IntelligentRouter:
    """Get singleton intelligent router instance"""
    return IntelligentRouter(model_pool or ModelPool())
