"""
AI-OS GitHub Integration
Manages GitHub sessions, private repos, cloning, pushing
"""

import os
import asyncio
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class GitHubSession:
    """GitHub authentication session"""
    token: str
    username: str = ""
    email: str = ""
    authenticated: bool = False


@dataclass
class Repository:
    """Repository information"""
    name: str
    full_name: str
    private: bool
    html_url: str
    clone_url: str
    ssh_url: str
    description: Optional[str] = None
    default_branch: str = "main"
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    updated_at: str = ""


@dataclass
class CommitInfo:
    """Commit information"""
    sha: str
    message: str
    author: str
    date: str
    url: str


class GitHubClient:
    """
    GitHub API client for managing repositories.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = None
        self.authenticated = False
        self.username = ""
        
    async def authenticate(self, token: str = None) -> bool:
        """
        Authenticate with GitHub using token.
        """
        self.token = token or self.token
        
        if not self.token:
            raise ValueError("No GitHub token provided")
        
        # Verify token by getting user info
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/user",
                headers={"Authorization": f"token {self.token}"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.username = data.get("login", "")
                self.authenticated = True
                
                self.session = GitHubSession(
                    token=self.token,
                    username=self.username,
                    email=data.get("email", ""),
                    authenticated=True
                )
                
                logger.info(f"Authenticated as {self.username}")
                return True
            
            return False
    
    async def get_user(self) -> Dict:
        """Get current user info"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/user",
                headers={"Authorization": f"token {self.token}"}
            )
            resp.raise_for_status()
            return resp.json()
    
    async def get_repo(self, owner: str, repo: str) -> Repository:
        """Get repository information"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}",
                headers={"Authorization": f"token {self.token}"}
            )
            resp.raise_for_status()
            data = resp.json()
            
            return Repository(
                name=data["name"],
                full_name=data["full_name"],
                private=data["private"],
                html_url=data["html_url"],
                clone_url=data["clone_url"],
                ssh_url=data["ssh_url"],
                description=data.get("description"),
                default_branch=data.get("default_branch", "main"),
                language=data.get("language"),
                stars=data.get("stargazers_count", 0),
                forks=data.get("forks_count", 0),
                updated_at=data.get("updated_at", "")
            )
    
    async def list_repos(self, private_only: bool = False) -> List[Repository]:
        """List user repositories"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/user/repos",
                headers={"Authorization": f"token {self.token}"},
                params={"sort": "updated", "per_page": 100}
            )
            resp.raise_for_status()
            data = resp.json()
            
            repos = []
            for repo in data:
                if private_only and not repo.get("private"):
                    continue
                    
                repos.append(Repository(
                    name=repo["name"],
                    full_name=repo["full_name"],
                    private=repo["private"],
                    html_url=repo["html_url"],
                    clone_url=repo["clone_url"],
                    ssh_url=repo["ssh_url"],
                    description=repo.get("description"),
                    default_branch=repo.get("default_branch", "main"),
                    language=repo.get("language"),
                    stars=repo.get("stargazers_count", 0),
                    forks=repo.get("forks_count", 0),
                    updated_at=repo.get("updated_at", "")
                ))
            
            return repos
    
    async def create_repo(
        self,
        name: str,
        private: bool = True,
        description: str = "",
        auto_init: bool = True,
        gitignore_template: str = None
    ) -> Repository:
        """Create a new repository"""
        import httpx
        
        data = {
            "name": name,
            "private": private,
            "auto_init": auto_init,
            "description": description
        }
        
        if gitignore_template:
            data["gitignore_template"] = gitignore_template
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/user/repos",
                headers={"Authorization": f"token {self.token}"},
                json=data
            )
            resp.raise_for_status()
            repo_data = resp.json()
            
            return Repository(
                name=repo_data["name"],
                full_name=repo_data["full_name"],
                private=repo_data["private"],
                html_url=repo_data["html_url"],
                clone_url=repo_data["clone_url"],
                ssh_url=repo_data["ssh_url"],
                description=repo_data.get("description"),
                default_branch=repo_data.get("default_branch", "main")
            )
    
    async def delete_repo(self, owner: str, repo: str):
        """Delete a repository"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.BASE_URL}/repos/{owner}/{repo}",
                headers={"Authorization": f"token {self.token}"}
            )
            resp.raise_for_status()
    
    async def get_branches(self, owner: str, repo: str) -> List[Dict]:
        """Get repository branches"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/branches",
                headers={"Authorization": f"token {self.token}"}
            )
            resp.raise_for_status()
            return resp.json()
    
    async def get_commits(
        self,
        owner: str,
        repo: str,
        limit: int = 10
    ) -> List[CommitInfo]:
        """Get recent commits"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/commits",
                headers={"Authorization": f"token {self.token}"},
                params={"per_page": limit}
            )
            resp.raise_for_status()
            data = resp.json()
            
            commits = []
            for commit in data:
                commits.append(CommitInfo(
                    sha=commit["sha"],
                    message=commit["commit"]["message"],
                    author=commit["commit"]["author"]["name"],
                    date=commit["commit"]["author"]["date"],
                    url=commit["html_url"]
                ))
            
            return commits
    
    async def get_contents(
        self,
        owner: str,
        repo: str,
        path: str = ""
    ) -> List[Dict]:
        """Get repository contents"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                headers={"Authorization": f"token {self.token}"}
            )
            resp.raise_for_status()
            return resp.json()
    
    async def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        name: str = None,
        body: str = None,
        draft: bool = False,
        prerelease: bool = False
    ) -> Dict:
        """Create a release"""
        import httpx
        
        data = {
            "tag_name": tag_name,
            "draft": draft,
            "prerelease": prerelease
        }
        
        if name:
            data["name"] = name
        if body:
            data["body"] = body
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/releases",
                headers={"Authorization": f"token {self.token}"},
                json=data
            )
            resp.raise_for_status()
            return resp.json()


