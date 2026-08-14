with open('/app/src/ai_os/main.py') as f:
    c = f.read()

# Fix duplicate dashboard and desktop imports
c = c.replace(
    'from ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop, dashboard, desktop',
    'from ai_os.api.routes import worker_lifecycle, execute, research, workflows, dashboard, desktop'
)

# Also fix any other duplicate variations
import re
c = re.sub(
    r'from ai_os\.api\.routes import ([\w, ]+)',
    lambda m: 'from ai_os.api.routes import ' + ', '.join(dict.fromkeys(x.strip() for x in m.group(1).split(','))),
    c
)

with open('/app/src/ai_os/main.py', 'w') as f:
    f.write(c)

# Also ensure dashboard and desktop exist in routes __init__.py
init_path = '/app/src/ai_os/api/routes/__init__.py'
with open(init_path) as f:
    init_content = f.read()

additions = []
if 'dashboard' not in init_content:
    additions.append('from ai_os.api.routes import dashboard')
if 'desktop' not in init_content:
    additions.append('from ai_os.api.routes import desktop')

if additions:
    with open(init_path, 'a') as f:
        f.write('\n' + '\n'.join(additions) + '\n')
    print("Added to __init__.py:", additions)
else:
    print("__init__.py already has dashboard and desktop")

print("main.py fixed")