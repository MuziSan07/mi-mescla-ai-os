"""
AI-OS Research API Routes
Exposes GitHub research, HuggingFace research, and Knowledge Base via REST.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class GitHubSearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    min_stars: int = 0
    include_code: bool = False
    include_trending: bool = True
    save_to_kb: bool = True
    limit: int = 10


class HFSearchRequest(BaseModel):
    query: str
    task: Optional[str] = None
    language: Optional[str] = None
    include_datasets: bool = True
    include_spaces: bool = True
    save_to_kb: bool = True
    limit: int = 10


class KnowledgeSearchRequest(BaseModel):
    query: str
    source: Optional[str] = None
    category: Optional[str] = None
    limit: int = 10


class KnowledgeAddRequest(BaseModel):
    source: str
    category: str
    title: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# GitHub Research Endpoints
# ---------------------------------------------------------------------------

@router.post("/research/github/search")
async def github_search(request: GitHubSearchRequest):
    """
    Search GitHub repositories and optionally save to knowledge base.
    Returns repos, trending, and code results.
    """
    try:
        from ai_os.utils.github_research_agent import get_github_research_agent
        agent = get_github_research_agent()
        report = await agent.research(
            query=request.query,
            language=request.language,
            include_code=request.include_code,
            include_trending=request.include_trending,
            save_to_knowledge_base=request.save_to_kb,
            limit=request.limit
        )
        return {
            "query": report.query,
            "timestamp": report.timestamp,
            "summary": report.summary,
            "knowledge_saved": report.knowledge_saved,
            "repos": [
                {
                    "full_name": r.full_name,
                    "description": r.description,
                    "stars": r.stars,
                    "language": r.language,
                    "topics": r.topics,
                    "url": r.html_url,
                    "clone_url": r.clone_url
                }
                for r in report.repos
            ],
            "trending": [
                {
                    "full_name": t.full_name,
                    "description": t.description,
                    "stars": t.stars,
                    "language": t.language,
                    "url": t.html_url
                }
                for t in report.trending
            ],
            "code_results": [
                {
                    "filename": c.filename,
                    "path": c.path,
                    "repository": c.repository,
                    "url": c.html_url
                }
                for c in report.code_results
            ]
        }
    except Exception as e:
        logger.exception("GitHub search failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/github/trending")
async def github_trending(
    language: Optional[str] = None,
    since: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    limit: int = 10
):
    """Get trending GitHub repositories"""
    try:
        from ai_os.utils.github_research_agent import get_github_research_agent
        agent = get_github_research_agent()
        trending = await agent.get_trending(language=language, since=since, limit=limit)
        return {
            "since": since,
            "language": language,
            "repos": [
                {
                    "full_name": t.full_name,
                    "description": t.description,
                    "stars": t.stars,
                    "language": t.language,
                    "url": t.html_url
                }
                for t in trending
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/github/analyze/{owner}/{repo}")
async def github_analyze_repo(owner: str, repo: str):
    """Deep analysis of a specific GitHub repository"""
    try:
        from ai_os.utils.github_research_agent import get_github_research_agent
        agent = get_github_research_agent()
        analysis = await agent.analyze_repository(f"{owner}/{repo}")
        if not analysis:
            raise HTTPException(status_code=404, detail="Repository not found")
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# HuggingFace Research Endpoints
# ---------------------------------------------------------------------------

@router.post("/research/huggingface/search")
async def huggingface_search(request: HFSearchRequest):
    """
    Search HuggingFace for models, datasets, and spaces.
    Returns ranked results and saves to knowledge base.
    """
    try:
        from ai_os.utils.huggingface_research_agent import get_hf_research_agent
        agent = get_hf_research_agent()
        report = await agent.research(
            query=request.query,
            task=request.task,
            language=request.language,
            include_datasets=request.include_datasets,
            include_spaces=request.include_spaces,
            save_to_knowledge_base=request.save_to_kb,
            limit=request.limit
        )
        return {
            "query": report.query,
            "timestamp": report.timestamp,
            "summary": report.summary,
            "best_model": report.best_model,
            "knowledge_saved": report.knowledge_saved,
            "models": [
                {
                    "id": m.id,
                    "pipeline_tag": m.pipeline_tag,
                    "downloads": m.downloads,
                    "likes": m.likes,
                    "library": m.library_name,
                    "inference_available": m.inference_api_available,
                    "tags": m.tags[:10]
                }
                for m in report.models
            ],
            "datasets": [
                {
                    "id": d.id,
                    "downloads": d.downloads,
                    "likes": d.likes,
                    "tags": d.tags[:5]
                }
                for d in report.datasets
            ],
            "spaces": [
                {
                    "id": s.id,
                    "sdk": s.sdk,
                    "likes": s.likes,
                    "url": s.app_url
                }
                for s in report.spaces
            ]
        }
    except Exception as e:
        logger.exception("HuggingFace search failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/huggingface/models")
async def list_hf_models(
    query: str = "",
    task: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 10
):
    """Quick model search on HuggingFace"""
    try:
        from ai_os.utils.huggingface_research_agent import get_hf_research_agent
        agent = get_hf_research_agent()
        models = await agent.search_models(query, task=task, library=library, limit=limit)
        models = agent.rank_models(models)
        return {
            "count": len(models),
            "models": [
                {
                    "id": m.id,
                    "pipeline_tag": m.pipeline_tag,
                    "downloads": m.downloads,
                    "likes": m.likes,
                    "inference_available": m.inference_api_available
                }
                for m in models
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/huggingface/infer")
async def hf_inference(
    model_id: str,
    inputs: Any,
    parameters: Optional[Dict[str, Any]] = None
):
    """Run inference on a HuggingFace model"""
    try:
        from ai_os.utils.huggingface_research_agent import get_hf_research_agent
        agent = get_hf_research_agent()
        result = await agent.run_inference(model_id, inputs, parameters)
        if result is None:
            raise HTTPException(status_code=503, detail="Inference unavailable — check HF token")
        return {"model": model_id, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Knowledge Base Endpoints
# ---------------------------------------------------------------------------

@router.post("/research/knowledge/search")
async def knowledge_search(request: KnowledgeSearchRequest):
    """Search the knowledge base semantically"""
    try:
        from ai_os.core.knowledge.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        results = await kb.search(
            query=request.query,
            source=request.source,
            category=request.category,
            limit=request.limit
        )
        return {
            "query": request.query,
            "count": len(results),
            "results": [
                {
                    "id": r.entry.id,
                    "source": r.entry.source,
                    "category": r.entry.category,
                    "title": r.entry.title,
                    "content_preview": r.entry.content[:300],
                    "tags": r.entry.tags,
                    "score": round(r.score, 4),
                    "match_type": r.match_type,
                    "created_at": r.entry.created_at
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/knowledge/add")
async def knowledge_add(request: KnowledgeAddRequest):
    """Manually add an entry to the knowledge base"""
    try:
        from ai_os.core.knowledge.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        entry = await kb.add(
            source=request.source,
            category=request.category,
            title=request.title,
            content=request.content,
            metadata=request.metadata,
            tags=request.tags,
            confidence=request.confidence
        )
        return {"id": entry.id, "title": entry.title, "created_at": entry.created_at}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/knowledge/list")
async def knowledge_list(
    source: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50
):
    """List knowledge base entries"""
    try:
        from ai_os.core.knowledge.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        entries = await kb.list_entries(source=source, category=category, limit=limit)
        return {
            "count": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "source": e.source,
                    "category": e.category,
                    "title": e.title,
                    "tags": e.tags,
                    "confidence": e.confidence,
                    "access_count": e.access_count,
                    "created_at": e.created_at
                }
                for e in entries
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/knowledge/stats")
async def knowledge_stats():
    """Get knowledge base statistics"""
    try:
        from ai_os.core.knowledge.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        return kb.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/research/knowledge/{entry_id}")
async def knowledge_delete(entry_id: str):
    """Delete a knowledge entry"""
    try:
        from ai_os.core.knowledge.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        deleted = await kb.delete(entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Entry not found")
        return {"deleted": True, "id": entry_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
