with open('/app/src/ai_os/main.py') as f:
    c = f.read()

# Add all missing imports
c = c.replace(
    'from ai_os.api.routes import worker_lifecycle, execute',
    'from ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop'
)

# Also handle case where research/workflows already added
c = c.replace(
    'from ai_os.api.routes import worker_lifecycle, execute, research, workflows',
    'from ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop'
)

# Add HTMLResponse import if missing
if 'from fastapi.responses import HTMLResponse' not in c:
    c = c.replace(
        'from fastapi import FastAPI',
        'from fastapi import FastAPI\nfrom fastapi.responses import HTMLResponse'
    )

# Add all routers if not already there
routers_to_add = [
    ('research.router', 'settings.API_PREFIX', 'research'),
    ('workflows.router', 'settings.API_PREFIX', 'workflows'),
    ('dashboard.router', 'settings.API_PREFIX', 'dashboard'),
    ('desktop.router', 'settings.API_PREFIX', 'desktop'),
]

anchor = 'app.include_router(worker_lifecycle.router, prefix=settings.API_PREFIX + "/lifecycle", tags=["lifecycle"])'

additions = anchor
for router, prefix, tag in routers_to_add:
    line = f'\napp.include_router({router}, prefix={prefix}, tags=["{tag}"])'
    if f'include_router({router}' not in c:
        additions += line

if additions != anchor:
    c = c.replace(anchor, additions)

# Add dashboard UI endpoint if missing
if '/dashboard-ui' not in c:
    old_root = '''@app.get("/")
async def root():'''
    new_root = '''@app.get("/dashboard-ui", response_class=HTMLResponse)
async def dashboard_ui():
    import os
    p = "/app/frontend/dashboard.html"
    if os.path.exists(p):
        with open(p) as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard not found at " + p + "</h1>")

@app.get("/")
async def root():'''
    c = c.replace(old_root, new_root)

with open('/app/src/ai_os/main.py', 'w') as f:
    f.write(c)

# Verify
with open('/app/src/ai_os/main.py') as f:
    content = f.read()

checks = ['dashboard', 'desktop', 'research', 'workflows', 'dashboard-ui']
for check in checks:
    print(f"{'OK' if check in content else 'MISSING'}: {check}")