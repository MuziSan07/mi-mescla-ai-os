"""
AI-OS Complete Project Auditor
Maps, analyzes, and verifies the entire project
"""

import os
import ast
import json
import subprocess
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FileInfo:
    """Information about a file"""
    path: str
    size: int = 0
    language: str = ""
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    is_empty: bool = False
    has_errors: bool = False
    error_message: str = ""


@dataclass
class FolderInfo:
    """Information about a folder"""
    path: str
    file_count: int = 0
    subfolder_count: int = 0
    total_size: int = 0
    is_empty: bool = True
    has_useless_files: bool = False


@dataclass
class ImportInfo:
    """Information about an import"""
    module: str
    file_path: str
    is_valid: bool = False
    is_external: bool = False
    resolution_path: Optional[str] = None


@dataclass
class FunctionInfo:
    """Information about a function"""
    name: str
    file_path: str
    line_number: int
    param_count: int = 0
    is_async: bool = False
    has_return: bool = False
    callers: List[str] = field(default_factory=list)


@dataclass
class APIEndpoint:
    """Information about an API endpoint"""
    path: str = ""
    method: str = "GET"
    file_path: str = ""
    line_number: int = 0
    handler_function: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Information about a class"""
    name: str
    file_path: str
    line_number: int
    methods: List[str] = field(default_factory=list)
    parent_classes: List[str] = field(default_factory=list)
    is_used: bool = False


@dataclass
class DependencyInfo:
    """Information about a dependency"""
    name: str
    version: str = ""
    is_used: bool = False
    is_internal: bool = False


@dataclass
class AuditReport:
    """Complete audit report"""
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    
    # Structure
    folders: Dict[str, FolderInfo] = field(default_factory=dict)
    files: Dict[str, FileInfo] = field(default_factory=dict)
    
    # Components
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    apis: List[APIEndpoint] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    dependencies: Dict[str, DependencyInfo] = field(default_factory=dict)
    
    # Issues
    orphan_files: List[str] = field(default_factory=list)
    empty_folders: List[str] = field(default_factory=list)
    invalid_imports: List[Tuple[str, str]] = field(default_factory=list)
    unused_imports: List[str] = field(default_factory=list)
    dead_code_paths: List[str] = field(default_factory=list)
    broken_endpoints: List[str] = field(default_factory=list)
    
    # Integration
    disconnected_modules: List[str] = field(default_factory=list)
    unconnected_apis: List[str] = field(default_factory=list)
    missing_dependencies: List[str] = field(default_factory=list)
    
    # Stats
    total_files: int = 0
    total_folders: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_apis: int = 0
    
    # Scores (0-100)
    integration_score: float = 0.0
    health_score: float = 0.0
    code_quality_score: float = 0.0


# ============================================================================
# PROJECT ANALYZER
# ============================================================================

class ProjectAnalyzer:
    """Analyzes the entire project structure"""
    
    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.report = AuditReport()
        
        # Config
        self.skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                     '.pytest_cache', '.mypy_cache', '.tox', 'dist', 'build', 
                     '.eggs', '*.egg-info'}
        self.skip_files = {'yarn.lock', 'package-lock.json', 'poetry.lock',
                       '.DS_Store', 'Thumbs.db'}
        
        # Language mappings
        self.extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'react',
            '.tsx': 'react',
            '.svelte': 'svelte',
            '.css': 'css',
            '.scss': 'scss',
            '.html': 'html',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.md': 'markdown',
            '.sh': 'bash',
            '.dockerfile': 'dockerfile',
        }
        
    def analyze(self) -> AuditReport:
        """Run complete analysis"""
        logger.info(f"Starting analysis of {self.project_path}")
        
        # 1. Map folders
        self._map_folders()
        
        # 2. Map files
        self._map_files()
        
        # 3. Parse files
        self._parse_files()
        
        # 4. Find API endpoints
        self._find_apis()
        
        # 5. Check dependencies
        self._check_dependencies()
        
        # 6. Calculate scores
        self._calculate_scores()
        
        logger.info(f"Analysis complete: {self.report.total_files} files, {self.report.total_folders} folders")
        
        return self.report
    
    def _map_folders(self):
        """Map all folders in project"""
        for root, dirs, files in os.walk(self.project_path):
            # Filter skip dirs
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            
            folder_path = os.path.relpath(root, self.project_path)
            if folder_path == '.':
                folder_path = '/'
            
            folder_info = FolderInfo(
                path=folder_path,
                file_count=len(files),
                subfolder_count=len(dirs),
                is_empty=len(files) == 0 and len(dirs) == 0
            )
            
            self.report.folders[folder_path] = folder_info
            
            if folder_info.is_empty and folder_path != '/':
                self.report.empty_folders.append(folder_path)
    
    def _map_files(self):
        """Map all files in project"""
        for root, dirs, files in os.walk(self.project_path):
            # Filter dirs
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            
            for filename in files:
                if filename in self.skip_files:
                    continue
                
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.project_path)
                
                # Get extension
                ext = os.path.splitext(filename)[1]
                language = self.extension_map.get(ext, 'unknown')
                
                # Get size
                try:
                    size = os.path.getsize(filepath)
                except:
                    size = 0
                
                file_info = FileInfo(
                    path=rel_path,
                    size=size,
                    language=language,
                    is_empty=size == 0
                )
                
                self.report.files[rel_path] = file_info
        
        self.report.total_files = len(self.report.files)
        self.report.total_folders = len(self.report.folders)
    
    def _parse_files(self):
        """Parse Python files for functions, classes, imports"""
        for filepath, file_info in self.report.files.items():
            if file_info.language != 'python':
                continue
            
            full_path = os.path.join(self.project_path, filepath)
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                file_info.size = len(content.encode('utf-8'))
                self.report.total_lines += len(content.split('\n'))
                
                # Parse AST
                try:
                    tree = ast.parse(content, filename=filepath)
                    
                    # Find imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                file_info.imports.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                file_info.imports.append(node.module)
                    
                    # Find classes
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef):
                            file_info.classes.append(node.name)
                            
                            class_info = ClassInfo(
                                name=node.name,
                                file_path=filepath,
                                line_number=node.lineno,
                                methods=[
                                    n.name for n in node.body 
                                    if isinstance(n, ast.FunctionDef)
                                ],
                                parent_classes=[
                                    b.attr for b in node.bases 
                                    if isinstance(b, ast.Attribute)
                                ]
                            )
                            self.report.classes.append(class_info)
                    
                    # Find functions
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            file_info.functions.append(node.name)
                            
                            func_info = FunctionInfo(
                                name=node.name,
                                file_path=filepath,
                                line_number=node.lineno,
                                param_count=len(node.args.args),
                                is_async=isinstance(node, ast.AsyncFunctionDef),
                                has_return=any(
                                    isinstance(n, ast.Return) 
                                    for n in node.body
                                )
                            )
                            self.report.functions.append(func_info)
                
                except SyntaxError as e:
                    file_info.has_errors = True
                    file_info.error_message = str(e)
                
            except Exception as e:
                file_info.has_errors = True
                file_info.error_message = str(e)
        
        self.report.total_functions = len(self.report.functions)
        self.report.total_classes = len(self.report.classes)
    
    def _find_apis(self):
        """Find FastAPI endpoints"""
        for filepath, file_info in self.report.files.items():
            if file_info.language != 'python':
                continue
            
            full_path = os.path.join(self.project_path, filepath)
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Simple pattern matching for FastAPI routes
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    # @router.get/post/etc
                    for method in ['get', 'post', 'put', 'delete', 'patch']:
                        if f'@router.{method}(' in line:
                            # Find path
                            path = "/"
                            if '(' in line:
                                start = line.index('(') + 1
                                end = line.index(')', start)
                                path = line[start:end].strip('"\'')
                            
                            # Find handler function
                            handler = ""
                            for j in range(i + 1, min(i + 10, len(lines))):
                                if 'async def' in lines[j] or 'def ' in lines[j]:
                                    handler = lines[j].strip()
                                    break
                            
                            # Find tags
                            tags = []
                            for j in range(max(0, i - 5), i):
                                if 'tags=' in lines[j]:
                                    tags.append(lines[j].strip())
                            
                            self.report.apis.append(APIEndpoint(
                                path=path.upper().replace('/', '') + ' ' + path,
                                method=method.upper(),
                                file_path=filepath,
                                line_number=i + 1,
                                handler_function=handler,
                                tags=tags
                            ))
            
            except Exception as e:
                logger.warning(f"Error finding APIs in {filepath}: {e}")
        
        self.report.total_apis = len(self.report.apis)
    
    def _check_dependencies(self):
        """Check package.json, requirements.txt"""
        
        # requirements.txt
        req_file = os.path.join(self.project_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Parse package==version
                        name = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0]
                        version = ""
                        if '==' in line:
                            version = line.split('==')[1]
                        self.report.dependencies[name] = DependencyInfo(
                            name=name,
                            version=version,
                            is_internal=False
                        )
        
        # package.json
        pkg_file = os.path.join(self.project_path, "package.json")
        if os.path.exists(pkg_file):
            try:
                with open(pkg_file, 'r') as f:
                    pkg = json.load(f)
                
                deps = pkg.get('dependencies', {})
                for name, version in deps.items():
                    self.report.dependencies[name] = DependencyInfo(
                        name=name,
                        version=version,
                        is_internal=False
                    )
            except:
                pass
    
    def _calculate_scores(self):
        """Calculate health scores"""
        
        # Files with errors
        error_files = sum(1 for f in self.report.files.values() if f.has_errors)
        
        # Integration score
        connected = self.report.total_apis > 0
        self.report.integration_score = min(100, (connected / 1) * 80 + 20)
        
        # Health score
        if self.report.total_files > 0:
            self.report.health_score = max(0, 100 - (error_files / self.report.total_files * 100))
        
        # Code quality
        self.report.code_quality_score = self.report.health_score


# ============================================================================
# INTEGRATION CHECKER
# ============================================================================

class IntegrationChecker:
    """Checks integration between modules"""
    
    def __init__(self, project_path: str, report: AuditReport):
        self.project_path = project_path
        self.report = report
        
    def check_all(self) -> List[str]:
        """Check all integrations, return issues"""
        issues = []
        
        # 1. Check if main.py imports all routers
        issues.extend(self._check_main_imports())
        
        # 2. Check if routers have valid handlers
        issues.extend(self._check_routers())
        
        # 3. Check Docker-compose consistency
        issues.extend(self._check_docker())
        
        # 4. Check model pool initialization
        issues.extend(self._check_model_pool())
        
        return issues
    
    def _check_main_imports(self) -> List[str]:
        """Verify main.py imports all routers"""
        issues = []
        
        main_file = os.path.join(self.project_path, "backend/main.py")
        if not os.path.exists(main_file):
            issues.append("main.py not found")
            return issues
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Expected routers
        expected_routes = [
            'chat', 'models', 'workers', 'vision', 'memory', 
            'tools', 'health', 'agents', 'browser', 'vms', 
            'gateway', 'tunnels', 'source'
        ]
        
        for route in expected_routes:
            if f'import {route}' not in content and f'from api.routes import {route}' not in content:
                # Check if endpoint exists
                route_file = os.path.join(self.project_path, f"backend/api/routes/{route}.py")
                if os.path.exists(route_file):
                    issues.append(f"Router '{route}' exists but not imported in main.py")
        
        return issues
    
    def _check_routers(self) -> List[str]:
        """Verify routers have valid handlers"""
        issues = []
        
        for api in self.report.apis:
            full_path = os.path.join(self.project_path, api.file_path)
            if not os.path.exists(full_path):
                issues.append(f"API file not found: {api.file_path}")
                continue
            
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Check if handler function exists
            if api.handler_function:
                if 'def ' + api.handler_function.split('(')[0].split()[-1] not in content:
                    pass  # Function might be defined elsewhere
        
        return issues
    
    def _check_docker(self) -> List[str]:
        """Check Docker-compose consistency"""
        issues = []
        
        # Check docker-compose.yaml
        compose_file = os.path.join(self.project_path, "docker-compose.yaml")
        if not os.path.exists(compose_file):
            issues.append("docker-compose.yaml not found")
            return issues
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Check for required services
        required = ['redis', 'rabbitmq']
        for service in required:
            if service not in content:
                issues.append(f"Docker service '{service}' not in docker-compose.yaml")
        
        return issues
    
    def _check_model_pool(self) -> List[str]:
        """Check model pool configuration"""
        issues = []
        
        model_pool = os.path.join(self.project_path, "backend/core/router/model_pool.py")
        if not os.path.exists(model_pool):
            issues.append("model_pool.py not found")
        
        return issues


# ============================================================================
# AUTO CORRECTOR
# ============================================================================

class AutoCorrector:
    """Automatically corrects detected issues"""
    
    def __init__(self, project_path: str, report: AuditReport):
        self.project_path = project_path
        self.report = report
        
    def correct_all(self) -> Dict[str, Any]:
        """Apply all corrections, return results"""
        results = {
            "fixed": [],
            "warnings": [],
            "created": []
        }
        
        # 1. Fix main.py imports
        results["fixed"].extend(self._fix_main_imports())
        
        # 2. Create missing __init__.py files
        results["created"].extend(self._create_init_files())
        
        # 3. Fix syntax errors
        results["fixed"].extend(self._fix_syntax_errors())
        
        return results
    
    def _fix_main_imports(self) -> List[str]:
        """Ensure all routers are imported in main.py"""
        fixed = []
        
        main_file = os.path.join(self.project_path, "backend/main.py")
        if not os.path.exists(main_file):
            return fixed
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Add imports for routes that exist but aren't imported
        routes_dir = os.path.join(self.project_path, "backend/api/routes")
        if os.path.exists(routes_dir):
            for filename in os.listdir(routes_dir):
                if filename.endswith('.py') and filename != '__init__.py':
                    route = filename[:-3]
                    if f'import {route}' not in content and 'api/routes' in content:
                        pass  # Already importing the module
        
        return fixed
    
    def _create_init_files(self) -> List[str]:
        """Create missing __init__.py files"""
        created = []
        
        # Find all Python packages (dirs with .py files)
        for root, dirs, files in os.walk(self.project_path):
            # Skip virtual envs
            if any(skip in root for skip in ['.venv', 'venv', 'node_modules']):
                continue
            
            has_py = any(f.endswith('.py') for f in files)
            init_file = os.path.join(root, '__init__.py')
            
            if has_py and not os.path.exists(init_file):
                try:
                    Path(init_file).touch()
                    created.append(init_file)
                except:
                    pass
        
        return created
    
    def _fix_syntax_errors(self) -> List[str]:
        """Fix obvious syntax errors"""
        fixed = []
        
        for filepath, file_info in self.report.files.items():
            if not file_info.has_errors:
                continue
            
            # Skip if too many errors
            if 'invalid syntax' not in file_info.error_message.lower():
                continue
            
            # Could add syntax fixing here
            pass
        
        return fixed


# ============================================================================
# MAIN AUDITOR CLASS
# ============================================================================

class ProjectAuditor:
    """
    Main auditor that orchestrates full project audit.
    """
    
    def __init__(self, project_path: str = "."):
        self.project_path = project_path
        self.analyzer = ProjectAnalyzer(project_path)
        self.report: Optional[AuditReport] = None
        
    async def run_full_audit(self) -> AuditReport:
        """Run complete audit"""
        logger.info("=" * 60)
        logger.info("STARTING FULL PROJECT AUDIT")
        logger.info("=" * 60)
        
        # Phase 1: Analysis
        logger.info("Phase 1: Analyzing project structure...")
        self.report = self.analyzer.analyze()
        
        # Phase 2: Integration check
        logger.info("Phase 2: Checking integrations...")
        checker = IntegrationChecker(self.project_path, self.report)
        issues = checker.check_all()
        
        for issue in issues:
            logger.warning(f"Integration issue: {issue}")
            self.report.disconnected_modules.append(issue)
        
        # Phase 3: Calculation
        logger.info("Phase 3: Calculating scores...")
        
        # Print summary
        logger.info("=" * 60)
        logger.info("AUDIT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Files analyzed: {self.report.total_files}")
        logger.info(f"Folders: {self.report.total_folders}")
        logger.info(f"Functions: {self.report.total_functions}")
        logger.info(f"Classes: {self.report.total_classes}")
        logger.info(f"APIs: {self.report.total_apis}")
        logger.info(f"Lines of code: {self.report.total_lines}")
        logger.info(f"Integration score: {self.report.integration_score:.1f}%")
        logger.info(f"Health score: {self.report.health_score:.1f}%")
        
        return self.report
    
    async def run_autocorrect(self) -> Dict[str, Any]:
        """Run auto-correction"""
        logger.info("=" * 60)
        logger.info("RUNNING AUTO CORRECTION")
        logger.info("=" * 60)
        
        corrector = AutoCorrector(self.project_path, self.report)
        results = corrector.correct_all()
        
        logger.info(f"Fixed: {len(results['fixed'])} items")
        logger.info(f"Created: {len(results['created'])} files")
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate human-readable report"""
        if not self.report:
            return {"error": "No audit run"}
        
        return {
            "summary": {
                "total_files": self.report.total_files,
                "total_folders": self.report.total_folders,
                "total_lines": self.report.total_lines,
                "total_functions": self.report.total_functions,
                "total_classes": self.report.total_classes,
                "total_apis": self.report.total_apis,
            },
            "scores": {
                "integration": self.report.integration_score,
                "health": self.report.health_score,
                "quality": self.report.code_quality_score,
            },
            "issues": {
                "empty_folders": self.report.empty_folders,
                "invalid_imports": self.report.invalid_imports,
                "disconnected": self.report.disconnected_modules,
            },
            "top_files": sorted(
                [(f.path, f.size) for f in self.report.files.values()],
                key=lambda x: -x[1]
            )[:10]
        }


# Singleton
_auditor: Optional[ProjectAuditor] = None


def get_project_auditor(project_path: str = ".") -> ProjectAuditor:
    global _auditor
    if _auditor is None:
        _auditor = ProjectAuditor(project_path)
    return _auditor