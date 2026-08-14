import asyncio
import httpx
import sys
sys.path.insert(0, '/app/src')

from ai_os.utils.n8n_integration import get_n8n_client, N8NWorkflowBuilder, N8NNodeTemplates

async def test():
    client = get_n8n_client()
    print("URL:", client._base_url)
    print("Key:", client._api_key[:20] + "..." if client._api_key else "NOT SET")

    # Test health
    ok = await client.health_check()
    print("Health:", ok)

    # Try raw API call
    headers = {"X-N8N-API-KEY": client._api_key, "Content-Type": "application/json"}
    payload = {
        "name": "Test Workflow",
        "nodes": [{
            "id": "abc1",
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "position": [240, 300],
            "parameters": {"path": "/test", "httpMethod": "POST", "responseMode": "onReceived"},
            "typeVersion": 2
        }],
        "connections": {},
        "settings": {"executionOrder": "v1"}
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{client._base_url}/api/v1/workflows", json=payload, headers=headers)
        print("Status:", r.status_code)
        print("Response:", r.text[:500])

asyncio.run(test())