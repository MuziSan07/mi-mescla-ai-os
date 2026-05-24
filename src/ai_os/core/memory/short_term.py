"""
AI Operating System - Memory Module

Provides persistent memory with short-term, long-term, shared, and semantic memory.
Semantic search uses real vector embeddings via Ollama nomic-embed-text.
Falls back to keyword matching if Ollama embeddings are unavailable.
"""

import asyncio
import logging
import math
import os
from typing import List, Optional, Any, Dict, Tuple
from datetime import datetime
from uuid import uuid4
import json

import httpx

from ai_os.models.schemas import (
    MemoryType, MemoryItem, MemoryStoreInput, MemoryRecallInput
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

async def _get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector from Ollama. Returns None if unavailable."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text}
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding", [])
            if embedding:
                return embedding
    except Exception as e:
        logger.debug(f"Embedding unavailable ({EMBEDDING_MODEL}): {e}")
    return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _keyword_score(query: str, memory: MemoryItem) -> float:
    """Fallback keyword overlap score (0.0 - 1.0)."""
    query_terms = set(query.lower().split())
    content = f"{memory.key} {json.dumps(memory.value)}".lower()
    content_terms = set(content.split())
    if not query_terms:
        return 0.0
    matches = len(query_terms & content_terms)
    return matches / len(query_terms)


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    Stores memories with different types and retrieval methods.
    Semantic search uses real Ollama embeddings when available,
    falls back to keyword matching automatically.
    """

    def __init__(self):
        self._memories: Dict[str, MemoryItem] = {}
        self._user_memories: Dict[str, Dict[str, MemoryItem]] = {}
        self._embeddings: Dict[str, List[float]] = {}  # memory_id -> embedding vector
        self._lock = asyncio.Lock()

    async def store(
        self,
        input_data: MemoryStoreInput,
        user_id: Optional[str] = None
    ) -> MemoryItem:
        """Store a memory and compute its embedding."""
        async with self._lock:
            memory_id = f"mem-{uuid4().hex[:8]}"

            memory = MemoryItem(
                id=memory_id,
                key=input_data.key,
                value=input_data.value,
                memory_type=input_data.memory_type,
                user_id=user_id,
                metadata=input_data.metadata,
                created_at=datetime.utcnow()
            )

            self._memories[memory_id] = memory

            if user_id:
                if user_id not in self._user_memories:
                    self._user_memories[user_id] = {}
                self._user_memories[user_id][input_data.key] = memory

        # Compute embedding outside the lock (async HTTP call)
        text_to_embed = f"{input_data.key} {json.dumps(input_data.value)}"
        embedding = await _get_embedding(text_to_embed)
        if embedding:
            async with self._lock:
                self._embeddings[memory_id] = embedding
            logger.debug(f"Stored memory {memory_id} with embedding dim={len(embedding)}")
        else:
            logger.debug(f"Stored memory {memory_id} (keyword fallback — no embedding)")

        return memory

    async def recall(
        self,
        input_data: MemoryRecallInput,
        user_id: Optional[str] = None
    ) -> List[MemoryItem]:
        """
        Recall memories ranked by semantic similarity.
        Uses real cosine similarity if embeddings available,
        falls back to keyword overlap scoring.
        """
        # Get query embedding
        query_embedding = await _get_embedding(input_data.query)

        # Collect candidates
        candidates: List[MemoryItem] = []
        for memory in self._memories.values():
            if input_data.memory_type and memory.memory_type != input_data.memory_type:
                continue
            if user_id and memory.user_id and memory.user_id != user_id:
                continue
            candidates.append(memory)

        if not candidates:
            return []

        # Score candidates
        scored: List[Tuple[MemoryItem, float]] = []
        for memory in candidates:
            if query_embedding and memory.id in self._embeddings:
                # Real semantic similarity
                score = _cosine_similarity(query_embedding, self._embeddings[memory.id])
            else:
                # Keyword fallback
                score = _keyword_score(input_data.query, memory)

            if score > 0.0:
                scored.append((memory, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return [mem for mem, _ in scored[:input_data.limit]]

    async def get(self, key: str, user_id: Optional[str] = None) -> Optional[MemoryItem]:
        """Get a specific memory by key."""
        if user_id:
            return self._user_memories.get(user_id, {}).get(key)
        for memory in self._memories.values():
            if memory.key == key:
                return memory
        return None

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory and its embedding."""
        async with self._lock:
            if memory_id not in self._memories:
                return False
            memory = self._memories[memory_id]
            if memory.user_id:
                self._user_memories.get(memory.user_id, {}).pop(memory.key, None)
            self._embeddings.pop(memory_id, None)
            del self._memories[memory_id]
            return True

    async def list_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[MemoryItem]:
        """List memories with optional filters."""
        results = []
        for memory in self._memories.values():
            if memory_type and memory.memory_type != memory_type:
                continue
            if user_id and memory.user_id != user_id:
                continue
            results.append(memory)
        return results[:limit]

    async def consolidate_short_term(self, user_id: Optional[str] = None):
        """Promote short-term memories to long-term."""
        async with self._lock:
            for memory in self._memories.values():
                if memory.memory_type == MemoryType.SHORT_TERM:
                    if user_id is None or memory.user_id == user_id:
                        memory.memory_type = MemoryType.LONG_TERM
        logger.info("Short-term memories consolidated to long-term")

    def get_stats(self) -> Dict[str, Any]:
        """Return memory store stats."""
        return {
            "total_memories": len(self._memories),
            "memories_with_embeddings": len(self._embeddings),
            "embedding_model": EMBEDDING_MODEL,
            "semantic_search_active": len(self._embeddings) > 0,
            "by_type": {
                mt.value: sum(1 for m in self._memories.values() if m.memory_type == mt)
                for mt in MemoryType
            }
        }


class SemanticallyIndexedMemory(MemoryStore):
    """
    Extended memory store — uses real cosine similarity search
    over Ollama-generated embeddings.
    """

    async def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 10
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Search for similar memories by cosine similarity.
        Returns list of (memory, similarity_score) tuples.
        """
        scored = []
        for memory_id, embedding in self._embeddings.items():
            memory = self._memories.get(memory_id)
            if not memory:
                continue
            score = _cosine_similarity(query_embedding, embedding)
            if score > 0.0:
                scored.append((memory, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


# Singleton
_memory_store_instance: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get the memory store singleton"""
    global _memory_store_instance
    if _memory_store_instance is None:
        _memory_store_instance = MemoryStore()
    return _memory_store_instance
