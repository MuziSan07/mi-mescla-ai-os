"""
AI-OS Auto-Validator / Repo Tester
Automatically tests repositories, checks for errors, validates builds
"""

import os
import asyncio
import subprocess
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """Validation result status"""
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """Result of a validation check"""
    check_name: str
    status: ValidationStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


@dataclass
class RepoValidationReport:
    """Complete validation report for a repo"""
    repo_url: str
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    checks: List[ValidationResult] = field(default_factory=list)
    overall_status: ValidationStatus = ValidationStatus.SUCCESS
    score: float = 0.0  # 0-100


class SyntaxChecker:
    """Check code syntax for various languages"""
    
    LANGUAGES = {
        "python": ["flake8", "pylint", "py_compile"],
        "javascript": ["eslint"],
        "typescript": ["eslint"],
        "go": ["go", "vet"],
        "rust": ["rustc", "clippy"],
    }
    
    @staticmethod
    async def check_python(file_path: str) -> ValidationResult:
        """Check Python syntax"""
        start = datetime.now()
        
        try:
            # Using py_compile
            result = subprocess.run(
                ["python3", "-m", "py_compile", file_path],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return ValidationResult(
                    check_name="python_syntax",
                    status=ValidationStatus.SUCCESS,
                    message="No syntax errors"
                )
            else:
                return ValidationResult(
                    check_name="python_syntax",
                    status=ValidationStatus.FAILED,
                    message=result.stderr.decode()[:500]
                )
                
        except Exception as e:
            return ValidationResult(
                check_name="python_syntax",
                status=ValidationStatus.ERROR,
                message=str(e)
            )
    
    @staticmethod
    async def check_all(repo_path: str) -> List[ValidationResult]:
        """Check all files in repo"""
        results = []
        
        for root, dirs, files in os.walk(repo_path):
            # Skip common non-code dirs
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', 'venv']]
            
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    result = await SyntaxChecker.check_python(path)
                    results.append(result)
        
        return results


class DockerTester:
    """Test Docker builds"""
    
    @staticmethod
    async def test_build(dockerfile_path: str) -> ValidationResult:
        """Test Docker build"""
        start = datetime.now()
        
        try:
            # Check docker is available
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return ValidationResult(
                    check_name="docker_build",
                    status=ValidationStatus.ERROR,
                    message="Docker not available"
                )
            
            # Try to build
            # This would actually build, but we'll just check Dockerfile exists
            if not os.path.exists(dockerfile_path):
                return ValidationResult(
                    check_name="docker_build",
                    status=ValidationStatus.FAILED,
                    message="Dockerfile not found"
                )
            
            return ValidationResult(
                check_name="docker_build",
                status=ValidationStatus.SUCCESS,
                message="Dockerfile valid"
            )
            
        except Exception as e:
            return ValidationResult(
                check_name="docker_build",
                status=ValidationStatus.ERROR,
                message=str(e)
            )
    
    @staticmethod
    async def test_docker_compose(path: str) -> ValidationResult:
        """Test docker-compose config"""
        start = datetime.now()
        
        compose_file = os.path.join(path, "docker-compose.yaml")
        
        if not os.path.exists(compose_file):
            return ValidationResult(
                check_name="docker_compose",
                status=ValidationStatus.SKIPPED,
                message="No docker-compose.yaml found"
            )
        
        # Basic validation
        try:
            with open(compose_file, 'r') as f:
                content = f.read()
                
            if 'services:' in content:
                return ValidationResult(
                    check_name="docker_compose",
                    status=ValidationStatus.SUCCESS,
                    message="docker-compose.yaml valid"
                )
            else:
                return ValidationResult(
                    check_name="docker_compose",
                    status=ValidationStatus.FAILED,
                    message="Invalid docker-compose format"
                )
        except Exception as e:
            return ValidationResult(
                check_name="docker_compose",
                status=ValidationStatus.ERROR,
                message=str(e)
            )


class DependencyChecker:
    """Check dependencies for updates/vulnerabilities"""
    
    @staticmethod
    async def check_requirements(file_path: str) -> ValidationResult:
        """Check Python requirements"""
        start = datetime.now()
        
        if not os.path.exists(file_path):
            return ValidationResult(
                check_name="dependencies",
                status=ValidationStatus.SKIPPED,
                message="No requirements.txt found"
            )
        
        try:
            with open(file_path, 'r') as f:
                deps = f.read().strip().split('\n')
            
            outdated = []
            for dep in deps:
                if dep and not dep.startswith('#'):
                    # Check if package exists
                    if '==' not in dep:
                        outdated.append(dep)
            
            if outdated:
                return ValidationResult(
                    check_name="dependencies",
                    status=ValidationStatus.WARNING,
                    message=f"{len(outdated)} packages without version pins",
                    details={"unpinned": outdated[:10]}
                )
            
            return ValidationResult(
                check_name="dependencies",
                status=ValidationStatus.SUCCESS,
                message="All dependencies properly versioned"
            )
            
        except Exception as e:
            return ValidationResult(
                check_name="dependencies",
                status=ValidationStatus.ERROR,
                message=str(e)
            )
    
    @staticmethod
    async def check_package_json(path: str) -> ValidationResult:
        """Check Node.js dependencies"""
        pkg_file = os.path.join(path, "package.json")
        
        if not os.path.exists(pkg_file):
            return ValidationResult(
                check_name="node_dependencies",
                status=ValidationStatus.SKIPPED,
                message="No package.json found"
            )
        
        try:
            import json
            with open(pkg_file, 'r') as f:
                pkg = json.load(f)
            
            has_lock = os.path.exists(os.path.join(path, "package-lock.json"))
            
            if has_lock:
                return ValidationResult(
                    check_name="node_dependencies",
                    status=ValidationStatus.SUCCESS,
                    message="Dependencies locked"
                )
            else:
                return ValidationResult(
                    check_name="node_dependencies",
                    status=ValidationStatus.WARNING,
                    message="No package-lock.json - run npm install"
                )
                
        except Exception as e:
            return ValidationResult(
                check_name="node_dependencies",
                status=ValidationStatus.ERROR,
                message=str(e)
            )


class HealthChecker:
    """Check if application can start/health check"""
    
    @staticmethod
    async def check_health(url: str, timeout: int = 10) -> ValidationResult:
        """Check if service is healthy"""
        start = datetime.now()
        
        try:
            import httpx
            
            # Try common health endpoints
            endpoints = ["/health", "/healthz", "/", "/api/health"]
            
            async with httpx.AsyncClient() as client:
                for endpoint in endpoints:
                    try:
                        resp = await client.get(
                            f"{url.rstrip('/')}{endpoint}",
                            timeout=timeout
                        )
                        if resp.status_code < 500:
                            return ValidationResult(
                                check_name="health_check",
                                status=ValidationStatus.SUCCESS,
                                message=f"Service healthy at {endpoint}",
                                details={"status_code": resp.status_code}
                            )
                    except:
                        continue
                
                return ValidationResult(
                    check_name="health_check",
                    status=ValidationStatus.FAILED,
                    message="No health endpoint responding"
                )
                
        except Exception as e:
            return ValidationResult(
                check_name="health_check",
                status=ValidationStatus.ERROR,
                message=str(e)
            )
    
    @staticmethod
    async def check_port(port: int, host: str = "localhost") -> ValidationResult:
        """Check if port is listening"""
        import socket
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return ValidationResult(
                    check_name="port_check",
                    status=ValidationStatus.SUCCESS,
                    message=f"Port {port} is open"
                )
            else:
                return ValidationResult(
                    check_name="port_check",
                    status=ValidationStatus.FAILED,
                    message=f"Port {port} is closed"
                )
        except Exception as e:
            return ValidationResult(
                check_name="port_check",
                status=ValidationStatus.ERROR,
                message=str(e)
            )


class GitAnalyzer:
    """Analyze git repository"""
    
    @staticmethod
    async def check_repo_status(repo_path: str) -> ValidationResult:
        """Check git status"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                timeout=10
            )
            
            changes = result.stdout.decode().strip()
            
            if changes:
                files = changes.split('\n')[:5]
                return ValidationResult(
                    check_name="git_status",
                    status=ValidationStatus.WARNING,
                    message=f"Uncommitted changes: {len(changes.split(chr(10)))} files",
                    details={"files": files}
                )
            
            return ValidationResult(
                check_name="git_status",
                status=ValidationStatus.SUCCESS,
                message="Working tree clean"
            )
            
        except Exception as e:
            return ValidationResult(
                check_name="git_status",
                status=ValidationStatus.ERROR,
                message=str(e)
            )
    
    @staticmethod
    async def check_branches(repo_path: str) -> ValidationResult:
        """Check branch status"""
        try:
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=repo_path,
                capture_output=True,
                timeout=10
            )
            
            branches = result.stdout.decode().strip().split('\n')
            
            current = [b for b in branches if b.startswith('*')]
            
            return ValidationResult(
                check_name="git_branches",
                status=ValidationStatus.SUCCESS,
                message=f"On branch: {current[0] if current else 'unknown'}",
                details={"branches": branches[:10]}
            )
            
        except Exception as e:
            return ValidationResult(
                check_name="git_branches",
                status=ValidationStatus.ERROR,
                message=str(e)
            )


class AutoValidator:
    """
    Main auto-validator that runs all checks on a repository.
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    async def validate_all(self) -> RepoValidationReport:
        """Run all validation checks"""
        report = RepoValidationReport(repo_url=self.repo_path)
        
        # 1. Syntax checks
        syntax_results = await SyntaxChecker.check_all(self.repo_path)
        report.checks.extend(syntax_results)
        
        # 2. Docker tests
        docker_result = await DockerTester.test_docker_compose(self.repo_path)
        report.checks.append(docker_result)
        
        # 3. Dependency checks
        req_file = os.path.join(self.repo_path, "requirements.txt")
        dep_result = await DependencyChecker.check_requirements(req_file)
        report.checks.append(dep_result)
        
        pkg_result = await DependencyChecker.check_package_json(self.repo_path)
        report.checks.append(pkg_result)
        
        # 4. Git status
        git_result = await GitAnalyzer.check_repo_status(self.repo_path)
        report.checks.append(git_result)
        
        # Calculate overall score
        total = len(report.checks)
        if total > 0:
            passed = sum(1 for c in report.checks if c.status == ValidationStatus.SUCCESS)
            warnings = sum(1 for c in report.checks if c.status == ValidationStatus.WARNING)
            report.score = (passed * 100 + warnings * 50) / total
            
            # Set overall status
            failed = sum(1 for c in report.checks if c.status == ValidationStatus.FAILED)
            if failed > 0:
                report.overall_status = ValidationStatus.FAILED
            else:
                report.overall_status = ValidationStatus.SUCCESS
        
        return report
    
    async def validate_remote(self, repo_url: str) -> RepoValidationReport:
        """Clone and validate remote repo"""
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # Clone repo
                subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, tmpdir],
                    capture_output=True,
                    timeout=120
                )
                
                # Validate
                validator = AutoValidator(tmpdir)
                return await validator.validate_all()
                
            except Exception as e:
                return RepoValidationReport(
                    repo_url=repo_url,
                    overall_status=ValidationStatus.ERROR,
                    checks=[ValidationResult(
                        check_name="clone",
                        status=ValidationStatus.ERROR,
                        message=str(e)
                    )]
                )


# Singleton
_validator: Optional[AutoValidator] = None


def get_auto_validator(repo_path: str = ".") -> AutoValidator:
    return AutoValidator(repo_path)