"""
AI-OS n8n Workflow Integration
================================
Create, manage, execute, and deploy n8n workflows programmatically.
Supports workflow splitting, node activation/deactivation, and Docker deployment.

n8n API docs: https://docs.n8n.io/api/
"""

import os
import json
import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
N8N_EMAIL = os.getenv("N8N_EMAIL", "admin@aios.local")
N8N_PASSWORD = os.getenv("N8N_PASSWORD", "admin123")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class N8NNode:
    """A single node in an n8n workflow"""
    id: str
    name: str
    type: str
    position: List[int] = field(default_factory=lambda: [0, 0])
    parameters: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, Any] = field(default_factory=dict)
    disabled: bool = False
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "position": self.position,
            "parameters": self.parameters,
            "credentials": self.credentials,
            "disabled": self.disabled,
            "notes": self.notes,
            "typeVersion": 1,
        }


@dataclass
class N8NConnection:
    """Connection between two nodes"""
    source_node: str
    source_output: int = 0
    target_node: str = ""
    target_input: int = 0


@dataclass
class N8NWorkflow:
    """Complete n8n workflow definition"""
    id: Optional[str]
    name: str
    nodes: List[N8NNode] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)
    active: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": self.connections,
            "active": self.active,
            "settings": self.settings or {"executionOrder": "v1"},
            "tags": self.tags,
        }


@dataclass
class WorkflowExecution:
    """Result of a workflow execution"""
    execution_id: str
    workflow_id: str
    status: str  # running, success, error, waiting
    started_at: str
    finished_at: Optional[str] = None
    data: Optional[Dict] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Node Templates
# ---------------------------------------------------------------------------

class N8NNodeTemplates:
    """Pre-built node templates for common operations"""

    @staticmethod
    def webhook(name: str = "Webhook", path: str = "/webhook", method: str = "POST") -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.webhook",
            position=[240, 300],
            parameters={
                "path": path,
                "httpMethod": method,
                "responseMode": "onReceived",
            }
        )

    @staticmethod
    def http_request(name: str, url: str, method: str = "GET",
                     body: Optional[Dict] = None) -> N8NNode:
        params = {"method": method, "url": url, "options": {}}
        if body:
            params["sendBody"] = True
            params["bodyParameters"] = {"parameters": [
                {"name": k, "value": v} for k, v in body.items()
            ]}
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.httpRequest",
            position=[480, 300],
            parameters=params
        )

    @staticmethod
    def code(name: str, code: str, language: str = "javaScript") -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.code",
            position=[720, 300],
            parameters={"language": language, "jsCode": code}
        )

    @staticmethod
    def set_data(name: str, values: Dict[str, str]) -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.set",
            position=[960, 300],
            parameters={
                "mode": "manual",
                "duplicateItem": False,
                "assignments": {"assignments": [
                    {"id": str(i), "name": k, "value": v, "type": "string"}
                    for i, (k, v) in enumerate(values.items())
                ]}
            }
        )

    @staticmethod
    def schedule(name: str = "Schedule", cron: str = "0 * * * *") -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.scheduleTrigger",
            position=[240, 300],
            parameters={"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}}
        )

    @staticmethod
    def if_condition(name: str, left: str, operator: str, right: str) -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.if",
            position=[720, 300],
            parameters={
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                    "conditions": [{"leftValue": left, "operator": {"type": "string", "operation": operator}, "rightValue": right}],
                    "combinator": "and"
                }
            }
        )

    @staticmethod
    def send_email(name: str, to: str, subject: str, body: str) -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.emailSend",
            position=[960, 300],
            parameters={"toEmail": to, "subject": subject, "emailType": "text", "message": body}
        )

    @staticmethod
    def redis_set(name: str, key: str, value: str) -> N8NNode:
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.redis",
            position=[960, 300],
            parameters={"operation": "set", "key": key, "value": value}
        )

    @staticmethod
    def llm_call(name: str, prompt: str, model: str = "tinyllama") -> N8NNode:
        """HTTP node configured to call the AI-OS chat endpoint"""
        return N8NNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            type="n8n-nodes-base.httpRequest",
            position=[720, 300],
            parameters={
                "method": "POST",
                "url": f"{os.getenv('AIOS_BASE_URL', 'http://app:8080')}/api/v1/chat",
                "sendHeaders": True,
                "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
                "sendBody": True,
                "bodyContentType": "json",
                "bodyParameters": {"parameters": [
                    {"name": "messages", "value": f'[{{"role":"user","content":"{prompt}"}}]'},
                    {"name": "model", "value": model}
                ]}
            }
        )


