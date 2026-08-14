import sys
sys.path.insert(0, '/app/src')

# The issue is the route uses get_n8n_client() which reads N8N_API_KEY at import time
# but the key was set AFTER import. Let's force reload the module.

import importlib
import ai_os.utils.n8n_integration as m
importlib.reload(m)

import os
print("N8N_API_KEY from env:", os.getenv("N8N_API_KEY", "NOT SET")[:20] if os.getenv("N8N_API_KEY") else "NOT SET")
print("Key in module:", m.N8N_API_KEY[:20] if m.N8N_API_KEY else "NOT SET")

# Force set the key in the module
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlY2Q3YWI3Ni1kNzRiLTQwZTQtODYzZC0zMmUxMDVhZjA5MWMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMGViMjg4ZGEtZTM1Zi00MjMwLTgyMzAtNmVjOWNmMmYxOTc1IiwiaWF0IjoxNzc5NjI1OTQyfQ.MwqeFILOxO1uP8VcTwUm8tDOK9LogVr-diofCaH9cFg"

# Write key to a permanent env file that gets loaded at startup
env_file = "/app/src/ai_os/n8n_key.py"
with open(env_file, "w") as f:
    f.write(f'N8N_API_KEY = "{KEY}"\n')
    f.write(f'N8N_BASE_URL = "http://cline-ai-n8n:5678"\n')
print(f"Key written to {env_file}")

# Also patch n8n_integration.py to import from this file
with open("/app/src/ai_os/utils/n8n_integration.py") as f:
    c = f.read()

if "from ai_os.n8n_key import" not in c:
    c = "try:\n    from ai_os.n8n_key import N8N_API_KEY as _KEY, N8N_BASE_URL as _URL\nexcept ImportError:\n    _KEY = ''\n    _URL = 'http://localhost:5678'\n\n" + c
    c = c.replace(
        "N8N_BASE_URL = os.getenv(\"N8N_BASE_URL\", \"http://localhost:5678\")",
        "N8N_BASE_URL = _URL or os.getenv(\"N8N_BASE_URL\", \"http://localhost:5678\")"
    )
    c = c.replace(
        "N8N_API_KEY = os.getenv(\"N8N_API_KEY\", \"\")",
        "N8N_API_KEY = _KEY or os.getenv(\"N8N_API_KEY\", \"\")"
    )
    with open("/app/src/ai_os/utils/n8n_integration.py", "w") as f:
        f.write(c)
    print("n8n_integration.py patched to load key from file")
else:
    print("Already patched")

print("Done! Restart the container.")