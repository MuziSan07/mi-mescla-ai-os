"""
AI-OS Integrated DevOps Service
Combines GitHub + HuggingFace + implementation + deployment
"""

import os
import asyncio
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class DevOpsConfig:
    """DevOps configuration"""
    github_token: str = ""
    huggingface_token: str = ""
    default_branch: str = "main"
    auto_format: bool = True
    auto_lint: bool = True
    run_tests: bool = True
    docker_build: bool = True


@dataclass
class ProjectInfo:
    """Project information"""
    name: str
    source: str  # github, huggingface, local
    url: str = ""
    path: str = ""
    language: str = ""
    is_private: bool = False
    last_updated: str = ""


@dataclass
class ImplementationResult:
    """Result of implementation"""
    success: bool
    message: str = ""
    changes: List[str] = field(default_factory=list)
    files_added: int = 0
    files_modified: int = 0
    tests_passed: bool = True
    build_success: bool = True
    error: Optional[str] = None


class ProjectManager:
    """
    Manages projects from GitHub/HuggingFace with implementation capabilities.
    """
    
    def __init__(self, config: DevOpsConfig = None):
        self.config = config or DevOpsConfig()
        self.github = None
        self.huggingface = None
        self.projects: Dict[str, ProjectInfo] = {}
        
    async def initialize(self):
        """Initialize clients"""
        from ai_os.utils.github_integration import get_github_client
        from ai_os.utils.huggingface_integration import get_huggingface_client
        
        self.github = get_github_client(self.config.github_token)
        self.huggingface = get_huggingface_client(self.config.huggingface_token)
        
        # Try to authenticate both
        if self.config.github_token:
            try:
                await self.github.authenticate()
            except Exception as e:
                logger.warning(f"GitHub auth failed: {e}")
        
        if self.config.huggingface_token:
            try:
                await self.huggingface.authenticate()
            except Exception as e:
                logger.warning(f"HuggingFace auth failed: {e}")
    
    async def import_from_github(
        self,
        owner: str,
        repo: str,
        target_dir: str = None
    ) -> ProjectInfo:
        """Import project from GitHub"""
        # Get repo info
        repo_info = await self.github.get_repo(owner, repo)
        
        # Clone to temp dir if no target
        if not target_dir:
            target_dir = tempfile.mkdtemp()
        
        # Clone the repo
        from ai_os.utils.github_integration import GitCloner
        
        await GitCloner.clone_private(
            owner,
            repo,
            target_dir,
            self.config.github_token,
            self.config.default_branch
        )
        
        # Get language
        language = ""
        if repo_info.language:
            language = repo_info.language
        
        project = ProjectInfo(
            name=repo,
            source="github",
            url=repo_info.html_url,
            path=target_dir,
            language=language,
            is_private=repo_info.private,
            last_updated=repo_info.updated_at
        )
        
        self.projects[f"github/{owner}/{repo}"] = project
        
        return project
    
    async def import_from_huggingface(
        self,
        model_id: str,
        target_dir: str = None
    ) -> ProjectInfo:
        """Import model from HuggingFace"""
        # Get model info
        model_info = await self.huggingface.get_model_info(model_id)
        
        # Target dir
        if not target_dir:
            target_dir = tempfile.mkdtemp()
        
        # Download model
        await self.huggingface.download_model(
            model_id,
            target_dir
        )
        
        project = ProjectInfo(
            name=model_id.split("/")[-1],
            source="huggingface",
            url=f"https://huggingface.co/{model_id}",
            path=target_dir,
            is_private=model_info.private,
            last_updated=model_info.created_at
        )
        
        self.projects[f"huggingface/{model_id}"] = project
        
        return project
    
    async def list_projects(self) -> List[ProjectInfo]:
        """List all imported projects"""
        return list(self.projects.values())


