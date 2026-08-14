import asyncio
import sys
sys.path.insert(0, '/app/src')

async def test():
    from ai_os.utils.n8n_integration import get_n8n_client, N8NWorkflowBuilder, N8NNodeTemplates, N8N_API_KEY, N8N_BASE_URL

    print("URL:", N8N_BASE_URL)
    print("Key:", N8N_API_KEY[:20] if N8N_API_KEY else "EMPTY")

    client = get_n8n_client()
    print("Client URL:", client._base_url)
    print("Client Key:", client._api_key[:20] if client._api_key else "EMPTY")

    # Rebuild singleton with correct key
    import ai_os.utils.n8n_integration as mod
    mod._n8n_client = None  # reset singleton
    mod.N8N_API_KEY = N8N_API_KEY
    mod.N8N_BASE_URL = N8N_BASE_URL

    client = mod.get_n8n_client()
    client._api_key = N8N_API_KEY
    client._base_url = N8N_BASE_URL
    # Reset headers
    client._client = None

    print("After reset - Key:", client._api_key[:20] if client._api_key else "EMPTY")

    t = Nod = N8NNodeTemplates
    builder = N8NWorkflowBuilder("Test From Route")
    builder.add_node(t.webhook("Webhook", "/test-route"), connect_to_last=False)
    builder.add_node(t.code("Process", "return items;"))
    workflow = builder.build()

    print("Workflow:", workflow.name, "nodes:", len(workflow.nodes))
    result = await client.create_workflow(workflow)
    print("Result:", result)

asyncio.run(test())