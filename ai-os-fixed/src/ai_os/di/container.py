"""DI Container - Dependency Injection
Wires all core services so they can be resolved via container.resolve()
instead of each module maintaining its own singleton.
"""

from typing import Dict, Any, Callable, List, Optional
import logging

logger = logging.getLogger(__name__)


class DIContainer:
    """
    Simple dependency injection container.
    - Supports singleton and transient registrations
    - Resolves dependencies by key
    - All core AI-OS services are pre-registered via setup()
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._dependencies: Dict[str, List[str]] = {}

    def register(self, key: str, factory: Callable, singleton: bool = False):
        """Register a service factory"""
        self._factories[key] = factory
        if singleton:
            self._singletons[key] = None

    def register_instance(self, key: str, instance: Any):
        """Register a pre-created instance"""
        self._services[key] = instance

    def register_dependency(self, key: str, depends_on: List[str]):
        """Register dependency order"""
        self._dependencies[key] = depends_on

    async def resolve(self, key: str) -> Any:
        """Resolve a service by key"""
        if key in self._singletons and self._singletons.get(key) is not None:
            return self._singletons[key]

        if key in self._services:
            return self._services[key]

        if key in self._factories:
            factory = self._factories[key]
            instance = factory(self)
            if key in self._singletons:
                self._singletons[key] = instance
            return instance

        raise KeyError(f"Service not registered: {key}")

    def has(self, key: str) -> bool:
        return key in self._services or key in self._factories

    def list_services(self) -> List[str]:
        return list(set(list(self._services.keys()) + list(self._factories.keys())))

    async def teardown(self):
        for key, instance in self._services.items():
            if hasattr(instance, 'close'):
                await instance.close()
            elif hasattr(instance, 'stop'):
                await instance.stop()
        self._services.clear()
        self._singletons.clear()


# ---------------------------------------------------------------------------
# Global container + setup
# ---------------------------------------------------------------------------

_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get global DI container — auto-setup on first call"""
    global _container
    if _container is None:
        _container = DIContainer()
        _setup_container(_container)
    return _container


def set_container(container: DIContainer):
    global _container
    _container = container


def _setup_container(container: DIContainer):
    """
    Register all core services into the container.
    Uses singleton=True so each service is only created once.
    """

    # Event Bus
    container.register(
        "event_bus",
        lambda c: _lazy("ai_os.core.events.event_bus", "get_event_bus")(),
        singleton=True
    )

    # Model Pool
    container.register(
        "model_pool",
        lambda c: _lazy("ai_os.core.router.model_pool", "get_model_pool")(),
        singleton=True
    )

    # Intelligent Router
    container.register(
        "intelligent_router",
        lambda c: _lazy("ai_os.core.router.intelligent_router", "get_intelligent_router")(),
        singleton=True
    )

    # Worker Manager
    container.register(
        "worker_manager",
        lambda c: _lazy("ai_os.core.gpu.worker_manager", "get_worker_manager")(),
        singleton=True
    )

    # Task Queue
    container.register(
        "task_queue",
        lambda c: _lazy("ai_os.core.orchestrator.task_queue", "get_task_queue")(),
        singleton=True
    )

    # Vision Pipeline
    container.register(
        "vision_pipeline",
        lambda c: _lazy("ai_os.core.vision.processor", "get_vision_pipeline")(),
        singleton=True
    )

    # Memory Store
    container.register(
        "memory_store",
        lambda c: _lazy("ai_os.core.memory.short_term", "get_memory_store")(),
        singleton=True
    )

    # Auditor
    container.register(
        "auditor",
        lambda c: _lazy("ai_os.core.audit.auditor", "get_auditor")(),
        singleton=True
    )

    # Security Manager
    container.register(
        "security_manager",
        lambda c: _lazy("ai_os.core.security.auth", "get_security_manager")(),
        singleton=True
    )

    # Process Splitter
    container.register(
        "process_splitter",
        lambda c: _lazy("ai_os.core.orchestrator.process_splitter", "get_process_splitter")(),
        singleton=True
    )

    # Browser Pool
    container.register(
        "browser_pool",
        lambda c: _lazy("ai_os.browser.engine", "get_browser_pool")(),
        singleton=True
    )

    logger.info(f"DI container configured with {len(container.list_services())} services")


def _lazy(module_path: str, func_name: str) -> Callable:
    """Lazy import helper — avoids circular imports at module load time"""
    def factory():
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, func_name)()
    return factory
