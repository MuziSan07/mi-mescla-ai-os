"""
AI-OS Knowledge API (Phase 5) — the Obsidian vault as shared memory.

Endpoints (mounted at /api/v1/knowledge):
  GET  /status              vault location + note count
  GET  /notes               list note paths
  GET  /note?path=...       read a note
  POST /note                {title|path, content, tags?} -> create/update
  DELETE /note?path=...     delete a note
  GET  /search?q=...        keyword search over the vault
  POST /ask                 {question} -> answer grounded in the vault, with sources
  POST /remember            {title, content, tags?} -> quick-save a note (agents use this)
"""

import os
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from ai_os.core.knowledge.vault import get_vault
from ai_os.core.router.api_gateway import get_unified_gateway

router = APIRouter(tags=["knowledge"])  # prefix supplied by main.py (/api/v1/knowledge)
logger = logging.getLogger(__name__)

ASK_SYSTEM = (
    "You answer using ONLY the notes provided from the user's knowledge vault. "
    "Cite the note paths you used. If the notes don't contain the answer, say so "
    "plainly instead of guessing."
)


class NoteRequest(BaseModel):
    title: Optional[str] = None
    path: Optional[str] = None
    content: str
    tags: Optional[List[str]] = None


class AskRequest(BaseModel):
    question: str
    k: int = 4
    model: Optional[str] = None


@router.get("/status")
async def knowledge_status():
    v = get_vault()
    from ai_os.core.knowledge.index import _HAVE_NATIVE
    return {**v.stats(), "retrieval": "keyword (inverted index)",
            "native_tokenizer": _HAVE_NATIVE,
            "semantic": "optional (embeddings/Qdrant)"}


@router.get("/notes")
async def list_notes():
    return {"notes": get_vault().list_notes()}


@router.get("/note")
async def read_note(path: str = Query(...)):
    try:
        return get_vault().read_note(path).to_dict()
    except FileNotFoundError:
        raise HTTPException(404, "Note not found.")


@router.post("/note")
async def write_note(req: NoteRequest):
    if not req.content.strip():
        raise HTTPException(422, "Empty note content.")
    target = req.path or req.title
    if not target:
        raise HTTPException(422, "Provide a title or path.")
    try:
        note = get_vault().write_note(target, req.content, tags=req.tags)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return note.to_dict()


@router.delete("/note")
async def delete_note(path: str = Query(...)):
    if not get_vault().delete_note(path):
        raise HTTPException(404, "Note not found.")
    return {"deleted": path}


@router.get("/search")
async def search(q: str = Query(...), k: int = 5):
    return {"query": q, "results": get_vault().search(q, k=k)}


@router.post("/remember")
async def remember(req: NoteRequest):
    """Quick-save a note — the convenience the Conductor's agents call to persist knowledge."""
    return await write_note(req)


@router.post("/ask")
async def ask(req: AskRequest):
    """Retrieval-augmented answer grounded in the vault, with sources."""
    if not req.question.strip():
        raise HTTPException(422, "Empty question.")
    vault = get_vault()
    hits = vault.search(req.question, k=req.k)
    if not hits:
        return {"answer": "I couldn't find anything about that in the vault yet.",
                "sources": [], "grounded": False}

    context = "\n\n".join(
        f"### Note: {h['path']}\n{vault.read_note(h['path']).content[:1200]}" for h in hits
    )
    model = req.model or os.getenv("DEFAULT_LOCAL_MODEL", "llama3.2")
    gateway = get_unified_gateway()
    try:
        result = await gateway.chat(
            model=model,
            messages=[
                {"role": "system", "content": ASK_SYSTEM},
                {"role": "user", "content": f"Notes:\n{context}\n\nQuestion: {req.question}"},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        answer = result.choices[0]["message"]["content"].strip() if result.choices else ""
    except Exception as e:
        logger.warning("Knowledge ask failed: %s", e)
        raise HTTPException(503, f"Assistant unavailable: {e}")

    return {"answer": answer, "sources": [h["path"] for h in hits], "grounded": True}
