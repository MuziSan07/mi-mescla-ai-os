import asyncio
import httpx

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlY2Q3YWI3Ni1kNzRiLTQwZTQtODYzZC0zMmUxMDVhZjA5MWMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMGViMjg4ZGEtZTM1Zi00MjMwLTgyMzAtNmVjOWNmMmYxOTc1IiwiaWF0IjoxNzc5NjI1OTQyfQ.MwqeFILOxO1uP8VcTwUm8tDOK9LogVr-diofCaH9cFg"

async def test():
    headers = {
        "X-N8N-API-KEY": KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "abc123",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "position": [240, 300],
                "parameters": {"path": "/test", "httpMethod": "POST", "responseMode": "onReceived"},
                "typeVersion": 1
            }
        ],
        "connections": {},
        "active": False,
        "settings": {"executionOrder": "v1"}
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("http://cline-ai-n8n:5678/api/v1/workflows", json=payload, headers=headers)
        print("Status:", r.status_code)
        print("Response:", r.text[:500])

asyncio.run(test())