# Step 1: Reset __init__.py to empty - no imports at all
with open('/app/src/ai_os/api/routes/__init__.py', 'w') as f:
    f.write('"""AI Operating System - API Routes"""\n')
print("__init__.py reset")

# Step 2: Fix main.py to import routes directly, not via __init__
with open('/app/src/ai_os/main.py') as f:
    c = f.read()

# Replace the grouped import lines with individual direct imports
old = "from ai_os.api.routes import chat, models, workers, vision, memory, tools, health\nfrom ai_os.api.routes import agents, browser, vms, gateway, tunnels, source, audit, runtime_validate, observability\nfrom ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop"

new = """from ai_os.api.routes import chat
from ai_os.api.routes import models
from ai_os.api.routes import workers
from ai_os.api.routes import vision
from ai_os.api.routes import memory
from ai_os.api.routes import tools
from ai_os.api.routes import health
from ai_os.api.routes import agents
from ai_os.api.routes import browser
from ai_os.api.routes import vms
from ai_os.api.routes import gateway
from ai_os.api.routes import tunnels
from ai_os.api.routes import source
from ai_os.api.routes import audit
from ai_os.api.routes import runtime_validate
from ai_os.api.routes import observability
from ai_os.api.routes import worker_lifecycle
from ai_os.api.routes import execute
from ai_os.api.routes import research
from ai_os.api.routes import workflows
from ai_os.api.routes import dashboard
from ai_os.api.routes import desktop"""

if old in c:
    c = c.replace(old, new)
    print("Replaced grouped imports with individual imports")
else:
    # Try fixing whatever variant is there
    import re
    # Remove all existing route import lines
    c = re.sub(r'from ai_os\.api\.routes import [^\n]+\n', '', c)
    # Find the right insertion point (after other imports, before app creation)
    c = c.replace(
        'from ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop',
        new
    )
    # Also handle any other variants
    for old_line in [
        'from ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop, dashboard, desktop',
        'from ai_os.api.routes import chat, models, workers, vision, memory, tools, health',
        'from ai_os.api.routes import agents, browser, vms, gateway, tunnels, source, audit, runtime_validate, observability',
    ]:
        c = c.replace(old_line, '')
    
    # Insert imports before first app.include_router line
    insert_before = 'app.include_router(chat.router'
    c = c.replace(insert_before, new + '\n\n' + insert_before)
    print("Used fallback insertion")

with open('/app/src/ai_os/main.py', 'w') as f:
    f.write(c)

# Verify
with open('/app/src/ai_os/main.py') as f:
    content = f.read()

for name in ['dashboard', 'desktop', 'research', 'workflows']:
    found = f'from ai_os.api.routes import {name}' in content
    print(f"{'OK' if found else 'MISSING'}: {name}")