# ---------------------------------------------------------------------------
# Workflow Builder
# ---------------------------------------------------------------------------

class N8NWorkflowBuilder:
    """Fluent API for building n8n workflows"""

    def __init__(self, name: str):
        self._workflow = N8NWorkflow(id=None, name=name)
        self._last_node: Optional[str] = None
        self._x = 240
        self._y = 300

    def add_node(self, node: N8NNode, connect_to_last: bool = True) -> "N8NWorkflowBuilder":
        node.position = [self._x, self._y]
        self._x += 240
        self._workflow.nodes.append(node)

        if connect_to_last and self._last_node:
            if self._last_node not in self._workflow.connections:
                self._workflow.connections[self._last_node] = {"main": [[{"node": node.name, "type": "main", "index": 0}]]}
            else:
                self._workflow.connections[self._last_node]["main"][0].append(
                    {"node": node.name, "type": "main", "index": 0}
                )

        self._last_node = node.name
        return self

    def set_active(self, active: bool = True) -> "N8NWorkflowBuilder":
        self._workflow.active = active
        return self

    def add_tag(self, tag: str) -> "N8NWorkflowBuilder":
        self._workflow.tags.append(tag)
        return self

    def build(self) -> N8NWorkflow:
        return self._workflow


# ---------------------------------------------------------------------------
# Workflow Splitter
# ---------------------------------------------------------------------------

class WorkflowSplitter:
    """
    Splits complex workflows into smaller manageable sub-workflows.
    Connects them via webhooks or message queues.
    """

    def split_by_size(
        self,
        nodes: List[N8NNode],
        max_nodes_per_workflow: int = 10
    ) -> List[List[N8NNode]]:
        """Split a list of nodes into chunks"""
        chunks = []
        for i in range(0, len(nodes), max_nodes_per_workflow):
            chunks.append(nodes[i:i + max_nodes_per_workflow])
        return chunks

    def create_sub_workflows(
        self,
        base_name: str,
        node_chunks: List[List[N8NNode]]
    ) -> List[N8NWorkflow]:
        """Create sub-workflows from node chunks, connected via webhooks"""
        workflows = []
        for i, chunk in enumerate(node_chunks):
            name = f"{base_name} - Part {i + 1}"
            builder = N8NWorkflowBuilder(name)

            # Add webhook trigger for sub-workflows (except first)
            if i > 0:
                webhook = N8NNodeTemplates.webhook(
                    name=f"Input from Part {i}",
                    path=f"/workflow/{base_name.lower().replace(' ', '-')}-{i}"
                )
                builder.add_node(webhook, connect_to_last=False)

            for node in chunk:
                builder.add_node(node)

            # Add webhook call to next sub-workflow (except last)
            if i < len(node_chunks) - 1:
                next_path = f"/workflow/{base_name.lower().replace(' ', '-')}-{i + 1}"
                http_node = N8NNodeTemplates.http_request(
                    name=f"Trigger Part {i + 2}",
                    url=f"{N8N_BASE_URL}{next_path}",
                    method="POST"
                )
                builder.add_node(http_node)

            workflows.append(builder.build())
        return workflows


# ---------------------------------------------------------------------------
# n8n Client
# ---------------------------------------------------------------------------

