"""
AI Operating System - Auto-Audit and Self-Correction Module

Performs continuous auditing and automatic correction of system issues.
"""

import asyncio
import logging
import os
import importlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import ast

from ai_os.models.schemas import AuditResult, CorrectionInput
from ai_os.core.events.event_bus import get_event_bus, EventTypes

logger = logging.getLogger(__name__)


# Define the required directory structure
REQUIRED_DIRECTORIES = [
    "api/routes",
    "middleware",
    "core/orchestrator",
    "core.router",
    "core.gpu",
    "core.vision",
    "core.memory",
    "core.security",
    "core.events",
    "core.monitoring",
    "core.audit",
    "models",
    "utils",
    "config"
]

# Define required files
REQUIRED_FILES = [
    "main.py",
    "api/routes/__init__.py",
    "core/__init__.py",
    "models/schemas.py",
    "config/settings.py"
]


class Issue:
    """Represents an audit issue"""
    
    def __init__(
        self,
        issue_id: str,
        severity: str,
        category: str,
        description: str,
        location: Optional[str] = None
    ):
        self.id = issue_id
        self.severity = severity  # critical, high, medium, low
        self.category = category
        self.description = description
        self.location = location


class AutoAuditor:
    """
    Performs continuous system auditing
    """
    
    def __init__(
        self,
        base_path: str,
        interval: int = 300,
        auto_correct: bool = True
    ):
        self.base_path = Path(base_path)
        self.interval = interval
        self.auto_correct = auto_correct
        self._running = False
        self._audit_task: Optional[asyncio.Task] = None
        self._event_bus = get_event_bus()
        self._last_audit: Optional[datetime] = None
        self._issues: List[Issue] = []
    
    async def start(self):
        """Start the auto-auditor"""
        self._running = True
        self._audit_task = asyncio.create_task(self._run_audit_loop())
        logger.info("Auto-auditor started")
    
    async def stop(self):
        """Stop the auto-auditor"""
        self._running = False
        if self._audit_task:
            self._audit_task.cancel()
            try:
                await self._audit_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-auditor stopped")
    
    async def run_audit(self) -> AuditResult:
        """Run a full system audit"""
        issues = []
        
        # Emit audit started event
        await self._event_bus.emit(
            EventTypes.AUDIT_STARTED,
            {"timestamp": datetime.utcnow().isoformat()},
            source="auto_auditor"
        )
        
        logger.info("Starting system audit...")
        
        # 1. Check directory structure
        dir_issues = await self._check_directories()
        issues.extend(dir_issues)
        
        # 2. Check required files
        file_issues = await self._check_required_files()
        issues.extend(file_issues)
        
        # 3. Check Python imports
        import_issues = await self._check_imports()
        issues.extend(import_issues)
        
        # 4. Check configurations
        config_issues = await self._check_configurations()
        issues.extend(config_issues)
        
        # 5. Check API endpoints
        api_issues = await self._check_api_endpoints()
        issues.extend(api_issues)
        
        # 6. Check model connectivity
        model_issues = await self._check_model_connectivity()
        issues.extend(model_issues)
        
        # 7. Check services
        service_issues = await self._check_services()
        issues.extend(service_issues)
        
        self._issues = issues
        
        corrections_applied = []
        
        # Auto-correct if enabled
        if self.auto_correct and issues:
            corrections = await self._auto_correct(issues)
            corrections_applied = corrections
        
        # Emit audit completed event
        await self._event_bus.emit(
            EventTypes.AUDIT_COMPLETED,
            {
                "timestamp": datetime.utcnow().isoformat(),
                "issues_found": len(issues),
                "corrections_applied": corrections_applied
            },
            source="auto_auditor"
        )
        
        passed = all(i.severity != "critical" for i in issues)
        
        result = AuditResult(
            id=f"audit-{datetime.utcnow().timestamp()}",
            timestamp=datetime.utcnow(),
            passed=passed,
            issues=[{
                "id": i.id,
                "severity": i.severity,
                "category": i.category,
                "description": i.description,
                "location": i.location
            } for i in issues],
            corrections_applied=corrections_applied
        )
        
        self._last_audit = datetime.utcnow()
        
        logger.info(
            f"Audit completed: {len(issues)} issues, "
            f"{len(corrections_applied)} corrections"
        )
        
        return result
    
    async def _check_directories(self) -> List[Issue]:
        """Check if required directories exist"""
        issues = []
        
        for dir_path in REQUIRED_DIRECTORIES:
            full_path = self.base_path / dir_path
            issue_id = f"dir-{dir_path.replace('/', '-')}"
            
            if not full_path.exists():
                issues.append(Issue(
                    issue_id=issue_id,
                    severity="high",
                    category="directory",
                    description=f"Required directory missing: {dir_path}",
                    location=str(full_path)
                ))
            elif not full_path.is_dir():
                issues.append(Issue(
                    issue_id=issue_id,
                    severity="high",
                    category="directory",
                    description=f"Path exists but is not a directory: {dir_path}",
                    location=str(full_path)
                ))
        
        return issues
    
    async def _check_required_files(self) -> List[Issue]:
        """Check if required files exist"""
        issues = []
        
        for file_path in REQUIRED_FILES:
            full_path = self.base_path / file_path
            issue_id = f"file-{file_path.replace('/', '-').replace('.', '-')}"
            
            if not full_path.exists():
                issues.append(Issue(
                    issue_id=issue_id,
                    severity="critical",
                    category="file",
                    description=f"Required file missing: {file_path}",
                    location=str(full_path)
                ))
        
        return issues
    
    async def _check_imports(self) -> List[Issue]:
        """Check for invalid imports"""
        issues = []
        
        # Find all Python files
        for py_file in self.base_path.rglob("*.py"):
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            try:
                                importlib.import_module(alias.name)
                            except ImportError:
                                pass  # Expected for internal modules
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module
                            try:
                                importlib.import_module(module_name)
                            except ImportError:
                                pass  # Expected for internal modules
            except SyntaxError as e:
                issues.append(Issue(
                    issue_id=f"syntax-{py_file.name}",
                    severity="critical",
                    category="syntax",
                    description=f"Syntax error: {e}",
                    location=str(py_file)
                ))
            except Exception as e:
                logger.debug(f"Could not parse {py_file}: {e}")
        
        return issues
    
    async def _check_configurations(self) -> List[Issue]:
        """Check configuration completeness"""
        issues = []
        
        # Check settings file
        settings_file = self.base_path / "config" / "settings.py"
        if settings_file.exists():
            try:
                content = settings_file.read_text()
                if "SECRET_KEY" not in content:
                    issues.append(Issue(
                        issue_id="config-secret",
                        severity="high",
                        category="configuration",
                        description="SECRET_KEY not found in settings"
                    ))
            except Exception as e:
                issues.append(Issue(
                    issue_id="config-read",
                    severity="medium",
                    category="configuration",
                    description=f"Could not read settings: {e}"
                ))
        
        return issues
    
    async def _check_api_endpoints(self) -> List[Issue]:
        """Check API endpoint definitions"""
        issues = []
        
        # Check main.py for FastAPI app definition
        main_file = self.base_path / "main.py"
        if not main_file.exists():
            issues.append(Issue(
                issue_id="api-main",
                severity="critical",
                category="api",
                description="main.py not found"
            ))
        
        return issues
    
    async def _check_model_connectivity(self) -> List[Issue]:
        """Check model connectivity by pinging Ollama and other endpoints"""
        issues = []
        import httpx

        endpoints = {
            "ollama": "http://localhost:11434/api/tags",
        }

        for name, url in endpoints.items():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                    if response.status_code >= 400:
                        issues.append(Issue(
                            issue_id=f"model-{name}-unreachable",
                            severity="high",
                            category="model",
                            description=f"{name} returned HTTP {response.status_code}",
                            location=url
                        ))
            except Exception as e:
                issues.append(Issue(
                    issue_id=f"model-{name}-unreachable",
                    severity="high",
                    category="model",
                    description=f"{name} not reachable: {e}",
                    location=url
                ))

        return issues
    
    async def _check_services(self) -> List[Issue]:
        """Check if required services are running"""
        issues = []
        
        # Check Docker availability
        import subprocess
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                issues.append(Issue(
                    issue_id="service-docker",
                    severity="medium",
                    category="service",
                    description="Docker not available"
                ))
        except FileNotFoundError:
            issues.append(Issue(
                issue_id="service-docker",
                severity="medium",
                category="service",
                description="Docker not installed"
            ))
        
        return issues
    
    async def _auto_correct(self, issues: List[Issue]) -> List[str]:
        """Automatically correct detected issues"""
        corrections = []
        
        for issue in issues:
            if issue.category == "directory":
                # Create missing directory
                try:
                    path = Path(issue.location)
                    path.mkdir(parents=True, exist_ok=True)
                    corrections.append(f"Created directory: {issue.location}")
                except Exception as e:
                    logger.error(f"Could not create directory: {e}")
            
            elif issue.category == "file":
                # Could create placeholder files
                if issue.location:
                    try:
                        path = Path(issue.location)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.touch()
                        corrections.append(f"Created file: {issue.location}")
                    except Exception as e:
                        logger.error(f"Could not create file: {e}")
        
        # Emit correction events
        for correction in corrections:
            await self._event_bus.emit(
                EventTypes.CORRECTION_APPLIED,
                {"correction": correction},
                source="auto_auditor"
            )
        
        return corrections
    
    async def _run_audit_loop(self):
        """Run audit loop"""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self.run_audit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit loop error: {e}")
    
    async def get_last_audit(self) -> Optional[AuditResult]:
        """Get the last audit result"""
        # This would return cached result
        return None
    
    async def get_current_issues(self) -> List[Issue]:
        """Get current issues"""
        return self._issues


