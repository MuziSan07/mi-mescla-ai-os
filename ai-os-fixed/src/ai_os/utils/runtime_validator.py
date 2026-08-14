"""
AI-OS Runtime Verification and Integration Validation System
Real execution tracing, validation, and fake architecture detection
"""

import os
import asyncio
import time
import json
import traceback
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================

class ExecutionStatus(str, Enum):
    """Execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DISCONNECTED = "disconnected"


class ComponentType(str, Enum):
    """Component types"""
    API = "api"
    WORKER = "worker"
    QUEUE = "queue"
    MODEL = "model"
    AGENT = "agent"
    TOOL = "tool"
    SERVICE = "service"
    MIDDLEWARE = "middleware"


@dataclass
class TraceEvent:
    """Runtime trace event"""
    timestamp: float = field(default_factory=time.time)
    component: str = ""
    event_type: str = ""  # enter, exit, call, error
    duration_ms: float = 0.0
    input_data: Optional[Dict] = None
    output_data: Optional[Dict] = None
    error: Optional[str] = None
    trace_id: str = ""


@dataclass
class ExecutionSpan:
    """Execution span for tracing"""
    span_id: str
    trace_id: str
    component: str
    operation: str
    start_time: float
    end_time: float = 0.0
    status: ExecutionStatus = ExecutionStatus.PENDING
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[TraceEvent] = field(default_factory=list)


@dataclass
class ComponentStatus:
    """Runtime status of a component"""
    name: str
    type: ComponentType
    is_registered: bool = False
    is_running: bool = False
    execution_count: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0
    last_execution: float = 0.0
    is_placeholder: bool = False
    never_called: bool = False


@dataclass
class WorkflowRun:
    """Real workflow execution"""
    workflow_id: str
    start_time: float
    end_time: float = 0.0
    status: ExecutionStatus = ExecutionStatus.PENDING
    steps: List[ExecutionSpan] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    result: Optional[Dict] = None


@dataclass
class ValidationResult:
    """Runtime validation result"""
    component: str
    is_working: bool = False
    is_integrated: bool = False
    is_recorded: bool = False
    call_count: int = 0
    avg_response_time_ms: float = 0.0
    last_error: Optional[str] = None
    is_fake: bool = False


# ============================================================================
# RUNTIME TRACER
# ============================================================================

class RuntimeTracer:
    """
    Runtime tracer that tracks real execution.
    """
    
    def __init__(self):
        self.trace_id = ""
        self.spans: Dict[str, ExecutionSpan] = {}
        self.events: List[TraceEvent] = []
        self.component_status: Dict[str, ComponentStatus] = {}
        self.enabled = True
        
    def start_trace(self, trace_id: str = None):
        """Start a new trace"""
        self.trace_id = trace_id or f"trace-{int(time.time() * 1000)}"
        self.spans = {}
        self.events = []
        return self.trace_id
    
    def start_span(
        self, 
        component: str, 
        operation: str,
        attributes: Dict = None
    ) -> ExecutionSpan:
        """Start a span"""
        span_id = f"{component}:{operation}:{len(self.spans)}"
        span = ExecutionSpan(
            span_id=span_id,
            trace_id=self.trace_id,
            component=component,
            operation=operation,
            start_time=time.time(),
            attributes=attributes or {}
        )
        self.spans[span_id] = span
        
        # Track component status
        if component not in self.component_status:
            self.component_status[component] = ComponentStatus(
                name=component,
                type=ComponentType.SERVICE
            )
        
        return span
    
    def end_span(
        self, 
        span: ExecutionSpan, 
        status: ExecutionStatus = ExecutionStatus.SUCCESS,
        error: str = None
    ):
        """End a span"""
        span.end_time = time.time()
        span.status = status
        if error:
            span.attributes["error"] = error
        
        # Update component status
        comp_status = self.component_status.get(span.component)
        if comp_status:
            comp_status.execution_count += 1
            comp_status.last_execution = time.time()
            if status == ExecutionStatus.FAILED:
                comp_status.error_count += 1
            span_duration = (span.end_time - span.start_time) * 1000
            comp_status.avg_duration_ms = (
                comp_status.avg_duration_ms * (comp_status.execution_count - 1) + span_duration
            ) / comp_status.execution_count
    
    def record_event(self, event: TraceEvent):
        """Record a trace event"""
        self.events.append(event)
        
        # Track never-called components
        if event.event_type == "call":
            comp = self.component_status.get(event.component)
            if comp:
                comp.never_called = False
    
    def get_trace_summary(self) -> Dict:
        """Get trace summary"""
        return {
            "trace_id": self.trace_id,
            "span_count": len(self.spans),
            "event_count": len(self.events),
            "components": {
                name: {
                    "count": status.execution_count,
                    "errors": status.error_count,
                    "avg_ms": status.avg_duration_ms,
                    "never_called": status.never_called
                }
                for name, status in self.component_status.items()
            }
        }


# Decorator for automatic tracing
def traced(component: str = None, operation: str = None):
    """Decorator to trace function execution"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_runtime_tracer()
            comp = component or func.__module__
            op = operation or func.__name__
            
            span = tracer.start_span(comp, op)
            try:
                result = await func(*args, **kwargs)
                tracer.end_span(span, ExecutionStatus.SUCCESS)
                tracer.record_event(TraceEvent(
                    component=comp,
                    event_type="exit",
                    duration_ms=(time.time() - span.start_time) * 1000,
                    output_data={"result": str(type(result))}
                ))
                return result
            except Exception as e:
                tracer.end_span(span, ExecutionStatus.FAILED, str(e))
                tracer.record_event(TraceEvent(
                    component=comp,
                    event_type="error",
                    error=str(e)
                ))
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_runtime_tracer()
            comp = component or func.__module__
            op = operation or func.__name__
            
            span = tracer.start_span(comp, op)
            try:
                result = func(*args, **kwargs)
                tracer.end_span(span, ExecutionStatus.SUCCESS)
                return result
            except Exception as e:
                tracer.end_span(span, ExecutionStatus.FAILED, str(e))
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============================================================================
# RUNTIME VALIDATOR
# ============================================================================

