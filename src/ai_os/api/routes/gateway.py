"""
AI-OS Unified Gateway API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from ai_os.core.router.api_gateway import get_unified_gateway, UnifiedAPIGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


class ChatRequest(BaseModel):
    """Chat completion request"""
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    seed: Optional[int] = None
    top_p: Optional[float] = None


class EmbedRequest(BaseModel):
    """Embedding request"""
    model: str
    texts: List[str]


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Unified chat endpoint.
    Automatically routes to the correct provider.
    """
    try:
        gateway = get_unified_gateway()
        
        result = await gateway.chat(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
            seed=request.seed,
            top_p=request.top_p
        )
        
        return {
            "id": result.id,
            "model": result.model,
            "choices": result.choices,
            "usage": result.usage,
            "provider": result.provider
        }
        
    except Exception as e:
        logger.error(f"Gateway chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed")
async def embed(request: EmbedRequest):
    """Generate embeddings"""
    try:
        gateway = get_unified_gateway()
        
        embeddings = await gateway.embed(
            model=request.model,
            texts=request.texts
        )
        
        return {"embeddings": embeddings}
        
    except Exception as e:
        logger.error(f"Gateway embed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List all available models"""
    try:
        gateway = get_unified_gateway()
        models = await gateway.list_models()
        return models
        
    except Exception as e:
        logger.error(f"List models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def list_providers():
    """List all supported providers"""
    try:
        gateway = get_unified_gateway()
        
        providers = []
        for name, config in gateway.providers.items():
            providers.append({
                "name": name,
                "base_url": config.get("base_url"),
                "supports": config.get("supports", []),
                "models": len(config.get("models", []))
            })
        
        return {"providers": providers}
        
    except Exception as e:
        logger.error(f"List providers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def gateway_health():
    """Gateway health check"""
    return {
        "status": "healthy",
        "providers": len(get_unified_gateway().providers)
    }