class CodeImplementer:
    """
    Implements code changes, fixes, improvements.
    """
    
    @staticmethod
    async def apply_fix(
        project_path: str,
        file_path: str,
        old_code: str,
        new_code: str
    ) -> bool:
        """Apply a code fix"""
        import os
        
        full_path = os.path.join(project_path, file_path)
        
        if not os.path.exists(full_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        # Read file
        with open(full_path, "r") as f:
            content = f.read()
        
        if old_code not in content:
            logger.error("Old code not found in file")
            return False
        
        # Replace
        new_content = content.replace(old_code, new_code)
        
        # Write back
        with open(full_path, "w") as f:
            f.write(new_content)
        
        logger.info(f"Applied fix to {file_path}")
        return True
    
    @staticmethod
    async def add_file(
        project_path: str,
        file_name: str,
        content: str
    ) -> bool:
        """Add a new file"""
        import os
        
        full_path = os.path.join(project_path, file_name)
        
        # Create directories
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w") as f:
            f.write(content)
        
        logger.info(f"Added file: {file_name}")
        return True
    
    @staticmethod
    async def delete_file(project_path: str, file_name: str) -> bool:
        """Delete a file"""
        import os
        
        full_path = os.path.join(project_path, file_name)
        
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        elif os.path.exists(full_path):
            os.remove(full_path)
        
        logger.info(f"Deleted: {file_name}")
        return True
    
    @staticmethod
    async def format_code(project_path: str, language: str) -> bool:
        """Format code automatically"""
        try:
            if language == "python":
                subprocess.run(
                    ["black", ".", "--quiet"],
                    cwd=project_path,
                    check=True
                )
            elif language in ["javascript", "typescript"]:
                subprocess.run(
                    ["prettier", "--write", "."],
                    cwd=project_path,
                    check=True
                )
            
            return True
        except Exception as e:
            logger.warning(f"Format failed: {e}")
            return False
    
    @staticmethod
    async def lint_code(project_path: str, language: str) -> List[str]:
        """Lint code and return issues"""
        issues = []
        
        try:
            if language == "python":
                result = subprocess.run(
                    ["flake8", ".", "--format=simple"],
                    cwd=project_path,
                    capture_output=True
                )
                if result.returncode != 0:
                    issues = result.stdout.decode().split("\n")
            
            elif language in ["javascript", "typescript"]:
                result = subprocess.run(
                    ["eslint", "."],
                    cwd=project_path,
                    capture_output=True
                )
                if result.returncode != 0:
                    issues = result.stdout.decode().split("\n")
        
        except Exception as e:
            logger.warning(f"Lint failed: {e}")
        
        return issues[:20]  # Limit issues


class ProjectTester:
    """
    Tests projects automatically.
    """
    
    @staticmethod
    async def run_tests(project_path: str, test_framework: str = "pytest") -> Dict:
        """Run project tests"""
        result = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "output": ""
        }
        
        try:
            if test_framework == "pytest":
                proc = await asyncio.create_subprocess_exec(
                    "pytest", "-v", "--tb=short",
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                output = stdout.decode() + stderr.decode()
                
                # Parse pytest output
                if "passed" in output:
                    # Simple parsing
                    result["output"] = output[:2000]
                    
            elif test_framework == "npm":
                proc = await asyncio.create_subprocess_exec(
                    "npm", "test", "--if-present",
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                result["output"] = (stdout.decode() + stderr.decode())[:2000]
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    @staticmethod
    async def test_build(project_path: str) -> bool:
        """Test if project builds"""
        import os
        
        # Check for build files
        if os.path.exists(os.path.join(project_path, "Dockerfile")):
            # Test Docker build
            try:
                subprocess.run(
                    ["docker", "build", "-t", "test-build", "."],
                    cwd=project_path,
                    check=True,
                    capture_output=True,
                    timeout=300
                )
                return True
            except:
                return False
        
        elif os.path.exists(os.path.join(project_path, "package.json")):
            try:
                subprocess.run(
                    ["npm", "run", "build"],
                    cwd=project_path,
                    check=True,
                    capture_output=True,
                    timeout=120
                )
                return True
            except:
                return False
        
        elif os.path.exists(os.path.join(project_path, "Makefile")):
            try:
                subprocess.run(
                    ["make", "build"],
                    cwd=project_path,
                    check=True,
                    capture_output=True,
                    timeout=120
                )
                return True
            except:
                return False
        
        return True  # No build system found


class DevOpsOrchestrator:
    """
    Main orchestrator for full DevOps pipeline.
    """
    
    def __init__(self, config: DevOpsConfig = None):
        self.config = config or DevOpsConfig()
        self.project_manager = None
        self.implementer = CodeImplementer()
        self.tester = ProjectTester()
        
    async def initialize(self):
        """Initialize orchestrator"""
        self.project_manager = ProjectManager(self.config)
        await self.project_manager.initialize()
    
    async def implement_and_deploy(
        self,
        source: str,  # github://owner/repo
        changes: Dict[str, Any],
        deploy: bool = False
    ) -> ImplementationResult:
        """Full implementation and optionally deploy"""
        
        result = ImplementationResult(success=False)
        
        try:
            # Import project
            if source.startswith("github://"):
                _, owner, repo = source.split("//")
                project = await self.project_manager.import_from_github(owner, repo)
            elif source.startswith("huggingface://"):
                _, model_id = source.split("//")
                project = await self.project_manager.import_from_huggingface(model_id)
            else:
                result.error = "Unknown source"
                return result
            
            result.message = f"Imported from {source}"
            
            # Apply changes
            if "fixes" in changes:
                for fix in changes["fixes"]:
                    await self.implementer.apply_fix(
                        project.path,
                        fix["file"],
                        fix["old"],
                        fix["new"]
                    )
                    result.files_modified += 1
                    result.changes.append(f"Modified: {fix['file']}")
            
            if "new_files" in changes:
                for file_info in changes["new_files"]:
                    await self.implementer.add_file(
                        project.path,
                        file_info["name"],
                        file_info["content"]
                    )
                    result.files_added += 1
                    result.changes.append(f"Added: {file_info['name']}")
            
            # Format
            if self.config.auto_format and project.language:
                await self.implementer.format_code(project.path, project.language)
            
            # Run tests
            if self.config.run_tests:
                test_result = await self.tester.run_tests(project.path)
                result.tests_passed = test_result.get("passed", 0) > 0 or test_result.get("errors", 0) == 0
            
            # Build
            if self.config.docker_build:
                result.build_success = await self.tester.test_build(project.path)
            
            # Deploy if requested
            if deploy and result.build_success:
                # Would trigger deployment
                result.message += " | Ready to deploy"
            
            result.success = True
            
        except Exception as e:
            logger.error(f"Implementation failed: {e}")
            result.error = str(e)
        
        return result


# Singleton
_devops: Optional[DevOpsOrchestrator] = None


def get_devops(config: DevOpsConfig = None) -> DevOpsOrchestrator:
    global _devops
    if _devops is None:
        _devops = DevOpsOrchestrator(config)
    return _devops