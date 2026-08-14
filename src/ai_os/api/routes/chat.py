"""AI Operating System - Chat API Route"""

import os
import logging
from fastapi import APIRouter, HTTPException

from ai_os.models.schemas import ChatRequest, ChatResponse
from ai_os.core.router.api_gateway import get_unified_gateway

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message with hybrid provider routing.

    Uses the unified gateway: the requested model first, then its fallback
    chain (skipping providers without credentials), ending at local Ollama.
    """
    gateway = get_unified_gateway()

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    model_name = request.model or os.getenv("DEFAULT_LOCAL_MODEL", "llama3.2")

    try:
        result = await gateway.chat(
            model=model_name,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens or 1024,
        )
    except Exception as e:
        # Every provider failed or none is configured — surface a clear 503.
        logger.warning("Chat failed across all providers: %s", e)
        raise HTTPException(status_code=503, detail=str(e))

    content = ""
    if result.choices:
        content = result.choices[0].get("message", {}).get("content", "") or ""
    content = content.strip()

    prompt_tokens = sum(len(m["content"].split()) for m in messages)
    completion_tokens = len(content.split())

    return ChatResponse(
        model=result.model,
        content=content,
        finish_reason="stop",
        usage=result.usage or {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat response.
    Falls back to non-streaming for now (streaming can be added per model).
    """
    return await chat(request)
