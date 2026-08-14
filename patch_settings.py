with open("/app/src/ai_os/config/settings.py") as f:
    c = f.read()

# Add N8N and workflow settings if not already there
additions = """
    # Workflow engines
    N8N_BASE_URL: str = "http://localhost:5678"
    N8N_API_KEY: str = ""
    COMFYUI_BASE_URL: str = "http://localhost:8188"
    AIOS_BASE_URL: str = "http://localhost:8080"

    # Research
    GITHUB_TOKEN: str = ""
    HUGGINGFACE_TOKEN: str = ""
    EMBEDDING_MODEL: str = "nomic-embed-text"
"""

# Find a good place to insert — before class Config
if "N8N_API_KEY" not in c:
    c = c.replace("    class Config:", additions + "\n    class Config:")
    print("Added N8N_API_KEY and other fields")
else:
    print("N8N_API_KEY already exists")

with open("/app/src/ai_os/config/settings.py", "w") as f:
    f.write(c)

print("settings.py patched")