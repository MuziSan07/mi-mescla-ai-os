"""
AI-OS HuggingFace Research Agent
==================================
Searches HuggingFace for models, datasets, and Spaces.
Evaluates model quality, downloads metadata, and saves to knowledge base.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
HF_API = "https://huggingface.co/api"
HF_INFERENCE_API = "https://api-inference.huggingface.co"


@dataclass
class ModelSearchResult:
    id: str
    author: str
    model_name: str
    pipeline_tag: Optional[str]
    downloads: int
    likes: int
    tags: List[str]
    last_modified: str
    private: bool
    library_name: Optional[str] = None
    card_data: Optional[Dict] = None
    inference_api_available: bool = False


@dataclass
class DatasetSearchResult:
    id: str
    author: str
    dataset_name: str
    downloads: int
    likes: int
    tags: List[str]
    last_modified: str
    private: bool
    description: Optional[str] = None


@dataclass
class SpaceSearchResult:
    id: str
    author: str
    space_name: str
    sdk: Optional[str]
    likes: int
    last_modified: str
    app_url: str
    tags: List[str]


@dataclass
class HFResearchReport:
    query: str
    timestamp: str
    models: List[ModelSearchResult] = field(default_factory=list)
    datasets: List[DatasetSearchResult] = field(default_factory=list)
    spaces: List[SpaceSearchResult] = field(default_factory=list)
    best_model: Optional[str] = None
    summary: str = ""
    knowledge_saved: bool = False


class HuggingFaceResearchAgent:
    """
    Full HuggingFace research agent.
    - Search models by task, library, language
    - Search datasets
    - Search Spaces
    - Evaluate and rank models
    - Auto-save to knowledge base
    """

    def __init__(self, token: str = None):
        self._token = token or HF_TOKEN
        self._headers = {}
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=30.0,
                follow_redirects=True
            )
        return self._client

    async def search_models(
        self,
        query: str,
        task: Optional[str] = None,
        library: Optional[str] = None,
        language: Optional[str] = None,
        sort: str = "downloads",
        limit: int = 10
    ) -> List[ModelSearchResult]:
        """
        Search HuggingFace models.
        Tasks: text-generation, text-classification, image-classification,
               object-detection, automatic-speech-recognition, etc.
        Libraries: transformers, diffusers, timm, sentence-transformers, etc.
        """
        params = {
            "search": query,
            "sort": sort,
            "direction": -1,
            "limit": limit,
            "full": True,
        }
        if task:
            params["pipeline_tag"] = task
        if library:
            params["library"] = library
        if language:
            params["language"] = language

        try:
            response = await self._get_client().get(
                f"{HF_API}/models",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data:
                model_id = item.get("id", "")
                parts = model_id.split("/", 1)
                author = parts[0] if len(parts) > 1 else ""
                name = parts[1] if len(parts) > 1 else model_id
                results.append(ModelSearchResult(
                    id=model_id,
                    author=author,
                    model_name=name,
                    pipeline_tag=item.get("pipeline_tag"),
                    downloads=item.get("downloads", 0),
                    likes=item.get("likes", 0),
                    tags=item.get("tags", []),
                    last_modified=item.get("lastModified", ""),
                    private=item.get("private", False),
                    library_name=item.get("library_name"),
                    card_data=item.get("cardData"),
                    inference_api_available=item.get("inference", {}).get("status") == "live"
                    if isinstance(item.get("inference"), dict) else False
                ))
            logger.info(f"HF model search '{query}': {len(results)} models")
            return results
        except Exception as e:
            logger.error(f"HF model search failed: {e}")
            return []

    async def search_datasets(
        self,
        query: str,
        task: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 10
    ) -> List[DatasetSearchResult]:
        """Search HuggingFace datasets"""
        params = {
            "search": query,
            "sort": "downloads",
            "direction": -1,
            "limit": limit,
            "full": True,
        }
        if task:
            params["task_categories"] = task
        if language:
            params["language"] = language

        try:
            response = await self._get_client().get(
                f"{HF_API}/datasets",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data:
                dataset_id = item.get("id", "")
                parts = dataset_id.split("/", 1)
                author = parts[0] if len(parts) > 1 else ""
                name = parts[1] if len(parts) > 1 else dataset_id
                results.append(DatasetSearchResult(
                    id=dataset_id,
                    author=author,
                    dataset_name=name,
                    downloads=item.get("downloads", 0),
                    likes=item.get("likes", 0),
                    tags=item.get("tags", []),
                    last_modified=item.get("lastModified", ""),
                    private=item.get("private", False),
                    description=item.get("description")
                ))
            return results
        except Exception as e:
            logger.error(f"HF dataset search failed: {e}")
            return []

    async def search_spaces(
        self,
        query: str,
        sdk: Optional[str] = None,
        limit: int = 10
    ) -> List[SpaceSearchResult]:
        """Search HuggingFace Spaces"""
        params = {
            "search": query,
            "sort": "likes",
            "direction": -1,
            "limit": limit,
            "full": True,
        }
        if sdk:
            params["sdk"] = sdk

        try:
            response = await self._get_client().get(
                f"{HF_API}/spaces",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data:
                space_id = item.get("id", "")
                parts = space_id.split("/", 1)
                author = parts[0] if len(parts) > 1 else ""
                name = parts[1] if len(parts) > 1 else space_id
                results.append(SpaceSearchResult(
                    id=space_id,
                    author=author,
                    space_name=name,
                    sdk=item.get("sdk"),
                    likes=item.get("likes", 0),
                    last_modified=item.get("lastModified", ""),
                    app_url=f"https://huggingface.co/spaces/{space_id}",
                    tags=item.get("tags", [])
                ))
            return results
        except Exception as e:
            logger.error(f"HF spaces search failed: {e}")
            return []

    async def get_model_card(self, model_id: str) -> Optional[str]:
        """Fetch model card (README) for a model"""
        try:
            response = await self._get_client().get(
                f"https://huggingface.co/{model_id}/raw/main/README.md"
            )
            if response.status_code == 200:
                return response.text[:3000]
            return None
        except Exception as e:
            logger.debug(f"Model card fetch failed for {model_id}: {e}")
            return None

    async def run_inference(
        self,
        model_id: str,
        inputs: Any,
        parameters: Optional[Dict] = None
    ) -> Optional[Any]:
        """
        Run inference on a model via HuggingFace Inference API.
        Only works for models with inference_api_available=True.
        """
        if not self._token:
            logger.warning("HF token required for inference API")
            return None
        try:
            payload = {"inputs": inputs}
            if parameters:
                payload["parameters"] = parameters

            response = await self._get_client().post(
                f"{HF_INFERENCE_API}/models/{model_id}",
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HF inference failed for {model_id}: {e}")
            return None

    def rank_models(self, models: List[ModelSearchResult]) -> List[ModelSearchResult]:
        """
        Rank models by a composite score:
        downloads * 0.5 + likes * 0.3 + inference_available * 0.2
        """
        def score(m: ModelSearchResult) -> float:
            dl_score = min(m.downloads / 1_000_000, 1.0) * 0.5
            like_score = min(m.likes / 10_000, 1.0) * 0.3
            inf_score = 0.2 if m.inference_api_available else 0.0
            return dl_score + like_score + inf_score

        return sorted(models, key=score, reverse=True)

    async def research(
        self,
        query: str,
        task: Optional[str] = None,
        language: Optional[str] = None,
        include_datasets: bool = True,
        include_spaces: bool = True,
        save_to_knowledge_base: bool = True,
        limit: int = 10
    ) -> HFResearchReport:
        """
        Full HuggingFace research pipeline:
        1. Search models
        2. Optionally search datasets
        3. Optionally search spaces
        4. Rank and pick best model
        5. Save to knowledge base
        """
        report = HFResearchReport(
            query=query,
            timestamp=datetime.now().isoformat()
        )

        # Search models
        report.models = await self.search_models(
            query, task=task, language=language, limit=limit
        )
        report.models = self.rank_models(report.models)

        if report.models:
            report.best_model = report.models[0].id

        # Search datasets
        if include_datasets:
            report.datasets = await self.search_datasets(
                query, language=language, limit=5
            )

        # Search spaces
        if include_spaces:
            report.spaces = await self.search_spaces(query, limit=5)

        # Summary
        report.summary = (
            f"Found {len(report.models)} models, "
            f"{len(report.datasets)} datasets, "
            f"{len(report.spaces)} spaces for '{query}'. "
            f"Best model: {report.best_model or 'none found'}."
        )

        # Save to knowledge base
        if save_to_knowledge_base:
            try:
                from ai_os.core.knowledge.knowledge_base import get_knowledge_base
                kb = get_knowledge_base()
                await kb.add_research_report("huggingface", query, {
                    "models": [m.__dict__ for m in report.models[:5]],
                    "datasets": [d.__dict__ for d in report.datasets[:3]],
                    "spaces": [s.__dict__ for s in report.spaces[:3]],
                    "best_model": report.best_model,
                    "summary": report.summary
                })
                report.knowledge_saved = True
            except Exception as e:
                logger.warning(f"Could not save to knowledge base: {e}")

        return report

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_hf_research_agent: Optional[HuggingFaceResearchAgent] = None


def get_hf_research_agent() -> HuggingFaceResearchAgent:
    global _hf_research_agent
    if _hf_research_agent is None:
        _hf_research_agent = HuggingFaceResearchAgent()
    return _hf_research_agent