class GitCloner:
    """
    Clone and manage git repositories.
    """
    
    @staticmethod
    async def clone(
        repo_url: str,
        target_dir: str = None,
        branch: str = "main",
        token: str = None
    ) -> str:
        """
        Clone a repository.
        """
        import subprocess
        
        # Add token to URL if provided
        if token and "github.com" in repo_url:
            if "https://" in repo_url:
                repo_url = repo_url.replace(
                    "https://",
                    f"https://{token}@"
                )
        
        cmd = ["git", "clone"]
        
        if branch:
            cmd.extend(["--branch", branch])
        
        cmd.append(repo_url)
        
        if target_dir:
            cmd.append(target_dir)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Clone failed: {result.stderr.decode()}")
        
        return target_dir or repo_url.split("/")[-1].replace(".git", "")
    
    @staticmethod
    async def clone_private(
        owner: str,
        repo: str,
        target_dir: str,
        token: str,
        branch: str = "main"
    ) -> str:
        """Clone a private repository"""
        repo_url = f"https://{token}@github.com/{owner}/{repo}.git"
        
        return await GitCloner.clone(
            repo_url,
            target_dir,
            branch,
            None  # Already in URL
        )
    
    @staticmethod
    async def add_commit_push(
        repo_path: str,
        message: str,
        files: List[str] = None,
        branch: str = "main"
    ):
        """
        Add, commit and push changes.
        """
        import subprocess
        
        # Add files
        if files:
            for f in files:
                subprocess.run(
                    ["git", "add", f],
                    cwd=repo_path,
                    check=True
                )
        else:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path,
                check=True
            )
        
        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path,
            check=True
        )
        
        # Push
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo_path,
            check=True
        )
    
    @staticmethod
    async def create_pr(
        repo_path: str,
        title: str,
        body: str = "",
        base: str = "main",
        head: str = None
    ):
        """Create a pull request"""
        import subprocess
        
        # Get current branch if not specified
        if not head:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True
            )
            head = result.stdout.decode().strip()
        
        # Push branch first
        subprocess.run(
            ["git", "push", "origin", head],
            cwd=repo_path,
            check=True
        )
        
        # Note: PR creation requires gh CLI or API
        # This is simplified - actual PR via create_pr tool


# Singleton clients
_github_client: Optional[GitHubClient] = None


def get_github_client(token: str = None) -> GitHubClient:
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient(token)
    return _github_client