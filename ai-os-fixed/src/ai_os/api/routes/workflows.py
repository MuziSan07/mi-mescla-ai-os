"""
AI-OS Workflow API Routes
n8n and ComfyUI workflow management endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData


logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflows"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class N8NCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: str = "webhook"  # webhook, schedule, manual
    cron: Optional[str] = "0 * * * *"
    steps: Optional[List[Dict[str, Any]]] = None
    activate: bool = False


class N8NNaturalLanguageRequest(BaseModel):
    description: str
    activate: bool = False


class N8NToggleNodeRequest(BaseModel):
    workflow_id: str
    node_name: str
    disabled: bool


class ComfyTxt2ImgRequest(BaseModel):
    positive_prompt: str
    negative_prompt: str = "ugly, blurry, low quality, deformed"
    model: str = "v1-5-pruned-emaonly.ckpt"
    width: int = 512
    height: int = 512
    steps: int = 20
    cfg: float = 7.0
    seed: int = 42
    wait_for_result: bool = False
    timeout: float = 120.0


class ComfyValidateRequest(BaseModel):
    workflow: Dict[str, Any]


class ComfySplitRequest(BaseModel):
    name: str
    node_count: int = 20
    max_nodes_per_part: int = 10


# ---------------------------------------------------------------------------
# n8n Endpoints
# ---------------------------------------------------------------------------

@router.get("/workflows/n8n/health")
async def n8n_health(user: TokenData = Depends(require_auth)):
    """Check if n8n is reachable"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    ok = await client.health_check()
    return {
        "n8n_available": ok,
        "n8n_url": client._base_url,
        "note": "Start n8n with: docker run -p 5678:5678 n8nio/n8n" if not ok else None
    }


@router.get("/workflows/n8n/list")
async def n8n_list_workflows(user: TokenData = Depends(require_auth)):
    """List all n8n workflows"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    workflows = await client.get_workflows()
    return {"count": len(workflows), "workflows": workflows}


@router.post("/workflows/n8n/create")
async def n8n_create_workflow(request: N8NCreateRequest,
    user: TokenData = Depends(require_auth)
):
    """Create a new n8n workflow with common node types"""
    from ai_os.utils.n8n_integration import (
        get_n8n_client, N8NWorkflowBuilder, N8NNodeTemplates
    )

    client = get_n8n_client()
    builder = N8NWorkflowBuilder(request.name)
    t = N8NNodeTemplates

    # Add trigger
    if request.trigger == "webhook":
        builder.add_node(
            t.webhook(name="Webhook Trigger", path=f"/{request.name.lower().replace(' ', '-')}"),
            connect_to_last=False
        )
    elif request.trigger == "schedule":
        builder.add_node(
            t.schedule(name="Schedule Trigger", cron=request.cron or "0 * * * *"),
            connect_to_last=False
        )

    # Add custom steps if provided
    if request.steps:
        for step in request.steps:
            step_type = step.get("type", "http")
            if step_type == "http":
                builder.add_node(t.http_request(
                    name=step.get("name", "HTTP Request"),
                    url=step.get("url", "https://example.com"),
                    method=step.get("method", "GET")
                ))
            elif step_type == "code":
                builder.add_node(t.code(
                    name=step.get("name", "Code"),
                    code=step.get("code", "return items;")
                ))
            elif step_type == "set":
                builder.add_node(t.set_data(
                    name=step.get("name", "Set Data"),
                    values=step.get("values", {})
                ))
            elif step_type == "llm":
                builder.add_node(t.llm_call(
                    name=step.get("name", "LLM Call"),
                    prompt=step.get("prompt", "Process this: {{$json}}")
                ))
    else:
        # Default: add a code node as placeholder
        builder.add_node(t.code(
            name="Process",
            code="// Add your logic here\nreturn items;"
        ))

    if request.activate:
        builder.set_active(True)

    workflow = builder.build()
    result = await client.create_workflow(workflow)

    if not result:
        raise HTTPException(status_code=503, detail="n8n not available or workflow creation failed")

    return {
        "id": result.get("id"),
        "name": result.get("name"),
        "active": result.get("active"),
        "created": True,
        "n8n_url": f"{client._base_url}/workflow/{result.get('id')}"
    }


@router.post("/workflows/n8n/from-description")
async def n8n_create_from_description(request: N8NNaturalLanguageRequest,
    user: TokenData = Depends(require_auth)
):
    """Generate and create an n8n workflow from natural language"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()

    workflow = await client.create_from_natural_language(request.description)
    if not workflow:
        raise HTTPException(status_code=500, detail="Failed to generate workflow from description")

    result = await client.create_workflow(workflow)
    if not result:
        return {
            "created": False,
            "workflow_preview": workflow.to_dict(),
            "note": "Workflow generated but n8n not available. Import manually."
        }

    if request.activate:
        await client.activate_workflow(str(result.get("id", "")))

    return {
        "id": result.get("id"),
        "name": result.get("name"),
        "active": result.get("active"),
        "created": True,
        "description": request.description
    }