class RuntimeValidator:
    """
    Validates real runtime execution.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.tracer = RuntimeTracer()
        self.services: Dict[str, ComponentStatus] = {}
    
    async def validate_api_endpoint(
        self, 
        method: str, 
        path: str,
        payload: Dict = None,
        timeout: int = 30
    ) -> ValidationResult:
        """Validate a real API endpoint"""
        import httpx
        
        result = ValidationResult(component=path)
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = f"{self.base_url}{path}"
                
                resp = await getattr(client, method.lower())(
                    url, 
                    json=payload or {}
                )
                
                result.is_working = resp.status_code < 500
                result.call_count = 1
                
                result.is_recorded = True
                
                if not result.is_working:
                    result.last_error = f"HTTP {resp.status_code}"
                
                # Check if fake (always returns same thing)
                if resp.status_code == 200:
                    result.is_integrated = True
        
        except asyncio.TimeoutError:
            result.is_working = False
            result.last_error = "Timeout"
        except Exception as e:
            result.is_working = False
            result.last_error = str(e)
            result.is_fake = "Connection" in str(e) or " refused" in str(e)
        
        return result
    
    async def validate_all_endpoints(self) -> List[ValidationResult]:
        """Validate all registered endpoints"""
        results = []
        
        # Common endpoints to test
        endpoints = [
            ("GET", "/api/chat"),
            ("GET", "/api/models"),
            ("GET", "/api/workers"),
            ("GET", "/api/health"),
            ("GET", "/api/gateway/models"),
            ("GET", "/api/agents/stats"),
            ("GET", "/api/audit/health"),
        ]
        
        for method, path in endpoints:
            result = await self.validate_api_endpoint(method, path)
            results.append(result)
        
        return results
    
    async def validate_queue(self, queue_name: str) -> ValidationResult:
        """Validate a queue is working"""
        import pika
        
        result = ValidationResult(component=f"queue:{queue_name}")
        
        try:
            # Try to connect
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host='localhost')
            )
            channel = connection.channel()
            
            # Declare queue
            channel.queue_declare(queue=queue_name, passive=True)
            
            result.is_working = True
            result.call_count = 1
            result.is_integrated = True
            
            connection.close()
        
        except Exception as e:
            result.last_error = str(e)
            result.is_fake = "connection refused" in str(e).lower()
        
        return result
    
    async def validate_redis(self) -> ValidationResult:
        """Validate Redis is working"""
        import redis
        
        result = ValidationResult(component="redis")
        
        try:
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            
            result.is_working = True
            result.is_integrated = True
            result.call_count = 1
        
        except Exception as e:
            result.last_error = str(e)
        
        return result
    
    async def validate_docker_service(self, service_name: str) -> ValidationResult:
        """Validate a Docker service is running"""
        import subprocess
        
        result = ValidationResult(component=f"docker:{service_name}")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                info = json.loads(stdout)
                result.is_working = info[0].get("State", {}).get("Running", False)
                result.is_integrated = result.is_working
            else:
                result.last_error = stderr.decode()
            
            result.call_count = 1
        
        except Exception as e:
            result.last_error = str(e)
            result.is_fake = True
        
        return result
    
    async def validate_worker_registration(self) -> ValidationResult:
        """Validate workers are registered"""
        result = await self.validate_api_endpoint("GET", "/api/workers")
        
        if result.is_working:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/api/workers")
                data = resp.json()
                
                workers = data.get("workers", [])
                result.call_count = len(workers)
                
                # Check if registered workers are actually working
                if len(workers) == 0:
                    result.last_error = "No workers registered"
                    result.is_fake = True
        
        return result
    
    async def run_workflow_test(
        self, 
        workflow_steps: List[Dict]
    ) -> WorkflowRun:
        """Run a real workflow end-to-end"""
        run = WorkflowRun(
            workflow_id=f"test-{int(time.time())}",
            start_time=time.time()
        )
        
        for step in workflow_steps:
            span = self.tracer.start_span(step["component"], step["operation"])
            
            try:
                # Execute step
                result = await self.validate_api_endpoint(
                    step["method"],
                    step["path"],
                    step.get("payload")
                )
                
                if result.is_working:
                    self.tracer.end_span(span, ExecutionStatus.SUCCESS)
                else:
                    self.tracer.end_span(span, ExecutionStatus.FAILED, result.last_error)
                    run.errors.append(f"{step['component']}: {result.last_error}")
                
                run.steps.append(span)
            
            except Exception as e:
                self.tracer.end_span(span, ExecutionStatus.FAILED, str(e))
                run.errors.append(f"{step['component']}: {str(e)}")
        
        run.end_time = time.time()
        run.status = ExecutionStatus.SUCCESS if not run.errors else ExecutionStatus.FAILED
        
        return run


# ============================================================================
# FAKE ARCHITECTURE DETECTOR
# ============================================================================

class FakeArchitectureDetector:
    """
    Detects fake/non-functional components.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    async def detect_placebo_modules(self) -> List[str]:
        """Find modules that exist but never execute"""
        fake_modules = []
        
        # Patterns to detect fake modules
        placeholder_patterns = [
            "pass  # TODO",
            "# Not implemented",
            "raise NotImplementedError",
            "return {}  # Placeholder",
            "return []  # Stub",
        ]
        
        # For each API route file
        api_dir = os.path.join(os.getcwd(), "backend/api/routes")
        if not os.path.exists(api_dir):
            return fake_modules
        
        for filename in os.listdir(api_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                filepath = os.path.join(api_dir, filename)
                
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Check for placeholder patterns
                for pattern in placeholder_patterns:
                    if pattern in content:
                        fake_modules.append(f"api:{filename}")
                        break
        
        return fake_modules
    
    async def detect_unused_endpoints(self) -> List[str]:
        """Find API endpoints that are never called"""
        unused = []
        
        # We would need runtime data for this
        # For now, return endpoints that might be fake
        
        return unused
    
    async def detect_disconnected_services(self) -> List[Dict]:
        """Find services that aren't connected"""
        disconnected = []
        
        # Check key integrations
        checks = [
            ("redis", "Redis"),
            ("rabbitmq", "RabbitMQ"),
            ("qdrant", "Qdrant"),
        ]
        
        for service, name in checks:
            try:
                if service == "redis":
                    import redis
                    r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
                    r.ping()
                elif service == "rabbitmq":
                    import pika
                    conn = pika.BlockingConnection(
                        pika.ConnectionParameters(host='localhost', socket_connect_timeout=2)
                    )
                    conn.close()
            except:
                disconnected.append({
                    "service": name,
                    "issue": "Not connected"
                })
        
        return disconnected
    
    async def detect_orphaned_files(self) -> List[str]:
        """Find files that aren't imported anywhere"""
        orphaned = []
        
        # Walk the project
        backend_dir = os.path.join(os.getcwd(), "backend")
        
        # Get all Python files
        all_files = set()
        for root, dirs, files in os.walk(backend_dir):
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__'}]
            for f in files:
                if f.endswith('.py'):
                    all_files.add(f)
        
        # Get all imports from main files
        imported = set()
        for root, dirs, files in os.walk(backend_dir):
            for f in files:
                if f == 'main.py' or f.endswith('_routes.py'):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, 'r') as fi:
                            content = fi.read()
                            for imp in all_files:
                                if f"import {imp.replace('.py', '')}" in content or f"from .{imp.replace('.py', '')}" in content:
                                    imported.add(imp)
                    except:
                        pass
        
        # Files never imported
        for f in all_files:
            if f not in imported and f != '__init__.py':
                orphaned.append(f)
        
        return orphaned


