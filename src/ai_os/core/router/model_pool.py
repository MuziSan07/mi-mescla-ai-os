"""
AI Operating System - Model Pool Module

Manages the pool of available AI models with their configurations,
capabilities, and availability status.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from ai_os.models.schemas import (
    ModelType, ModelInfo, ModelConfig
)

logger = logging.getLogger(__name__)


class ModelPool:
    """
    Manages a pool of AI models with load balancing and failover
    """
    
    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._models_by_type: Dict[ModelType, List[str]] = {}
        self._lock = asyncio.Lock()
    
    async def initialize_default_models(self):
        """Initialize with default model configurations"""
        defaults = [
            ModelConfig(
                name="codellama-local",
                model_type=ModelType.CODING,
                provider="ollama",
                model="codellama:13b",
                endpoint="http://localhost:11434",
                capabilities=["code", "refactor", "review", "complete"]
            ),
            ModelConfig(
                name="mistral-local",
                model_type=ModelType.REASONING,
                provider="ollama",
                model="mistral:7b",
                endpoint="http://localhost:11434",
                capabilities=["reasoning", "planning", "explanation"]
            ),
            ModelConfig(
                name="llava-local",
                model_type=ModelType.VISION,
                provider="ollama",
                model="llava:7b",
                endpoint="http://localhost:11434",
                capabilities=["vision", "image_understanding", "ocr"]
            ),
            ModelConfig(
                name="qwen-vl",
                model_type=ModelType.VISION,
                provider="qwen",
                model="qwen-vl-chat",
                endpoint="http://localhost:8080",
                capabilities=["vision", "ocr", "image_analysis"]
            ),
            ModelConfig(
                name="verify-model",
                model_type=ModelType.VERIFICATION,
                provider="custom",
                model="verify-model",
                endpoint="internal",
                capabilities=["verification", "testing", "linting"]
            ),
            ModelConfig(
                name="planner-model",
                model_type=ModelType.PLANNING,
                provider="custom",
                model="planner-model",
                endpoint="internal",
                capabilities=["planning", "decomposition", "scheduling"]
            ),
        ]
        
        for config in defaults:
            await self.add_model(config)
        
        logger.info(f"Initialized {len(defaults)} default models")
    
    async def add_model(self, config: ModelConfig) -> ModelInfo:
        """Add a model to the pool"""
        async with self._lock:
            model_id = f"{config.provider}-{config.model}"
            
            model = ModelInfo(
                id=model_id,
                name=config.name,
                model_type=config.model_type,
                provider=config.provider,
                model=config.model,
                endpoint=config.endpoint,
                capabilities=config.capabilities,
                is_available=True,
                usage_count=0
            )
            
            self._models[model_id] = model
            
            # Index by type
            if config.model_type not in self._models_by_type:
                self._models_by_type[config.model_type] = []
            self._models_by_type[config.model_type].append(model_id)
            
            logger.info(f"Added model: {model_id}")
            return model
    
    async def remove_model(self, model_id: str) -> bool:
        """Remove a model from the pool"""
        async with self._lock:
            if model_id not in self._models:
                return False
            
            model = self._models[model_id]
            model_type = model.model_type
            
            del self._models[model_id]
            
            if model_type in self._models_by_type:
                try:
                    self._models_by_type[model_type].remove(model_id)
                except ValueError:
                    pass
            
            logger.info(f"Removed model: {model_id}")
            return True
    
    async def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get a model by ID"""
        return self._models.get(model_id)
    
    async def list_models(
        self,
        model_type: Optional[ModelType] = None,
        available_only: bool = False
    ) -> List[ModelInfo]:
        """List models with optional filtering"""
        models = []
        
        if model_type:
            model_ids = self._models_by_type.get(model_type, [])
            for mid in model_ids:
                model = self._models.get(mid)
                if model:
                    if not available_only or model.is_available:
                        models.append(model)
        else:
            for model in self._models.values():
                if not available_only or model.is_available:
                    models.append(model)
        
        return models
    
    async def get_all_models(self) -> List[ModelInfo]:
        """Get all models"""
        return list(self._models.values())
    
    async def get_any_available(
        self,
        exclude: Optional[set] = None
    ) -> Optional[ModelInfo]:
        """Get any available model"""
        exclude = exclude or set()
        
        for model in self._models.values():
            if model.is_available and model.id not in exclude:
                return model
        
        return None
    
    async def set_availability(
        self,
        model_id: str,
        available: bool
    ) -> bool:
        """Set model availability"""
        async with self._lock:
            if model_id not in self._models:
                return False
            
            self._models[model_id].is_available = available
            logger.info(f"Model {model_id} availability: {available}")
            return True
    
    async def record_usage(self, model_id: str):
        """Record model usage"""
        async with self._lock:
            if model_id in self._models:
                self._models[model_id].usage_count += 1
                self._models[model_id].last_used = datetime.utcnow()
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health of all models"""
        total = len(self._models)
        available = sum(1 for m in self._models.values() if m.is_available)
        
        by_type = {}
        for model_type, model_ids in self._models_by_type.items():
            by_type[model_type.value] = sum(
                1 for mid in model_ids
                if self._models.get(mid) and self._models[mid].is_available
            )
        
        return {
            "total": total,
            "available": available,
            "by_type": by_type
        }


# Singleton instance
_model_pool_instance: Optional[ModelPool] = None


def get_model_pool() -> ModelPool:
    """Get the model pool singleton"""
    global _model_pool_instance
    if _model_pool_instance is None:
        _model_pool_instance = ModelPool()
    return _model_pool_instance