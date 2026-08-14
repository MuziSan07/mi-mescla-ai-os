with open('/app/src/ai_os/api/routes/__init__.py', 'w') as f:
    f.write('''"""AI Operating System - API Routes"""
from . import chat, models, workers, vision, memory, tools, health
from . import agents, browser, vms, gateway, tunnels, source, audit, runtime_validate, observability
from . import worker_lifecycle, execute
from . import research, workflows, dashboard, desktop

__all__ = [
    "chat", "models", "workers", "vision", "memory", "tools", "health",
    "agents", "browser", "vms", "gateway", "tunnels", "source", "audit",
    "runtime_validate", "observability", "worker_lifecycle", "execute",
    "research", "workflows", "dashboard", "desktop"
]
''')
print("done")