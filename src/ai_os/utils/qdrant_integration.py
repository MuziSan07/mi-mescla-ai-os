"""
AI-OS Qdrant Integration
Connects Qdrant vector database for persistent semantic memory storage.
Falls back gracefully to in-memory storage if Qdrant is unavailable.
"""

import os
import logging
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "aios_memories")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))  # nomic-embed-text default


class QdrantMemoryStore:
    """
    Persistent vector memory store backed by Qdrant.
    Automatically falls back to in-memory if Qdrant is not reachable.
    """

    def __init__(self):
        self._client = None
        self._available = False
        self._fallback: Dict[str, Tuple[List[float], Dict]] = {}  # id -> (vector, payload)

    async def connect(self) -> bool:
        """Try to connect to Qdrant. Returns True if successful."""
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

            # Check connection
            collections = await self._client.get_collections()
            existing = [c.name for c in collections.collections]

            # Create collection if it doesn't exist
            if QDRANT_COLLECTION not in existing:
                await self._client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")

            self._available = True
            logger.info(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
            return True

        except ImportError:
            logger.warning(
                "qdrant-client not installed. "
                "Install with: pip install qdrant-client. "
                "Using in-memory fallback."
            )
            return False
        except Exception as e:
            logger.warning(
                f"Qdrant not reachable at {QDRANT_HOST}:{QDRANT_PORT}: {e}. "
                "Using in-memory fallback."
            )
            return False

    async def upsert(
        self,
        memory_id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ) -> bool:
        """Store a vector + payload. Falls back to dict if Qdrant unavailable."""
        if self._available and self._client:
            try:
                from qdrant_client.models import PointStruct
                await self._client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=[PointStruct(id=_id_to_int(memory_id), vector=vector, payload=payload)]
                )
                return True
            except Exception as e:
                logger.error(f"Qdrant upsert failed: {e}")

        # Fallback
        self._fallback[memory_id] = (vector, payload)
        return True

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filter_payload: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """
        Search for similar vectors.
        Returns list of (memory_id, score, payload).
        """
        if self._available and self._client:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                qdrant_filter = None
                if filter_payload:
                    conditions = [
                        FieldCondition(key=k, match=MatchValue(value=v))
                        for k, v in filter_payload.items()
                    ]
                    if conditions:
                        qdrant_filter = Filter(must=conditions)

                results = await self._client.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    with_payload=True
                )
                return [
                    (_int_to_id(r.id), r.score, r.payload or {})
                    for r in results
                ]
            except Exception as e:
                logger.error(f"Qdrant search failed: {e}")

        # Fallback — cosine similarity in memory
        return _in_memory_search(query_vector, self._fallback, limit)

    async def delete(self, memory_id: str) -> bool:
        """Delete a vector by ID."""
        if self._available and self._client:
            try:
                from qdrant_client.models import PointIdsList
                await self._client.delete(
                    collection_name=QDRANT_COLLECTION,
                    points_selector=PointIdsList(points=[_id_to_int(memory_id)])
                )
            except Exception as e:
                logger.error(f"Qdrant delete failed: {e}")

        self._fallback.pop(memory_id, None)
        return True

    async def count(self) -> int:
        """Get total number of stored vectors."""
        if self._available and self._client:
            try:
                result = await self._client.count(collection_name=QDRANT_COLLECTION)
                return result.count
            except Exception:
                pass
        return len(self._fallback)

    def is_available(self) -> bool:
        return self._available

    def get_stats(self) -> Dict[str, Any]:
        return {
            "qdrant_available": self._available,
            "qdrant_host": f"{QDRANT_HOST}:{QDRANT_PORT}",
            "collection": QDRANT_COLLECTION,
            "fallback_count": len(self._fallback),
            "embedding_dim": EMBEDDING_DIM,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id_to_int(memory_id: str) -> int:
    """Convert memory string ID to int for Qdrant (uses hash)."""
    return abs(hash(memory_id)) % (2 ** 53)


def _int_to_id(point_id) -> str:
    return str(point_id)


def _in_memory_search(
    query_vector: List[float],
    store: Dict[str, Tuple[List[float], Dict]],
    limit: int
) -> List[Tuple[str, float, Dict]]:
    """Cosine similarity search over in-memory fallback store."""
    import math

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        ma = math.sqrt(sum(x * x for x in a))
        mb = math.sqrt(sum(x * x for x in b))
        return dot / (ma * mb) if ma and mb else 0.0

    scored = []
    for mem_id, (vector, payload) in store.items():
        if len(vector) == len(query_vector):
            score = cosine(query_vector, vector)
            scored.append((mem_id, score, payload))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_qdrant_store: Optional[QdrantMemoryStore] = None


def get_qdrant_store() -> QdrantMemoryStore:
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantMemoryStore()
    return _qdrant_store


async def init_qdrant() -> bool:
    """Call this at startup to connect Qdrant. Safe to call even if unavailable."""
    store = get_qdrant_store()
    return await store.connect()
