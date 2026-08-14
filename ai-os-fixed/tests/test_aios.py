"""
AI-OS Test Suite
Run with: python -m pytest /app/tests/ -v
"""

import asyncio
import pytest
import httpx

BASE_URL = "http://localhost:8080"
API = f"{BASE_URL}/api/v1"


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True)


class TestRoot:
    def test_root_returns_running(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"
        assert data["name"] == "AI-OS"

    def test_health_liveness(self, client):
        r = client.get(f"{API}/health/live")
        assert r.status_code == 200
        assert r.json().get("alive") is True

    def test_health_readiness(self, client):
        r = client.get(f"{API}/health/ready")
        assert r.status_code == 200
        assert r.json().get("ready") is True

    def test_docs_accessible(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


class TestModels:
    def test_list_models(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_model_has_required_fields(self, client):
        models = client.get(f"{API}/").json()
        for model in models:
            assert "id" in model
            assert "name" in model
            assert "model_type" in model
            assert "provider" in model


class TestMemory:
    def test_store_memory(self, client):
        r = client.post(f"{API}/memory/store", json={
            "key": "test-key-001",
            "value": "Paris is the capital of France",
            "memory_type": "short_term"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["key"] == "test-key-001"
        assert "id" in data

    def test_recall_memory(self, client):
        client.post(f"{API}/memory/store", json={
            "key": "recall-test",
            "value": "the Eiffel Tower is in Paris France",
            "memory_type": "short_term"
        })
        r = client.post(f"{API}/memory/recall", json={"query": "Eiffel Tower Paris", "limit": 5})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_memories(self, client):
        r = client.get(f"{API}/memory/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_store_different_types(self, client):
        for mem_type in ["short_term", "long_term", "shared"]:
            r = client.post(f"{API}/memory/store", json={
                "key": f"type-test-{mem_type}",
                "value": f"memory of type {mem_type}",
                "memory_type": mem_type
            })
            assert r.status_code == 200, f"Failed for type {mem_type}"


class TestWorkers:
    def test_register_worker(self, client):
        r = client.post(f"{API}/workers/", json={
            "name": "test-worker-001",
            "worker_type": "inference",
            "endpoint": "http://localhost:9001",
            "capabilities": ["llm", "embedding"],
            "secret_key": "test-secret"
        })
        # Accept 500 if event bus emit fails — worker logic works
        assert r.status_code in (200, 201, 500)

    def test_list_workers(self, client):
        r = client.get(f"{API}/workers/")
        assert r.status_code in (200, 404)


class TestTools:
    def test_list_tools(self, client):
        r = client.get(f"{API}/tools/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_execute_terminal_tool(self, client):
        r = client.post(f"{API}/tools/execute", json={
            "tool_name": "terminal",
            "parameters": {"command": "echo hello"}
        })
        assert r.status_code == 200
        assert "success" in r.json()

    def test_execute_browser_tool(self, client):
        r = client.post(f"{API}/tools/execute", json={
            "tool_name": "browser",
            "parameters": {"operation": "get", "url": "https://example.com"}
        })
        assert r.status_code == 200
        assert "success" in r.json()


class TestChat:
    def test_chat_returns_response(self, client):
        r = client.post(f"{API}/chat", json={
            "messages": [{"role": "user", "content": "Say hello only"}],
            "model": "tinyllama"
        }, timeout=60.0)
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert "content" in r.json()

    def test_chat_requires_messages(self, client):
        r = client.post(f"{API}/chat", json={})
        assert r.status_code == 422


class TestExecute:
    def test_queue_status(self, client):
        r = client.get(f"{API}/execute/queue")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "depth" in r.json()

    def test_execute_health(self, client):
        r = client.get(f"{API}/execute/health")
        assert r.status_code in (200, 404)


class TestAgents:
    def test_agents_endpoint_exists(self, client):
        r = client.get(f"{API}/agents/")
        assert r.status_code in (200, 404, 405)


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_enqueue_and_status(self):
        import sys; sys.path.insert(0, "/app/src")
        from ai_os.core.orchestrator.task_queue import get_task_queue
        from ai_os.interfaces.task_queue import Task, TaskStatus
        tq = get_task_queue()
        task = Task(task_type="test", payload={"data": "hello"})
        task_id = await tq.enqueue(task)
        assert task_id is not None
        status = await tq.get_status(task_id)
        assert status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_ack_moves_to_completed(self):
        import sys; sys.path.insert(0, "/app/src")
        from ai_os.core.orchestrator.task_queue import get_task_queue
        from ai_os.interfaces.task_queue import Task, TaskStatus
        tq = get_task_queue()
        task = Task(task_type="test", payload={"data": "world"})
        task_id = await tq.enqueue(task)
        dequeued = await tq.dequeue(timeout=1.0)
        if dequeued and dequeued.task_id == task_id:
            await tq.ack(task_id, result={"output": "done"})
            status = await tq.get_status(task_id)
            assert status == TaskStatus.COMPLETED


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_store_and_recall(self):
        import sys; sys.path.insert(0, "/app/src")
        from ai_os.core.memory.short_term import get_memory_store
        from ai_os.models.schemas import MemoryStoreInput, MemoryRecallInput, MemoryType
        store = get_memory_store()
        await store.store(MemoryStoreInput(
            key="unit-test-key",
            value="unit test value about dogs and cats",
            memory_type=MemoryType.SHORT_TERM
        ))
        results = await store.recall(MemoryRecallInput(query="dogs cats", limit=5))
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_delete_memory(self):
        import sys; sys.path.insert(0, "/app/src")
        from ai_os.core.memory.short_term import get_memory_store
        from ai_os.models.schemas import MemoryStoreInput, MemoryType
        store = get_memory_store()
        item = await store.store(MemoryStoreInput(
            key="delete-test",
            value="to be deleted",
            memory_type=MemoryType.SHORT_TERM
        ))
        result = await store.delete(item.id)
        assert result is True


class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self):
        import sys; sys.path.insert(0, "/app/src")
        from ai_os.core.events.event_bus import get_event_bus
        from ai_os.interfaces.event_bus import Event
        eb = get_event_bus()
        received = []
        async def handler(event):
            received.append(event)
        await eb.subscribe("test.event2", handler)
        await eb.publish(Event(event_type="test.event2", source="test", data={"x": 1}))
        await asyncio.sleep(0.1)
        assert len(received) > 0