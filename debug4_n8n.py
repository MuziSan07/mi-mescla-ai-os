import asyncio, json, sys
sys.path.insert(0, '/app/src')

async def test():
    from ai_os.utils.n8n_integration import N8NWorkflowBuilder, N8NNodeTemplates, N8N_API_KEY, N8N_BASE_URL
    import httpx

    t = N8NNodeTemplates
    builder = N8NWorkflowBuilder("Test")
    builder.add_node(t.webhook("Webhook", "/test2"), connect_to_last=False)
    workflow = builder.build()

    payload = workflow.to_dict()
    print("Payload being sent:")
    print(json.dumps(payload, indent=2))

    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{N8N_BASE_URL}/api/v1/workflows", json=payload, headers=headers)
        print("Status:", r.status_code)
        print("Response:", r.text[:500])

asyncio.run(test())