"""
AI-OS Knowledge Base
=====================
Automatically builds and maintains a knowledge base from research findings.
Stores structured knowledge from GitHub, HuggingFace, web research, and docs.
Uses SQLite for persistence + in-memory semantic index.
"""

import os
import json
import asyncio
import logging
import sqlite3
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading

import httpx

logger = logging.getLogger(__name__)

KB_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "/app/src/ai_os/data/knowledge.db")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

_db_lock = threading.Lock()


# ---------------------------------------------------------------------------
# DB Setup
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(KB_PATH), exist_ok=True)
    conn = sqlite3.connect(KB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _db_lock:
        conn = _get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]',
                embedding TEXT DEFAULT NULL,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS research_reports (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_source ON knowledge_entries(source);
            CREATE INDEX IF NOT EXISTS idx_category ON knowledge_entries(category);
            CREATE INDEX IF NOT EXISTS idx_created ON knowledge_entries(created_at);
        """)
        conn.commit()
        conn.close()


_init_db()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeEntry:
    id: str
    source: str
    category: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0

    @staticmethod
    def from_row(row) -> "KnowledgeEntry":
        return KnowledgeEntry(
            id=row["id"],
            source=row["source"],
            category=row["category"],
            title=row["title"],
            content=row["content"],
            metadata=json.loads(row["metadata"] or "{}"),
            tags=json.loads(row["tags"] or "[]"),
            confidence=row["confidence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"]
        )


@dataclass
class KnowledgeSearchResult:
    entry: KnowledgeEntry
    score: float
    match_type: str  # "semantic" or "keyword"


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

async def _get_embedding(text: str) -> Optional[List[float]]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text[:2000]}
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
    except Exception:
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a))
    mb = math.sqrt(sum(x * x for x in b))
    return dot / (ma * mb) if ma and mb else 0.0


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """
    Persistent knowledge base with semantic search.
    Sources: github, huggingface, web, manual, agent
    Categories: model, repo, dataset, tutorial, api, concept, tool
    """

    def __init__(self):
        self._embeddings: Dict[str, List[float]] = {}  # id -> embedding
        self._loaded = False

    async def _ensure_loaded(self):
        """Load embeddings from DB on first access"""
        if self._loaded:
            return
        with _db_lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT id, embedding FROM knowledge_entries WHERE embedding IS NOT NULL"
                ).fetchall()
                for row in rows:
                    if row["embedding"]:
                        try:
                            self._embeddings[row["id"]] = json.loads(row["embedding"])
                        except Exception:
                            pass
            finally:
                conn.close()
        self._loaded = True

    async def add(
        self,
        source: str,
        category: str,
        title: str,
        content: str,
        metadata: Dict[str, Any] = None,
        tags: List[str] = None,
        confidence: float = 1.0
    ) -> KnowledgeEntry:
        """Add a new knowledge entry"""
        entry = KnowledgeEntry(
            id=str(uuid.uuid4()),
            source=source,
            category=category,
            title=title,
            content=content,
            metadata=metadata or {},
            tags=tags or [],
            confidence=confidence
        )

        # Get embedding
        embedding = await _get_embedding(f"{title} {content}")
        embedding_json = json.dumps(embedding) if embedding else None
        if embedding:
            self._embeddings[entry.id] = embedding

        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO knowledge_entries
                    (id, source, category, title, content, metadata, tags, embedding, confidence, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    entry.id, entry.source, entry.category, entry.title,
                    entry.content, json.dumps(entry.metadata), json.dumps(entry.tags),
                    embedding_json, entry.confidence, entry.created_at, entry.updated_at
                ))
                conn.commit()
            finally:
                conn.close()

        logger.info(f"Knowledge added: [{source}/{category}] {title}")
        return entry

    async def search(
        self,
        query: str,
        source: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[KnowledgeSearchResult]:
        """Search knowledge base by semantic similarity + keyword fallback"""
        await self._ensure_loaded()

        # Get query embedding
        query_embedding = await _get_embedding(query)

        # Load candidates from DB
        with _db_lock:
            conn = _get_conn()
            try:
                sql = "SELECT * FROM knowledge_entries WHERE 1=1"
                params = []
                if source:
                    sql += " AND source = ?"
                    params.append(source)
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                rows = conn.execute(sql, params).fetchall()
                candidates = [KnowledgeEntry.from_row(r) for r in rows]
            finally:
                conn.close()

        if not candidates:
            return []

        # Score candidates
        scored: List[KnowledgeSearchResult] = []
        query_lower = query.lower()

        for entry in candidates:
            if query_embedding and entry.id in self._embeddings:
                score = _cosine_similarity(query_embedding, self._embeddings[entry.id])
                match_type = "semantic"
            else:
                # Keyword fallback
                text = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
                words = set(query_lower.split())
                matches = sum(1 for w in words if w in text)
                score = matches / max(len(words), 1)
                match_type = "keyword"

            if score > 0.1:
                scored.append(KnowledgeSearchResult(
                    entry=entry, score=score, match_type=match_type
                ))

        scored.sort(key=lambda x: x.score, reverse=True)

        # Update access counts
        top_ids = [r.entry.id for r in scored[:limit]]
        if top_ids:
            with _db_lock:
                conn = _get_conn()
                try:
                    conn.execute(
                        f"UPDATE knowledge_entries SET access_count = access_count + 1 "
                        f"WHERE id IN ({','.join('?' * len(top_ids))})",
                        top_ids
                    )
                    conn.commit()
                finally:
                    conn.close()

        return scored[:limit]

    async def add_research_report(
        self,
        source: str,
        query: str,
        data: Dict[str, Any]
    ) -> str:
        """Save a full research report and extract knowledge entries"""
        report_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO research_reports (id, source, query, data, created_at)
                    VALUES (?,?,?,?,?)
                """, (report_id, source, query, json.dumps(data), now))
                conn.commit()
            finally:
                conn.close()

        # Extract and store individual knowledge entries
        if source == "github":
            repos = data.get("repos", [])
            for repo in repos[:5]:
                if isinstance(repo, dict):
                    await self.add(
                        source="github",
                        category="repo",
                        title=repo.get("full_name", repo.get("name", "unknown")),
                        content=(
                            f"Description: {repo.get('description', 'N/A')}\n"
                            f"Stars: {repo.get('stars', 0)}\n"
                            f"Language: {repo.get('language', 'N/A')}\n"
                            f"Topics: {', '.join(repo.get('topics', []))}\n"
                            f"URL: {repo.get('html_url', '')}"
                        ),
                        metadata=repo,
                        tags=repo.get("topics", []) + [repo.get("language", "")],
                        confidence=min(1.0, repo.get("stars", 0) / 10000)
                    )

        elif source == "huggingface":
            models = data.get("models", [])
            for model in models[:5]:
                if isinstance(model, dict):
                    await self.add(
                        source="huggingface",
                        category="model",
                        title=model.get("id", "unknown"),
                        content=(
                            f"Task: {model.get('pipeline_tag', 'N/A')}\n"
                            f"Downloads: {model.get('downloads', 0)}\n"
                            f"Likes: {model.get('likes', 0)}\n"
                            f"Library: {model.get('library_name', 'N/A')}\n"
                            f"Inference available: {model.get('inference_api_available', False)}\n"
                            f"Tags: {', '.join(model.get('tags', []))}"
                        ),
                        metadata=model,
                        tags=model.get("tags", []) + [model.get("pipeline_tag", "")],
                        confidence=min(1.0, model.get("downloads", 0) / 1_000_000)
                    )

        return report_id

    async def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get a specific entry by ID"""
        with _db_lock:
            conn = _get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM knowledge_entries WHERE id = ?", (entry_id,)
                ).fetchone()
                return KnowledgeEntry.from_row(row) if row else None
            finally:
                conn.close()

    async def delete(self, entry_id: str) -> bool:
        """Delete an entry"""
        with _db_lock:
            conn = _get_conn()
            try:
                result = conn.execute(
                    "DELETE FROM knowledge_entries WHERE id = ?", (entry_id,)
                )
                conn.commit()
                self._embeddings.pop(entry_id, None)
                return result.rowcount > 0
            finally:
                conn.close()

    async def list_entries(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[KnowledgeEntry]:
        """List knowledge entries with filters"""
        with _db_lock:
            conn = _get_conn()
            try:
                sql = "SELECT * FROM knowledge_entries WHERE 1=1"
                params = []
                if source:
                    sql += " AND source = ?"
                    params.append(source)
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                sql += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
                return [KnowledgeEntry.from_row(r) for r in rows]
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        with _db_lock:
            conn = _get_conn()
            try:
                total = conn.execute("SELECT COUNT(*) FROM knowledge_entries").fetchone()[0]
                by_source = conn.execute(
                    "SELECT source, COUNT(*) as count FROM knowledge_entries GROUP BY source"
                ).fetchall()
                by_category = conn.execute(
                    "SELECT category, COUNT(*) as count FROM knowledge_entries GROUP BY category"
                ).fetchall()
                reports = conn.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0]
                return {
                    "total_entries": total,
                    "research_reports": reports,
                    "embeddings_loaded": len(self._embeddings),
                    "by_source": {r["source"]: r["count"] for r in by_source},
                    "by_category": {r["category"]: r["count"] for r in by_category},
                }
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base