@router.post("/workflows/n8n/{workflow_id}/activate")
async def n8n_activate(workflow_id: str,
    user: TokenData = Depends(require_auth)
):
    """Activate an n8n workflow"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    ok = await client.activate_workflow(workflow_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to activate workflow")
    return {"workflow_id": workflow_id, "active": True}


@router.post("/workflows/n8n/{workflow_id}/deactivate")
async def n8n_deactivate(workflow_id: str,
    user: TokenData = Depends(require_auth)
):
    """Deactivate an n8n workflow"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    ok = await client.deactivate_workflow(workflow_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to deactivate workflow")
    return {"workflow_id": workflow_id, "active": False}


@router.post("/workflows/n8n/{workflow_id}/execute")
async def n8n_execute(workflow_id: str, data: Optional[Dict[str, Any]] = None,
    user: TokenData = Depends(require_auth)
):
    """Manually execute an n8n workflow"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    execution = await client.execute_workflow(workflow_id, data)
    if not execution:
        raise HTTPException(status_code=500, detail="Failed to execute workflow")
    return {
        "execution_id": execution.execution_id,
        "workflow_id": workflow_id,
        "status": execution.status
    }


@router.post("/workflows/n8n/toggle-node")
async def n8n_toggle_node(request: N8NToggleNodeRequest,
    user: TokenData = Depends(require_auth)
):
    """Enable or disable a specific node in a workflow"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    ok = await client.toggle_node(request.workflow_id, request.node_name, request.disabled)
    return {
        "workflow_id": request.workflow_id,
        "node": request.node_name,
        "disabled": request.disabled,
        "success": ok
    }


@router.delete("/workflows/n8n/{workflow_id}")
async def n8n_delete(workflow_id: str,
    user: TokenData = Depends(require_auth)
):
    """Delete an n8n workflow"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    ok = await client.delete_workflow(workflow_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete workflow")
    return {"workflow_id": workflow_id, "deleted": True}


@router.get("/workflows/n8n/{workflow_id}/executions")
async def n8n_executions(workflow_id: str, limit: int = 20,
    user: TokenData = Depends(require_auth)
):
    """Get execution history for a workflow"""
    from ai_os.utils.n8n_integration import get_n8n_client
    client = get_n8n_client()
    executions = await client.get_executions(workflow_id, limit)
    return {"workflow_id": workflow_id, "executions": executions}


# ---------------------------------------------------------------------------
# ComfyUI Endpoints
# ---------------------------------------------------------------------------

@router.get("/workflows/comfy/health")
async def comfy_health(user: TokenData = Depends(require_auth)):
    """Check if ComfyUI is reachable"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()
    ok = await client.health_check()
    stats = await client.get_system_stats() if ok else None
    return {
        "comfyui_available": ok,
        "comfyui_url": client._base_url,
        "system_stats": stats,
        "note": "Start ComfyUI with: python main.py --listen" if not ok else None
    }


@router.get("/workflows/comfy/models")
async def comfy_models(user: TokenData = Depends(require_auth)):
    """List available models, LoRAs, and VAEs in ComfyUI"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()
    models = await client.get_models()
    return {"models": models}


@router.post("/workflows/comfy/txt2img")
async def comfy_txt2img(request: ComfyTxt2ImgRequest,
    user: TokenData = Depends(require_auth)
):
    """Generate an image using ComfyUI text-to-image"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()

    ok = await client.health_check()
    if not ok:
        raise HTTPException(
            status_code=503,
            detail=f"ComfyUI not available at {client._base_url}. Start with: python main.py --listen"
        )

    execution = await client.generate_txt2img(
        positive_prompt=request.positive_prompt,
        negative_prompt=request.negative_prompt,
        model=request.model,
        width=request.width,
        height=request.height,
        steps=request.steps,
        cfg=request.cfg,
        seed=request.seed,
        wait=request.wait_for_result,
        timeout=request.timeout
    )

    return {
        "prompt_id": execution.prompt_id,
        "status": execution.status,
        "image_count": len(execution.images),
        "image_urls": execution.image_urls,
        "images_base64": execution.images if execution.images else None,
        "error": execution.error
    }


