"""
AI-OS Source Code Integration API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/source", tags=["source"])


class GitHubLoginRequest(BaseModel):
    """GitHub login request"""
    token: str


class CloneRequest(BaseModel):
    """Clone repository request"""
    owner: str
    repo: str
    branch: str = "main"


class HuggingFaceLoginRequest(BaseModel):
    """HuggingFace login request"""
    token: str


class DownloadModelRequest(BaseModel):
    """Download model request"""
    model_id: str


@router.post("/github/login")
async def github_login(request: GitHubLoginRequest,
    user: TokenData = Depends(require_auth)
):
    """Authenticate with GitHub"""
    from ai_os.utils.github_integration import get_github_client
    
    try:
        client = get_github_client(request.token)
        success = await client.authenticate()
        
        if success:
            return {
                "status": "authenticated",
                "username": client.username
            }
        else:
            raise HTTPException(status_code=401, detail="Authentication failed")
            
    except Exception as e:
        logger.error(f"GitHub login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/repos")
async def github_list_repos(private_only: bool = False,
    user: TokenData = Depends(require_auth)
):
    """List GitHub repositories"""
    from ai_os.utils.github_integration import get_github_client
    
    try:
        client = get_github_client()
        repos = await client.list_repos(private_only)
        
        return {
            "repos": [
                {
                    "name": r.name,
                    "full_name": r.full_name,
                    "private": r.private,
                    "url": r.html_url,
                    "language": r.language,
                    "stars": r.stars
                }
                for r in repos
            ]
        }
        
    except Exception as e:
        logger.error(f"List repos error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/repos/{owner}/{repo}")
async def github_get_repo(owner: str, repo: str,
    user: TokenData = Depends(require_auth)
):
    """Get repository info"""
    from ai_os.utils.github_integration import get_github_client
    
    try:
        client = get_github_client()
        r = await client.get_repo(owner, repo)
        
        return {
            "name": r.name,
            "full_name": r.full_name,
            "private": r.private,
            "url": r.html_url,
            "description": r.description,
            "language": r.language,
            "stars": r.stars,
            "forks": r.forks,
            "default_branch": r.default_branch
        }
        
    except Exception as e:
        logger.error(f"Get repo error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/github/clone")
async def github_clone(request: CloneRequest,
    user: TokenData = Depends(require_auth)
):
    """Clone a GitHub repository"""
    from ai_os.utils.github_integration import get_github_client, GitCloner
    import tempfile
    
    try:
        client = get_github_client()
        token = client.token
        
        with tempfile.TemporaryDirectory() as target_dir:
            await GitCloner.clone_private(
                request.owner,
                request.repo,
                target_dir,
                token,
                request.branch
            )
            
            return {
                "status": "cloned",
                "path": target_dir,
                "repo": f"{request.owner}/{request.repo}"
            }
        
    except Exception as e:
        logger.error(f"Clone error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/commits/{owner}/{repo}")
async def github_commits(owner: str, repo: str, limit: int = 10,
    user: TokenData = Depends(require_auth)
):
    """Get repository commits"""
    from ai_os.utils.github_integration import get_github_client
    
    try:
        client = get_github_client()
        commits = await client.get_commits(owner, repo, limit)
        
        return {
            "commits": [
                {
                    "sha": c.sha[:7],
                    "message": c.message[:100],
                    "author": c.author,
                    "date": c.date
                }
                for c in commits
            ]
        }
        
    except Exception as e:
        logger.error(f"Commits error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/huggingface/login")
async def huggingface_login(request: HuggingFaceLoginRequest,
    user: TokenData = Depends(require_auth)
):
    """Authenticate with HuggingFace"""
    from ai_os.utils.huggingface_integration import get_huggingface_client
    
    try:
        client = get_huggingface_client(request.token)
        success = await client.authenticate()
        
        if success:
            return {
                "status": "authenticated",
                "username": client.username
            }
        else:
            raise HTTPException(status_code=401, detail="Authentication failed")
            
    except Exception as e:
        logger.error(f"HuggingFace login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/huggingface/models")
async def huggingface_list_models(limit: int = 50,
    user: TokenData = Depends(require_auth)
):
    """List HuggingFace models"""
    from ai_os.utils.huggingface_integration import get_huggingface_client
    
    try:
        client = get_huggingface_client()
        models = await client.list_models(limit=limit)
        
        return {
            "models": [
                {
                    "id": m.id,
                    "downloads": m.downloads,
                    "likes": m.likes,
                    "private": m.private
                }
                for m in models
            ]
        }
        
    except Exception as e:
        logger.error(f"List models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/huggingface/download")
async def huggingface_download(request: DownloadModelRequest,
    user: TokenData = Depends(require_auth)
):
    """Download model from HuggingFace"""
    from ai_os.utils.huggingface_integration import get_huggingface_client
    import tempfile
    
    try:
        client = get_huggingface_client()
        
        with tempfile.TemporaryDirectory() as target_dir:
            await client.download_model(request.model_id, target_dir)
            
            return {
                "status": "downloaded",
                "path": target_dir,
                "model": request.model_id
            }
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def source_health(user: TokenData = Depends(require_auth)):
    """Source integration health check"""
    return {"status": "healthy"}