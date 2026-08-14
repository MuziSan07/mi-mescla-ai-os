"""
AI-OS HuggingFace Integration
Manages HuggingFace sessions, models, datasets, Spaces
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class HuggingFaceSession:
    """HuggingFace authentication session"""
    token: str
    username: str = ""
    email: str = ""
    authenticated: bool = False


@dataclass
class HFModel:
    """HuggingFace model information"""
    id: str  # namespace/model
    modelId: str
    private: bool
    downloads: int = 0
    likes: int = 0
    tags: List[str] = []
    pipeline_tag: Optional[str] = None
    created_at: str = ""
    sha: str = ""
    

@dataclass
class HFSPACE:
    """HuggingFace Space information"""
    id: str
    title: str
    private: bool
    sdk: str  # streamlit, gradio, docker, static
    app_url: str
    created_at: str = ""


class HuggingFaceClient:
    """
    HuggingFace Hub API client.
    """
    
    BASE_URL = "https://huggingface.co/api"
    HF_URL = "https://huggingface.co"
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("HUGGING_FACE_TOKEN")
        self.authenticated = False
        self.username = ""
        
    async def authenticate(self, token: str = None) -> bool:
        """
        Authenticate with HuggingFace.
        """
        import httpx
        
        self.token = token or self.token
        
        if not self.token:
            raise ValueError("No HuggingFace token provided")
        
        # Get whoami
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.HF_URL}/api/whoami-v2",
                headers=headers
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.username = data.get("name", "")
                self.authenticated = True
                
                self.session = HuggingFaceSession(
                    token=self.token,
                    username=self.username,
                    email=data.get("email", ""),
                    authenticated=True
                )
                
                logger.info(f"Authenticated on HuggingFace as {self.username}")
                return True
            
            return False
    
    async def list_models(
        self,
        filter: str = None,
        limit: int = 100
    ) -> List[HFModel]:
        """List models"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        params = {"limit": limit}
        
        async with httpx.AsyncClient() as client:
            if self.authenticated:
                resp = await client.get(
                    f"{self.BASE_URL}/users/{self.username}/models",
                    headers=headers,
                    params={"limit": limit}
                )
            else:
                # Public models
                resp = await client.get(
                    f"{self.BASE_URL}/models",
                    headers=headers,
                    params=params
                )
            
            resp.raise_for_status()
            data = resp.json()
            
            models = []
            for m in data:
                models.append(HFModel(
                    id=m.get("id", ""),
                    modelId=m.get("modelId", ""),
                    private=m.get("private", False),
                    downloads=m.get("downloads", 0),
                    likes=m.get("likes", 0),
                    tags=m.get("tags", []),
                    pipeline_tag=m.get("pipeline_tag"),
                    created_at=m.get("createdAt", ""),
                    sha=m.get("sha", "")
                ))
            
            return models
    
    async def get_model_info(self, model_id: str) -> HFModel:
        """Get model information"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/models/{model_id}",
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            
            return HFModel(
                id=data.get("id", ""),
                modelId=data.get("modelId", ""),
                private=data.get("private", False),
                downloads=data.get("downloads", 0),
                likes=data.get("likes", 0),
                tags=data.get("tags", []),
                pipeline_tag=data.get("pipeline_tag"),
                created_at=data.get("createdAt", ""),
                sha=data.get("sha", "")
            )
    
    async def create_model_repo(
        self,
        name: str,
        private: bool = False,
        license: str = None
    ) -> Dict:
        """Create a model repository"""
        import httpx
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "name": name,
            "private": private,
            "license": license
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/models/{self.username}/{name}",
                headers=headers,
                json=data
            )
            resp.raise_for_status()
            return resp.json()
    
    async def delete_model_repo(self, model_id: str):
        """Delete a model repository"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.BASE_URL}/models/{model_id}",
                headers=headers
            )
            resp.raise_for_status()
    
    async def upload_file(
        self,
        model_id: str,
        file_path: str,
        path_in_repo: str,
        commit_message: str = "Upload file"
    ):
        """Upload a file to model repo"""
        import httpx
        
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        
        # This is simplified - actual upload uses hf_hub
        # For full implementation, use huggingface_hub library
        
        files = {"file": open(file_path, "rb")}
        
        data = {
            "pathInRepo": path_in_repo,
            "title": commit_message
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.HF_URL}/api/models/{model_id}/upload/main",
                headers=headers,
                files=files,
                data=data
            )
            resp.raise_for_status()
            return resp.json()
    
    async def download_model(
        self,
        model_id: str,
        target_dir: str,
        revision: str = "main"
    ):
        """Download a model"""
        import subprocess
        
        # Use huggingface-cli or git
        cmd = [
            "huggingface-cli", "download",
            model_id,
            "--local-dir", target_dir
        ]
        
        if revision:
            cmd.extend(["--revision", revision])
        
        subprocess.run(cmd, check=True)
    
    async def list_spaces(self, limit: int = 100) -> List[HFSPACE]:
        """List spaces"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            if self.authenticated:
                resp = await client.get(
                    f"{self.BASE_URL}/users/{self.username}/spaces",
                    headers=headers,
                    params={"limit": limit}
                )
            else:
                resp = await client.get(
                    f"{self.BASE_URL}/spaces",
                    headers=headers,
                    params={"limit": limit}
                )
            
            resp.raise_for_status()
            data = resp.json()
            
            spaces = []
            for s in data:
                spaces.append(HFSPACE(
                    id=s.get("id", ""),
                    title=s.get("title", ""),
                    private=s.get("private", False),
                    sdk=s.get("sdk", ""),
                    app_url=s.get("appUrl", ""),
                    created_at=s.get("createdAt", "")
                ))
            
            return spaces
    
    async def create_space(
        self,
        name: str,
        sdk: str = "gradio",
        private: bool = False,
        title: str = None
    ) -> HFSPACE:
        """Create a Space"""
        import httpx
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "name": name,
            "sdk": sdk,
            "private": private,
            "title": title or name
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/spaces/{self.username}/{name}",
                headers=headers,
                json=data
            )
            resp.raise_for_status()
            space_data = resp.json()
            
            return HFSPACE(
                id=space_data.get("id", ""),
                title=space_data.get("title", ""),
                private=space_data.get("private", False),
                sdk=space_data.get("sdk", ""),
                app_url=space_data.get("appUrl", ""),
                created_at=space_data.get("createdAt", "")
            )
    
    async def start_space(self, space_id: str):
        """Start a Space (resume from paused)"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/api/spaces/{space_id}/runtime",
                headers=headers,
                json={"state": "started"}
            )
            resp.raise_for_status()
    
    async def pause_space(self, space_id: str):
        """Pause a Space"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/api/spaces/{space_id}/runtime",
                headers=headers,
                json={"state": "paused"}
            )
            resp.raise_for_status()
    
    async def get_space_logs(self, space_id: str) -> str:
        """Get Space logs"""
        import httpx
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.HF_URL}/api/spaces/{space_id}/logs",
                headers=headers
            )
            resp.raise_for_status()
            return resp.text


# Singleton
_hf_client: Optional[HuggingFaceClient] = None


def get_huggingface_client(token: str = None) -> HuggingFaceClient:
    global _hf_client
    if _hf_client is None:
        _hf_client = HuggingFaceClient(token)
    return _hf_client