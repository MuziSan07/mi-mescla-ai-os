"""AI Operating System - Chat API Route"""

import httpx
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from datetime import datetime

from ai_os.models.schemas import ChatRequest, ChatResponse, ChatMessage
from ai_os.core.router.intelligent_router import get_intelligent_router
from ai_os.core.router.model_pool import get_model_pool
from ai_os.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def get_router():
    """Get intelligent router — uses absolute imports only"""
    from ai_os.core.router.intelligent_router import IntelligentRouter
    return IntelligentRouter(get_model_pool())


async def _call_ollama(model: str, messages: List[Dict[str, Any]], max_tokens: int = 1024) -> str:
    """Call Ollama chat completion endpoint"""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens}
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "").strip()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message with intelligent routing.
    Routes to the best available Ollama model based on task type.
    """
    try:
        model_pool = get_model_pool()
        irouter = get_router()

        # Route to best model
        selected_model = await irouter.route_request(request)

        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]

        # Use requested model name or routed model
        model_name = request.model or selected_model.model

        try:
            content = await _call_ollama(
                model=model_name,
                messages=messages,
                max_tokens=request.max_tokens or 1024
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Ollama not reachable at {settings.OLLAMA_BASE_URL}. "
                       f"Start Ollama and pull model: ollama pull {model_name}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama error: {e.response.text}"
            )

        prompt_tokens = sum(len(m["content"].split()) for m in messages)
        completion_tokens = len(content.split())

        return ChatResponse(
            model=model_name,
            content=content,
            finish_reason="stop",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat response.
    Falls back to non-streaming for now (streaming can be added per model).
    """
    return await chat(request)
