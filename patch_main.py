with open('/app/src/ai_os/main.py') as f:
    c = f.read()

c = c.replace(
    'from ai_os.api.routes import worker_lifecycle, execute',
    'from ai_os.api.routes import worker_lifecycle, execute, research, workflows'
)

c = c.replace(
    'app.include_router(worker_lifecycle.router, prefix=settings.API_PREFIX + "/lifecycle", tags=["lifecycle"])',
    'app.include_router(worker_lifecycle.router, prefix=settings.API_PREFIX + "/lifecycle", tags=["lifecycle"])\napp.include_router(research.router, prefix=settings.API_PREFIX, tags=["research"])\napp.include_router(workflows.router, prefix=settings.API_PREFIX, tags=["workflows"])'
)

with open('/app/src/ai_os/main.py', 'w') as f:
    f.write(c)

print('done')