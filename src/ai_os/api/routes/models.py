"""AI Operating System - Models API Route"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime

from ai_os.models.schemas import (
    ModelInfo, ModelConfig, ModelType
)
from ai_os.core.router.model_pool import get_model_pool

router = APIRouter()


@router.get("/", response_model=List[ModelInfo])
async def list_models(model_type: Optional[str] = None):
    """List all available models"""
    model_pool = get_model_pool()
    
    mt = None
    if model_type:
        try:
            mt = ModelType(model_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid model type")
    
    return await model_pool.list_models(model_type=mt, available_only=False)


@router.get("/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str):
    """Get a specific model"""
    model_pool = get_model_pool()
    model = await model_pool.get_model(model_id)
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return model


@router.post("/")
async def add_model(config: ModelConfig):
    """Add a new model"""
    model_pool = get_model_pool()
    model = await model_pool.add_model(config)
    return model


@router.delete("/{model_id}")
async def remove_model(model_id: str):
    """Remove a model"""
    model_pool = get_model_pool()
    result = await model_pool.remove_model(model_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {"status": "removed"}


@router.post("/{model_id}/availability")
async def set_availability(model_id: str, available: bool = True):
    """Set model availability"""
    model_pool = get_model_pool()
    result = await model_pool.set_availability(model_id, available)
    
    if not result:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {"status": "updated", "available": available}