class N8NClient:
    """
    Full n8n API client.
    Manages workflows, executions, credentials, and tags.
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        self._base_url = (base_url or N8N_BASE_URL).rstrip("/")
        self._api_key = api_key or N8N_API_KEY
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["X-N8N-API-KEY"] = self._api_key
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30.0
            )
        return self._client

    async def health_check(self) -> bool:
        """Check if n8n is reachable"""
        try:
            response = await self._get_client().get("/healthz")
            return response.status_code == 200
        except Exception:
            return False

    async def get_workflows(self) -> List[Dict]:
        """List all workflows"""
        try:
            response = await self._get_client().get("/api/v1/workflows")
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Failed to get workflows: {e}")
            return []

    async def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get a specific workflow"""
        try:
            response = await self._get_client().get(f"/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get workflow {workflow_id}: {e}")
            return None

    async def create_workflow(self, workflow: N8NWorkflow) -> Optional[Dict]:
        """Create a new workflow"""
        try:
            response = await self._get_client().post(
                "/api/v1/workflows",
                json=workflow.to_dict()
            )
            response.raise_for_status()
            data = response.json()
            workflow.id = str(data.get("id", ""))
            logger.info(f"Created workflow: {workflow.name} (id={workflow.id})")
            return data
        except Exception as e:
            logger.error(f"Failed to create workflow {workflow.name}: {e}")
            return None

    async def update_workflow(self, workflow_id: str, workflow: N8NWorkflow) -> Optional[Dict]:
        """Update an existing workflow"""
        try:
            response = await self._get_client().put(
                f"/api/v1/workflows/{workflow_id}",
                json=workflow.to_dict()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update workflow {workflow_id}: {e}")
            return None

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        try:
            response = await self._get_client().delete(f"/api/v1/workflows/{workflow_id}")
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to delete workflow {workflow_id}: {e}")
            return False

    async def activate_workflow(self, workflow_id: str) -> bool:
        """Activate a workflow"""
        try:
            response = await self._get_client().patch(
                f"/api/v1/workflows/{workflow_id}/activate"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to activate workflow {workflow_id}: {e}")
            return False

    async def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate a workflow"""
        try:
            response = await self._get_client().patch(
                f"/api/v1/workflows/{workflow_id}/deactivate"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to deactivate workflow {workflow_id}: {e}")
            return False

    async def execute_workflow(self, workflow_id: str, data: Dict = None) -> Optional[WorkflowExecution]:
        """Manually execute a workflow"""
        try:
            payload = {}
            if data:
                payload["data"] = data
            response = await self._get_client().post(
                f"/api/v1/workflows/{workflow_id}/run",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return WorkflowExecution(
                execution_id=str(result.get("executionId", "")),
                workflow_id=workflow_id,
                status="running",
                started_at=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to execute workflow {workflow_id}: {e}")
            return None

    async def get_executions(self, workflow_id: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Get execution history"""
        try:
            params = {"limit": limit}
            if workflow_id:
                params["workflowId"] = workflow_id
            response = await self._get_client().get("/api/v1/executions", params=params)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Failed to get executions: {e}")
            return []

    async def toggle_node(
        self,
        workflow_id: str,
        node_name: str,
        disabled: bool
    ) -> bool:
        """Enable or disable a specific node in a workflow"""
        workflow_data = await self.get_workflow(workflow_id)
        if not workflow_data:
            return False
        nodes = workflow_data.get("nodes", [])
        for node in nodes:
            if node.get("name") == node_name:
                node["disabled"] = disabled
                break
        try:
            response = await self._get_client().put(
                f"/api/v1/workflows/{workflow_id}",
                json=workflow_data
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to toggle node {node_name}: {e}")
            return False

    async def create_from_natural_language(self, description: str) -> Optional[N8NWorkflow]:
        """
        Generate a workflow from a natural language description using LLM.
        Calls the AI-OS chat endpoint to generate the workflow JSON.
        """
        prompt = f"""Create an n8n workflow for: {description}

Return ONLY a JSON object with this exact structure:
{{
  "name": "workflow name",
  "nodes": [
    {{
      "name": "Node Name",
      "type": "n8n-nodes-base.webhook",
      "parameters": {{}},
      "position": [240, 300]
    }}
  ],
  "connections": {{
    "Node Name": {{
      "main": [[{{"node": "Next Node", "type": "main", "index": 0}}]]
    }}
  }}
}}

Common node types: n8n-nodes-base.webhook, n8n-nodes-base.httpRequest, 
n8n-nodes-base.code, n8n-nodes-base.set, n8n-nodes-base.if, 
n8n-nodes-base.scheduleTrigger, n8n-nodes-base.emailSend"""

        try:
            aios_url = os.getenv("AIOS_BASE_URL", "http://localhost:8080")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{aios_url}/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "model": os.getenv("DEFAULT_MODEL", "tinyllama")
                    }
                )
                if response.status_code == 200:
                    content = response.json().get("content", "")
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        workflow_data = json.loads(json_match.group())
                        nodes = [
                            N8NNode(
                                id=str(uuid.uuid4())[:8],
                                name=n.get("name", "Node"),
                                type=n.get("type", "n8n-nodes-base.code"),
                                position=n.get("position", [240, 300]),
                                parameters=n.get("parameters", {})
                            )
                            for n in workflow_data.get("nodes", [])
                        ]
                        return N8NWorkflow(
                            id=None,
                            name=workflow_data.get("name", description[:50]),
                            nodes=nodes,
                            connections=workflow_data.get("connections", {})
                        )
        except Exception as e:
            logger.error(f"NL workflow generation failed: {e}")
        return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_n8n_client: Optional[N8NClient] = None


def get_n8n_client() -> N8NClient:
    global _n8n_client
    if _n8n_client is None:
        _n8n_client = N8NClient()
    return _n8n_client


def get_workflow_splitter() -> WorkflowSplitter:
    return WorkflowSplitter()
