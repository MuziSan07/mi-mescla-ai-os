"""
AI-OS GitHub Research Agent
============================
Searches GitHub for repositories, code, users, and trending projects.
Automatically adds findings to the knowledge base.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"


@dataclass
class RepoSearchResult:
    id: int
    name: str
    full_name: str
    description: Optional[str]
    html_url: str
    clone_url: str
    language: Optional[str]
    stars: int
    forks: int
    topics: List[str]
    updated_at: str
    license: Optional[str] = None
    readme_preview: Optional[str] = None


@dataclass
class CodeSearchResult:
    filename: str
    path: str
    repository: str
    html_url: str
    score: float
    content_preview: Optional[str] = None


@dataclass
class TrendingRepo:
    name: str
    full_name: str
    description: Optional[str]
    html_url: str
    language: Optional[str]
    stars: int
    stars_today: int
    forks: int


@dataclass
class ResearchReport:
    query: str
    timestamp: str
    repos: List[RepoSearchResult] = field(default_factory=list)
    code_results: List[CodeSearchResult] = field(default_factory=list)
    trending: List[TrendingRepo] = field(default_factory=list)
    summary: str = ""
    knowledge_saved: bool = False


class GitHubResearchAgent:
    """
    Full GitHub research agent.
    - Search repositories by query, language, stars
    - Search code across GitHub
    - Get trending repositories
    - Analyze README and file structure
    - Auto-save findings to knowledge base
    """

    def __init__(self, token: str = None):
        self._token = token or GITHUB_TOKEN
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
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

    async def search_repositories(
        self,
        query: str,
        language: Optional[str] = None,
        min_stars: int = 0,
        sort: str = "stars",
        limit: int = 10
    ) -> List[RepoSearchResult]:
        """Search GitHub repositories"""
        q = query
        if language:
            q += f" language:{language}"
        if min_stars > 0:
            q += f" stars:>={min_stars}"

        try:
            response = await self._get_client().get(
                f"{GITHUB_API}/search/repositories",
                params={"q": q, "sort": sort, "order": "desc", "per_page": limit}
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get("items", []):
                results.append(RepoSearchResult(
                    id=item["id"],
                    name=item["name"],
                    full_name=item["full_name"],
                    description=item.get("description"),
                    html_url=item["html_url"],
                    clone_url=item["clone_url"],
                    language=item.get("language"),
                    stars=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0),
                    topics=item.get("topics", []),
                    updated_at=item.get("updated_at", ""),
                    license=item.get("license", {}).get("name") if item.get("license") else None
                ))
            logger.info(f"GitHub search '{query}': {len(results)} repos found")
            return results
        except Exception as e:
            logger.error(f"GitHub repo search failed: {e}")
            return []

    async def search_code(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 10
    ) -> List[CodeSearchResult]:
        """Search code across GitHub"""
        q = query
        if language:
            q += f" language:{language}"

        try:
            response = await self._get_client().get(
                f"{GITHUB_API}/search/code",
                params={"q": q, "per_page": limit}
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get("items", []):
                results.append(CodeSearchResult(
                    filename=item["name"],
                    path=item["path"],
                    repository=item["repository"]["full_name"],
                    html_url=item["html_url"],
                    score=item.get("score", 0.0)
                ))
            return results
        except Exception as e:
            logger.error(f"GitHub code search failed: {e}")
            return []

    async def get_trending(
        self,
        language: Optional[str] = None,
        since: str = "daily",
        limit: int = 10
    ) -> List[TrendingRepo]:
        """
        Get trending repositories.
        Uses GitHub search sorted by recently updated with high stars
        as a proxy for trending (GitHub doesn't have an official trending API).
        """
        try:
            from datetime import timedelta
            days = {"daily": 1, "weekly": 7, "monthly": 30}.get(since, 1)
            date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            q = f"created:>={date_from} stars:>=10"
            if language:
                q += f" language:{language}"

            response = await self._get_client().get(
                f"{GITHUB_API}/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": limit}
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get("items", []):
                results.append(TrendingRepo(
                    name=item["name"],
                    full_name=item["full_name"],
                    description=item.get("description"),
                    html_url=item["html_url"],
                    language=item.get("language"),
                    stars=item.get("stargazers_count", 0),
                    stars_today=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0)
                ))
            return results
        except Exception as e:
            logger.error(f"Trending fetch failed: {e}")
            return []

    async def get_readme(self, owner: str, repo: str) -> Optional[str]:
        """Fetch README content for a repository"""
        try:
            import base64
            response = await self._get_client().get(
                f"{GITHUB_API}/repos/{owner}/{repo}/readme"
            )
            response.raise_for_status()
            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
            return content[:3000]  # First 3000 chars
        except Exception as e:
            logger.debug(f"README fetch failed for {owner}/{repo}: {e}")
            return None

    async def get_file_structure(self, owner: str, repo: str) -> List[str]:
        """Get top-level file structure of a repository"""
        try:
            response = await self._get_client().get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/"
            )
            response.raise_for_status()
            items = response.json()
            return [f"{item['type']}: {item['name']}" for item in items]
        except Exception as e:
            logger.debug(f"File structure fetch failed: {e}")
            return []

    async def analyze_repository(self, full_name: str) -> Dict[str, Any]:
        """Deep analysis of a single repository"""
        try:
            owner, repo = full_name.split("/", 1)
            response = await self._get_client().get(
                f"{GITHUB_API}/repos/{owner}/{repo}"
            )
            response.raise_for_status()
            data = response.json()

            readme = await self.get_readme(owner, repo)
            structure = await self.get_file_structure(owner, repo)

            # Get languages breakdown
            langs_response = await self._get_client().get(
                f"{GITHUB_API}/repos/{owner}/{repo}/languages"
            )
            languages = langs_response.json() if langs_response.status_code == 200 else {}

            return {
                "name": data["name"],
                "full_name": data["full_name"],
                "description": data.get("description"),
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "language": data.get("language"),
                "languages": languages,
                "topics": data.get("topics", []),
                "license": data.get("license", {}).get("name") if data.get("license") else None,
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "has_wiki": data.get("has_wiki"),
                "has_pages": data.get("has_pages"),
                "readme_preview": readme,
                "file_structure": structure,
                "html_url": data.get("html_url"),
                "clone_url": data.get("clone_url"),
            }
        except Exception as e:
            logger.error(f"Repository analysis failed for {full_name}: {e}")
            return {}

    async def research(
        self,
        query: str,
        language: Optional[str] = None,
        include_code: bool = False,
        include_trending: bool = True,
        save_to_knowledge_base: bool = True,
        limit: int = 10
    ) -> ResearchReport:
        """
        Full research pipeline:
        1. Search repos
        2. Optionally search code
        3. Optionally get trending
        4. Generate summary
        5. Save to knowledge base
        """
        report = ResearchReport(
            query=query,
            timestamp=datetime.now().isoformat()
        )

        # Search repos
        report.repos = await self.search_repositories(
            query, language=language, limit=limit
        )

        # Search code if requested
        if include_code:
            report.code_results = await self.search_code(
                query, language=language, limit=limit
            )

        # Get trending
        if include_trending:
            report.trending = await self.get_trending(
                language=language, limit=5
            )

        # Generate summary
        repo_names = [r.full_name for r in report.repos[:5]]
        report.summary = (
            f"Found {len(report.repos)} repositories for '{query}'. "
            f"Top results: {', '.join(repo_names)}. "
            f"Trending: {len(report.trending)} repos. "
            f"Code results: {len(report.code_results)} files."
        )

        # Save to knowledge base
        if save_to_knowledge_base:
            try:
                from ai_os.core.knowledge.knowledge_base import get_knowledge_base
                kb = get_knowledge_base()
                await kb.add_research_report("github", query, report.__dict__)
                report.knowledge_saved = True
            except Exception as e:
                logger.warning(f"Could not save to knowledge base: {e}")

        return report

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_github_research_agent: Optional[GitHubResearchAgent] = None


def get_github_research_agent() -> GitHubResearchAgent:
    global _github_research_agent
    if _github_research_agent is None:
        _github_research_agent = GitHubResearchAgent()
    return _github_research_agent