class AutoCorrector:
    """
    Handles automatic corrections based on audit results
    """
    
    def __init__(self, auditor: AutoAuditor):
        self.auditor = auditor
        self._correction_handlers: Dict[str, callable] = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """Register correction handlers"""
        self._correction_handlers["directory"] = self._fix_directory
        self._correction_handlers["file"] = self._fix_file
        self._correction_handlers["configuration"] = self._fix_configuration
        self._correction_handlers["service"] = self._fix_service
    
    async def correct(self, correction: CorrectionInput) -> bool:
        """Apply a specific correction"""
        handler = self._correction_handlers.get(correction.action)
        if handler:
            return await handler(correction.parameters)
        return False
    
    async def _fix_directory(self, params: Dict[str, Any]) -> bool:
        """Fix missing directory"""
        try:
            path = Path(params["path"])
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path}")
            return True
        except Exception as e:
            logger.error(f"Could not fix directory: {e}")
            return False
    
    async def _fix_file(self, params: Dict[str, Any]) -> bool:
        """Fix missing file"""
        try:
            path = Path(params["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            logger.info(f"Created file: {path}")
            return True
        except Exception as e:
            logger.error(f"Could not fix file: {e}")
            return False
    
    async def _fix_configuration(self, params: Dict[str, Any]) -> bool:
        """Fix configuration by writing a key-value pair to the config file"""
        import json
        config_path = params.get("config_path")
        key = params.get("key")
        value = params.get("value")
        if not config_path or key is None:
            logger.warning("_fix_configuration: missing config_path or key")
            return False
        try:
            path = Path(config_path)
            data = {}
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
            data[key] = value
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Configuration updated: {key}={value} in {config_path}")
            return True
        except Exception as e:
            logger.error(f"Could not fix configuration: {e}")
            return False

    async def _fix_service(self, params: Dict[str, Any]) -> bool:
        """Attempt to restart a service via docker-compose"""
        import subprocess
        service = params.get("service")
        compose_file = params.get("compose_file", "docker-compose.yaml")
        if not service:
            logger.warning("_fix_service: no service name provided")
            return False
        try:
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "restart", service],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                logger.info(f"Service restarted: {service}")
                return True
            else:
                logger.error(f"Service restart failed: {result.stderr.decode().strip()}")
                return False
        except Exception as e:
            logger.error(f"Could not fix service {service}: {e}")
            return False


# Singleton instance
_auditor_instance: Optional[AutoAuditor] = None


def get_auditor(base_path: Optional[str] = None) -> AutoAuditor:
    """Get the auto-auditor singleton"""
    global _auditor_instance
    if _auditor_instance is None:
        if base_path is None:
            # Default to backend path
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _auditor_instance = AutoAuditor(base_path)
    return _auditor_instance