@router.post("/workflows/comfy/validate")
async def comfy_validate(request: ComfyValidateRequest,
    user: TokenData = Depends(require_auth)
):
    """Validate a ComfyUI workflow for broken connections"""
    from ai_os.utils.comfyui_integration import (
        ComfyWorkflow, ComfyNode, get_connection_validator
    )

    workflow = ComfyWorkflow()
    for node_id, node_data in request.workflow.items():
        workflow.nodes[node_id] = ComfyNode(
            id=node_id,
            type=node_data.get("class_type", ""),
            inputs=node_data.get("inputs", {}),
            meta=node_data.get("_meta", {})
        )

    validator = get_connection_validator()
    issues = validator.validate(workflow)

    return {
        "valid": len(issues) == 0,
        "issue_count": len(issues),
        "issues": [
            {
                "source_node": i.source_node,
                "target_node": i.target_node,
                "target_input": i.target_input,
                "issue_type": i.issue_type,
                "description": i.description
            }
            for i in issues
        ]
    }


@router.post("/workflows/comfy/optimize")
async def comfy_optimize(request: ComfyValidateRequest,
    user: TokenData = Depends(require_auth)
):
    """Validate and optimize a ComfyUI workflow"""
    from ai_os.utils.comfyui_integration import (
        ComfyWorkflow, ComfyNode,
        get_connection_validator, get_workflow_optimizer
    )

    workflow = ComfyWorkflow()
    for node_id, node_data in request.workflow.items():
        workflow.nodes[node_id] = ComfyNode(
            id=node_id,
            type=node_data.get("class_type", ""),
            inputs=node_data.get("inputs", {}),
            meta=node_data.get("_meta", {})
        )

    validator = get_connection_validator()
    optimizer = get_workflow_optimizer()

    workflow, fixes = validator.auto_fix(workflow)
    workflow, optimizations = optimizer.optimize(workflow)

    return {
        "optimized_workflow": workflow.to_prompt(),
        "fixes_applied": fixes,
        "optimizations": optimizations,
        "node_count": len(workflow.nodes)
    }


@router.get("/workflows/comfy/queue")
async def comfy_queue(user: TokenData = Depends(require_auth)):
    """Get ComfyUI execution queue status"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()
    queue = await client.get_queue_status()
    return queue


@router.post("/workflows/comfy/interrupt")
async def comfy_interrupt(user: TokenData = Depends(require_auth)):
    """Interrupt the current ComfyUI execution"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()
    ok = await client.interrupt()
    return {"interrupted": ok}


@router.post("/workflows/comfy/clear-queue")
async def comfy_clear_queue(user: TokenData = Depends(require_auth)):
    """Clear the ComfyUI execution queue"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()
    ok = await client.clear_queue()
    return {"cleared": ok}


@router.get("/workflows/comfy/history/{prompt_id}")
async def comfy_history(prompt_id: str,
    user: TokenData = Depends(require_auth)
):
    """Get execution history for a specific prompt"""
    from ai_os.utils.comfyui_integration import get_comfy_client
    client = get_comfy_client()
    history = await client.get_history(prompt_id)
    return history


@router.get("/workflows/health")
async def workflows_health(user: TokenData = Depends(require_auth)):
    """Combined health check for all workflow engines"""
    from ai_os.utils.n8n_integration import get_n8n_client
    from ai_os.utils.comfyui_integration import get_comfy_client

    n8n_ok = await get_n8n_client().health_check()
    comfy_ok = await get_comfy_client().health_check()

    return {
        "n8n": {"available": n8n_ok, "url": get_n8n_client()._base_url},
        "comfyui": {"available": comfy_ok, "url": get_comfy_client()._base_url},
        "any_available": n8n_ok or comfy_ok
    }
