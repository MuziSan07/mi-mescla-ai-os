import re

# Read main.py
with open('/app/src/ai_os/main.py') as f:
    c = f.read()

# Replace ALL route imports with direct module imports
# Remove every "from ai_os.api.routes import ..." line
c = re.sub(r'from ai_os\.api\.routes import [^\n]+\n', '', c)

# Add correct imports right before the first app.include_router line
correct_imports = """import importlib, sys
_routes_pkg = 'ai_os.api.routes'
chat = importlib.import_module(f'{_routes_pkg}.chat')
models = importlib.import_module(f'{_routes_pkg}.models')
workers = importlib.import_module(f'{_routes_pkg}.workers')
vision = importlib.import_module(f'{_routes_pkg}.vision')
memory = importlib.import_module(f'{_routes_pkg}.memory')
tools = importlib.import_module(f'{_routes_pkg}.tools')
health = importlib.import_module(f'{_routes_pkg}.health')
agents = importlib.import_module(f'{_routes_pkg}.agents')
browser = importlib.import_module(f'{_routes_pkg}.browser')
vms = importlib.import_module(f'{_routes_pkg}.vms')
gateway = importlib.import_module(f'{_routes_pkg}.gateway')
tunnels = importlib.import_module(f'{_routes_pkg}.tunnels')
source = importlib.import_module(f'{_routes_pkg}.source')
audit = importlib.import_module(f'{_routes_pkg}.audit')
runtime_validate = importlib.import_module(f'{_routes_pkg}.runtime_validate')
observability = importlib.import_module(f'{_routes_pkg}.observability')
worker_lifecycle = importlib.import_module(f'{_routes_pkg}.worker_lifecycle')
execute = importlib.import_module(f'{_routes_pkg}.execute')
research = importlib.import_module(f'{_routes_pkg}.research')
workflows = importlib.import_module(f'{_routes_pkg}.workflows')
dashboard = importlib.import_module(f'{_routes_pkg}.dashboard')
desktop = importlib.import_module(f'{_routes_pkg}.desktop')
"""

# Insert before first app.include_router
c = c.replace('app.include_router(chat.router', correct_imports + '\napp.include_router(chat.router', 1)

with open('/app/src/ai_os/main.py', 'w') as f:
    f.write(c)

print("done")