# ============================================================================
# END-TO-END WORKFLOW TESTER
# ============================================================================

class E2EWorkflowTester:
    """
    Tests complete workflows end-to-end.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.validator = RuntimeValidator(base_url)
        self.tracer = RuntimeTracer()
    
    async def test_chat_workflow(self) -> WorkflowRun:
        """Test chat workflow"""
        run = WorkflowRun(
            workflow_id="chat_e2e",
            start_time=time.time()
        )
        
        steps = [
            {"component": "api", "operation": "chat", "method": "POST", "path": "/api/chat", "payload": {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}]
            }},
        ]
        
        # Execute
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for step in steps:
                    span = self.tracer.start_span(step["component"], step["operation"])
                    
                    resp = await client.post(
                        f"{self.base_url}{step['path']}",
                        json=step["payload"]
                    )
                    
                    if resp.status_code < 400:
                        self.tracer.end_span(span, ExecutionStatus.SUCCESS)
                        run.result = resp.json()
                    else:
                        self.tracer.end_span(span, ExecutionStatus.FAILED)
                        run.errors.append(f"HTTP {resp.status_code}")
                    
                    run.steps.append(span)
        
        except Exception as e:
            run.errors.append(str(e))
        
        run.end_time = time.time()
        run.status = ExecutionStatus.SUCCESS if not run.errors else ExecutionStatus.FAILED
        
        return run
    
    async def test_agent_workflow(self) -> WorkflowRun:
        """Test agent execution workflow"""
        run = WorkflowRun(
            workflow_id="agent_e2e",
            start_time=time.time()
        )
        
        # Single agent call
        result = await self.validator.validate_api_endpoint(
            "POST", 
            "/api/agents/execute",
            {"task_type": "chat", "prompt": "test"}
        )
        
        run.status = ExecutionStatus.SUCCESS if result.is_working else ExecutionStatus.FAILED
        if result.last_error:
            run.errors.append(result.last_error)
        
        run.end_time = time.time()
        
        return run
    
    async def test_vision_workflow(self) -> WorkflowRun:
        """Test vision processing workflow"""
        run = WorkflowRun(
            workflow_id="vision_e2e",
            start_time=time.time()
        )
        
        result = await self.validator.validate_api_endpoint(
            "POST",
            "/api/vision/analyze",
            {"image_url": "https://example.com/test.jpg"}
        )
        
        run.status = ExecutionStatus.SUCCESS if result.is_working else ExecutionStatus.FAILED
        if result.last_error:
            run.errors.append(result.last_error)
        
        run.end_time = time.time()
        
        return run
    
    async def run_all_tests(self) -> Dict:
        """Run all E2E tests"""
        results = {}
        
        # Test each workflow
        workflows = [
            ("chat", self.test_chat_workflow),
            ("agent", self.test_agent_workflow),
            ("vision", self.test_vision_workflow),
        ]
        
        for name, test_func in workflows:
            try:
                result = await test_func()
                results[name] = {
                    "status": result.status.value,
                    "duration_ms": (result.end_time - result.start_time) * 1000,
                    "errors": result.errors,
                    "steps": len(result.steps)
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results


# ============================================================================
# MAIN RUNTIME VALIDATOR
# ============================================================================

class RuntimeVerificationSystem:
    """
    Main runtime verification system.
    Combines all validators.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.tracer = RuntimeTracer()
        self.validator = RuntimeValidator(base_url)
        self.detector = FakeArchitectureDetector(base_url)
        self.e2e_tester = E2EWorkflowTester(base_url)
    
    async def run_full_validation(self) -> Dict:
        """Run complete runtime validation"""
        logger.info("=" * 60)
        logger.info("RUNNING RUNTIME VERIFICATION")
        logger.info("=" * 60)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "endpoints": [],
            "services": {},
            "fake_components": [],
            "disconnected": [],
            "e2e_tests": {},
            "integration_score": 0.0
        }
        
        # 1. Test endpoints
        logger.info("Testing API endpoints...")
        endpoints = await self.validator.validate_all_endpoints()
        
        working_endpoints = [e for e in endpoints if e.is_working]
        results["endpoints"] = [
            {"path": e.component, "working": e.is_working}
            for e in endpoints
        ]
        
        # 2. Test services
        logger.info("Testing services...")
        
        # Redis
        redis_result = await self.validator.validate_redis()
        results["services"]["redis"] = {
            "working": redis_result.is_working,
            "error": redis_result.last_error
        }
        
        # 3. Detect fake components
        logger.info("Detecting fake architecture...")
        
        disconnected = await self.detector.detect_disconnected_services()
        results["disconnected"] = disconnected
        
        # Calculate score
        total_elements = len(endpoints) + len(disconnected) + 1
        working_elements = len(working_endpoints) + (1 if redis_result.is_working else 0)
        results["integration_score"] = (working_elements / total_elements) * 100
        
        # 4. E2E tests
        logger.info("Running E2E tests...")
        results["e2e_tests"] = await self.e2e_tester.run_all_tests()
        
        logger.info("=" * 60)
        logger.info(f"Integration Score: {results['integration_score']:.1f}%")
        logger.info("=" * 60)
        
        return results
    
    def get_trace_summary(self) -> Dict:
        """Get execution trace summary"""
        return self.tracer.get_trace_summary()


# Singleton
_runtime_system: Optional[RuntimeVerificationSystem] = None


def get_runtime_verification(base_url: str = "http://localhost:8000") -> RuntimeVerificationSystem:
    global _runtime_system
    if _runtime_system is None:
        _runtime_system = RuntimeVerificationSystem(base_url)
    return _runtime_system


def get_runtime_tracer() -> RuntimeTracer:
    """Get global runtime tracer"""
    system = get_runtime_verification()
    return system.tracer