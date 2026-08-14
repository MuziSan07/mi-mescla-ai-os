key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlY2Q3YWI3Ni1kNzRiLTQwZTQtODYzZC0zMmUxMDVhZjA5MWMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMGViMjg4ZGEtZTM1Zi00MjMwLTgyMzAtNmVjOWNmMmYxOTc1IiwiaWF0IjoxNzc5NjI1OTQyfQ.MwqeFILOxO1uP8VcTwUm8tDOK9LogVr-diofCaH9cFg"

import os
os.environ["N8N_API_KEY"] = key

f = open("/app/src/ai_os/utils/n8n_integration.py")
c = f.read()
f.close()

c = c.replace(
    "N8N_API_KEY = os.getenv(\"N8N_API_KEY\", \"\")",
    f'N8N_API_KEY = os.getenv("N8N_API_KEY", "{key}")'
)

open("/app/src/ai_os/utils/n8n_integration.py", "w").write(c)
print("n8n API key set")