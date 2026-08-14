"""
AI-OS ComfyUI Workflow Integration
=====================================
Create, edit, optimize and execute ComfyUI workflows programmatically.
Supports node graph management, broken connection detection, and deployment.

ComfyUI API docs: https://github.com/comfyanonymous/ComfyUI
"""

import os
import json
import asyncio
import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import base64

import httpx

logger = logging.getLogger(__name__)

COMFY_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://localhost:8188")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ComfyNode:
    """A single node in a ComfyUI workflow graph"""
    id: str
    type: str  # class_type e.g. "KSampler", "CLIPTextEncode", "VAEDecode"
    inputs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "class_type": self.type,
            "inputs": self.inputs,
            "_meta": self.meta or {"title": self.type}
        }


@dataclass
class ComfyWorkflow:
    """Complete ComfyUI workflow (prompt)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    nodes: Dict[str, ComfyNode] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_prompt(self) -> Dict:
        """Convert to ComfyUI API prompt format"""
        return {node_id: node.to_dict() for node_id, node in self.nodes.items()}

    def add_node(self, node: ComfyNode) -> str:
        """Add a node and return its ID"""
        node_id = node.id or str(len(self.nodes) + 1)
        self.nodes[node_id] = node
        return node_id


@dataclass
class ComfyExecution:
    """Result of a ComfyUI workflow execution"""
    prompt_id: str
    status: str  # pending, running, completed, error
    images: List[str] = field(default_factory=list)  # base64 encoded
    image_urls: List[str] = field(default_factory=list)
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: Optional[str] = None


@dataclass
class ConnectionIssue:
    """Detected connection issue in a workflow"""
    source_node: str
    source_output: str
    target_node: str
    target_input: str
    issue_type: str  # missing_source, type_mismatch, broken_link
    description: str


# ---------------------------------------------------------------------------
# Node Templates
# ---------------------------------------------------------------------------

class ComfyNodeTemplates:
    """Pre-built ComfyUI node templates"""

    @staticmethod
    def checkpoint_loader(model_name: str = "v1-5-pruned-emaonly.ckpt") -> ComfyNode:
        return ComfyNode(
            id="1",
            type="CheckpointLoaderSimple",
            inputs={"ckpt_name": model_name},
            meta={"title": "Load Checkpoint"}
        )

    @staticmethod
    def clip_text_encode(text: str, clip_ref: Tuple = ("1", 1), node_id: str = "2") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="CLIPTextEncode",
            inputs={"text": text, "clip": list(clip_ref)},
            meta={"title": "CLIP Text Encode (Positive)" if node_id == "2" else "CLIP Text Encode (Negative)"}
        )

    @staticmethod
    def empty_latent(width: int = 512, height: int = 512,
                     batch_size: int = 1, node_id: str = "4") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="EmptyLatentImage",
            inputs={"width": width, "height": height, "batch_size": batch_size},
            meta={"title": "Empty Latent Image"}
        )

    @staticmethod
    def ksampler(
        model_ref: Tuple = ("1", 0),
        positive_ref: Tuple = ("2", 0),
        negative_ref: Tuple = ("3", 0),
        latent_ref: Tuple = ("4", 0),
        seed: int = 42,
        steps: int = 20,
        cfg: float = 7.0,
        sampler: str = "euler",
        scheduler: str = "normal",
        denoise: float = 1.0,
        node_id: str = "5"
    ) -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="KSampler",
            inputs={
                "model": list(model_ref),
                "positive": list(positive_ref),
                "negative": list(negative_ref),
                "latent_image": list(latent_ref),
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
            },
            meta={"title": "KSampler"}
        )

    @staticmethod
    def vae_decode(samples_ref: Tuple = ("5", 0),
                   vae_ref: Tuple = ("1", 2), node_id: str = "6") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="VAEDecode",
            inputs={"samples": list(samples_ref), "vae": list(vae_ref)},
            meta={"title": "VAE Decode"}
        )

    @staticmethod
    def save_image(images_ref: Tuple = ("6", 0),
                   prefix: str = "aios_", node_id: str = "7") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="SaveImage",
            inputs={"images": list(images_ref), "filename_prefix": prefix},
            meta={"title": "Save Image"}
        )

    @staticmethod
    def upscale(image_ref: Tuple = ("6", 0),
                model: str = "RealESRGAN_x4plus.pth",
                scale: float = 2.0, node_id: str = "8") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="UpscaleModelLoader",
            inputs={"model_name": model},
            meta={"title": "Upscale Model"}
        )

    @staticmethod
    def lora_loader(model_ref: Tuple = ("1", 0), clip_ref: Tuple = ("1", 1),
                    lora_name: str = "", strength: float = 1.0,
                    node_id: str = "9") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="LoraLoader",
            inputs={
                "model": list(model_ref),
                "clip": list(clip_ref),
                "lora_name": lora_name,
                "strength_model": strength,
                "strength_clip": strength,
            },
            meta={"title": "Load LoRA"}
        )

    @staticmethod
    def image_preview(images_ref: Tuple = ("6", 0), node_id: str = "99") -> ComfyNode:
        return ComfyNode(
            id=node_id,
            type="PreviewImage",
            inputs={"images": list(images_ref)},
            meta={"title": "Preview Image"}
        )


# ---------------------------------------------------------------------------
# Workflow Builder
# ---------------------------------------------------------------------------

class ComfyWorkflowBuilder:
    """Fluent builder for ComfyUI workflows"""

    def __init__(self, name: str = ""):
        self._workflow = ComfyWorkflow(name=name)

    def add_node(self, node: ComfyNode) -> "ComfyWorkflowBuilder":
        self._workflow.add_node(node)
        return self

    def build(self) -> ComfyWorkflow:
        return self._workflow

    @classmethod
    def txt2img(
        cls,
        positive_prompt: str,
        negative_prompt: str = "ugly, blurry, low quality",
        model: str = "v1-5-pruned-emaonly.ckpt",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = 42,
    ) -> "ComfyWorkflow":
        """Standard text-to-image workflow"""
        builder = cls(name=f"txt2img: {positive_prompt[:30]}")
        t = ComfyNodeTemplates
        return (
            builder
            .add_node(t.checkpoint_loader(model))
            .add_node(t.clip_text_encode(positive_prompt, ("1", 1), "2"))
            .add_node(t.clip_text_encode(negative_prompt, ("1", 1), "3"))
            .add_node(t.empty_latent(width, height, 1, "4"))
            .add_node(t.ksampler(("1", 0), ("2", 0), ("3", 0), ("4", 0), seed, steps, cfg, node_id="5"))
            .add_node(t.vae_decode(("5", 0), ("1", 2), "6"))
            .add_node(t.save_image(("6", 0), "txt2img_", "7"))
            .build()
        )

    @classmethod
    def txt2img_with_lora(
        cls,
        positive_prompt: str,
        negative_prompt: str = "ugly, blurry",
        model: str = "v1-5-pruned-emaonly.ckpt",
        lora_name: str = "",
        lora_strength: float = 0.8,
        width: int = 512,
        height: int = 512,
        steps: int = 25,
        seed: int = 42,
    ) -> "ComfyWorkflow":
        """Text-to-image with LoRA"""
        builder = cls(name=f"txt2img+lora: {positive_prompt[:30]}")
        t = ComfyNodeTemplates
        return (
            builder
            .add_node(t.checkpoint_loader(model))
            .add_node(t.lora_loader(("1", 0), ("1", 1), lora_name, lora_strength, "2"))
            .add_node(t.clip_text_encode(positive_prompt, ("2", 1), "3"))
            .add_node(t.clip_text_encode(negative_prompt, ("2", 1), "4"))
            .add_node(t.empty_latent(width, height, 1, "5"))
            .add_node(t.ksampler(("2", 0), ("3", 0), ("4", 0), ("5", 0), seed, steps, node_id="6"))
            .add_node(t.vae_decode(("6", 0), ("1", 2), "7"))
            .add_node(t.save_image(("7", 0), "lora_", "8"))
            .build()
        )


# ---------------------------------------------------------------------------
# Connection Validator
# ---------------------------------------------------------------------------

class ComfyConnectionValidator:
    """Detects broken or invalid connections in ComfyUI workflows"""

    # Expected output types per node type
    NODE_OUTPUTS = {
        "CheckpointLoaderSimple": ["MODEL", "CLIP", "VAE"],
        "CLIPTextEncode": ["CONDITIONING"],
        "EmptyLatentImage": ["LATENT"],
        "KSampler": ["LATENT"],
        "VAEDecode": ["IMAGE"],
        "SaveImage": [],
        "PreviewImage": [],
        "LoraLoader": ["MODEL", "CLIP"],
        "VAELoader": ["VAE"],
        "UpscaleModelLoader": ["UPSCALE_MODEL"],
        "ImageUpscaleWithModel": ["IMAGE"],
    }

    # Expected input types per node type
    NODE_INPUTS = {
        "CLIPTextEncode": {"clip": "CLIP"},
        "KSampler": {
            "model": "MODEL",
            "positive": "CONDITIONING",
            "negative": "CONDITIONING",
            "latent_image": "LATENT"
        },
        "VAEDecode": {"samples": "LATENT", "vae": "VAE"},
        "SaveImage": {"images": "IMAGE"},
        "PreviewImage": {"images": "IMAGE"},
        "LoraLoader": {"model": "MODEL", "clip": "CLIP"},
        "ImageUpscaleWithModel": {"upscale_model": "UPSCALE_MODEL", "image": "IMAGE"},
    }

    def validate(self, workflow: ComfyWorkflow) -> List[ConnectionIssue]:
        """Find all connection issues in a workflow"""
        issues = []
        node_ids = set(workflow.nodes.keys())

        for node_id, node in workflow.nodes.items():
            for input_name, input_value in node.inputs.items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_id, output_idx = input_value
                    source_id = str(source_id)

                    if source_id not in node_ids:
                        issues.append(ConnectionIssue(
                            source_node=source_id,
                            source_output=str(output_idx),
                            target_node=node_id,
                            target_input=input_name,
                            issue_type="missing_source",
                            description=f"Node {node_id} input '{input_name}' references missing node '{source_id}'"
                        ))
                    else:
                        source_node = workflow.nodes[source_id]
                        source_outputs = self.NODE_OUTPUTS.get(source_node.type, [])
                        expected_type = self.NODE_INPUTS.get(node.type, {}).get(input_name)

                        if expected_type and source_outputs:
                            if output_idx < len(source_outputs):
                                actual_type = source_outputs[output_idx]
                                if actual_type != expected_type:
                                    issues.append(ConnectionIssue(
                                        source_node=source_id,
                                        source_output=str(output_idx),
                                        target_node=node_id,
                                        target_input=input_name,
                                        issue_type="type_mismatch",
                                        description=(
                                            f"Type mismatch: node '{node_id}' input '{input_name}' "
                                            f"expects {expected_type} but got {actual_type}"
                                        )
                                    ))
                            else:
                                issues.append(ConnectionIssue(
                                    source_node=source_id,
                                    source_output=str(output_idx),
                                    target_node=node_id,
                                    target_input=input_name,
                                    issue_type="broken_link",
                                    description=(
                                        f"Output index {output_idx} out of range for node '{source_id}' "
                                        f"which has {len(source_outputs)} outputs"
                                    )
                                ))
        return issues

    def auto_fix(self, workflow: ComfyWorkflow) -> Tuple[ComfyWorkflow, List[str]]:
        """Attempt to auto-fix connection issues"""
        fixes = []
        issues = self.validate(workflow)

        for issue in issues:
            if issue.issue_type == "missing_source":
                # Remove the broken input
                target = workflow.nodes.get(issue.target_node)
                if target and issue.target_input in target.inputs:
                    del target.inputs[issue.target_input]
                    fixes.append(f"Removed broken input '{issue.target_input}' from node '{issue.target_node}'")

        return workflow, fixes


# ---------------------------------------------------------------------------
# Workflow Optimizer
# ---------------------------------------------------------------------------

class ComfyWorkflowOptimizer:
    """Optimizes ComfyUI workflows for performance"""

    def remove_duplicate_loaders(self, workflow: ComfyWorkflow) -> ComfyWorkflow:
        """Merge duplicate checkpoint/model loader nodes"""
        loaders: Dict[str, str] = {}
        to_remove = []
        replacements: Dict[str, str] = {}

        for node_id, node in workflow.nodes.items():
            if node.type in ("CheckpointLoaderSimple", "VAELoader"):
                key = f"{node.type}:{json.dumps(node.inputs, sort_keys=True)}"
                if key in loaders:
                    replacements[node_id] = loaders[key]
                    to_remove.append(node_id)
                else:
                    loaders[key] = node_id

        # Remove duplicate nodes
        for node_id in to_remove:
            del workflow.nodes[node_id]

        # Update references in remaining nodes
        for node in workflow.nodes.values():
            for input_name, input_value in node.inputs.items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_id = str(input_value[0])
                    if source_id in replacements:
                        node.inputs[input_name] = [replacements[source_id], input_value[1]]

        return workflow

    def optimize(self, workflow: ComfyWorkflow) -> Tuple[ComfyWorkflow, List[str]]:
        """Run all optimizations"""
        optimizations = []
        before_count = len(workflow.nodes)
        workflow = self.remove_duplicate_loaders(workflow)
        after_count = len(workflow.nodes)
        if before_count != after_count:
            optimizations.append(f"Removed {before_count - after_count} duplicate loader nodes")
        return workflow, optimizations


# ---------------------------------------------------------------------------
# ComfyUI Client
# ---------------------------------------------------------------------------

class ComfyUIClient:
    """
    Full ComfyUI API client.
    Manages prompts, queue, history, and image retrieval.
    """

    def __init__(self, base_url: str = None):
        self._base_url = (base_url or COMFY_BASE_URL).rstrip("/")
        self._client_id = str(uuid.uuid4())
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=60.0
            )
        return self._client

    async def health_check(self) -> bool:
        """Check if ComfyUI is reachable"""
        try:
            response = await self._get_client().get("/system_stats")
            return response.status_code == 200
        except Exception:
            return False

    async def get_system_stats(self) -> Optional[Dict]:
        """Get ComfyUI system stats"""
        try:
            response = await self._get_client().get("/system_stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return None

    async def get_models(self) -> Dict[str, List[str]]:
        """List available models, LoRAs, and VAEs"""
        try:
            response = await self._get_client().get("/object_info")
            response.raise_for_status()
            data = response.json()
            result = {}
            for node_type in ["CheckpointLoaderSimple", "LoraLoader", "VAELoader"]:
                if node_type in data:
                    node_info = data[node_type]
                    for input_name, input_data in node_info.get("input", {}).get("required", {}).items():
                        if isinstance(input_data, list) and isinstance(input_data[0], list):
                            result[f"{node_type}/{input_name}"] = input_data[0]
            return result
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return {}

    async def queue_prompt(self, workflow: ComfyWorkflow) -> Optional[ComfyExecution]:
        """Queue a workflow for execution"""
        try:
            payload = {
                "prompt": workflow.to_prompt(),
                "client_id": self._client_id
            }
            response = await self._get_client().post("/prompt", json=payload)
            response.raise_for_status()
            data = response.json()
            prompt_id = data.get("prompt_id", "")
            logger.info(f"Queued ComfyUI prompt: {prompt_id}")
            return ComfyExecution(
                prompt_id=prompt_id,
                status="pending",
                started_at=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to queue prompt: {e}")
            return None

    async def get_queue_status(self) -> Dict:
        """Get current queue status"""
        try:
            response = await self._get_client().get("/queue")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {}

    async def get_history(self, prompt_id: Optional[str] = None) -> Dict:
        """Get execution history"""
        try:
            url = f"/history/{prompt_id}" if prompt_id else "/history"
            response = await self._get_client().get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return {}

    async def get_image(self, filename: str, subfolder: str = "",
                        folder_type: str = "output") -> Optional[bytes]:
        """Download a generated image"""
        try:
            response = await self._get_client().get(
                "/view",
                params={"filename": filename, "subfolder": subfolder, "type": folder_type}
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to get image {filename}: {e}")
            return None

    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout: float = 120.0,
        poll_interval: float = 2.0
    ) -> ComfyExecution:
        """Wait for a prompt to complete and return results"""
        start = asyncio.get_event_loop().time()
        execution = ComfyExecution(prompt_id=prompt_id, status="pending",
                                   started_at=datetime.now().isoformat())

        while (asyncio.get_event_loop().time() - start) < timeout:
            await asyncio.sleep(poll_interval)
            history = await self.get_history(prompt_id)

            if prompt_id in history:
                result = history[prompt_id]
                outputs = result.get("outputs", {})
                execution.status = "completed"
                execution.finished_at = datetime.now().isoformat()

                for node_id, output in outputs.items():
                    images = output.get("images", [])
                    for img_info in images:
                        filename = img_info.get("filename", "")
                        subfolder = img_info.get("subfolder", "")
                        img_data = await self.get_image(filename, subfolder)
                        if img_data:
                            execution.images.append(
                                base64.b64encode(img_data).decode("utf-8")
                            )
                            execution.image_urls.append(
                                f"{self._base_url}/view?filename={filename}&subfolder={subfolder}&type=output"
                            )
                return execution

            # Check if still running
            queue = await self.get_queue_status()
            running = [p[1] for p in queue.get("queue_running", [])]
            if prompt_id not in running:
                pending = [p[1] for p in queue.get("queue_pending", [])]
                if prompt_id not in pending:
                    execution.status = "error"
                    execution.error = "Prompt not found in queue or history"
                    return execution
            else:
                execution.status = "running"

        execution.status = "timeout"
        execution.error = f"Timed out after {timeout}s"
        return execution

    async def interrupt(self) -> bool:
        """Interrupt current execution"""
        try:
            response = await self._get_client().post("/interrupt")
            return response.status_code == 200
        except Exception:
            return False

    async def clear_queue(self) -> bool:
        """Clear the execution queue"""
        try:
            response = await self._get_client().post(
                "/queue",
                json={"clear": True}
            )
            return response.status_code == 200
        except Exception:
            return False

    async def generate_txt2img(
        self,
        positive_prompt: str,
        negative_prompt: str = "ugly, blurry, low quality",
        model: str = "v1-5-pruned-emaonly.ckpt",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = 42,
        wait: bool = True,
        timeout: float = 120.0
    ) -> ComfyExecution:
        """
        High-level text-to-image generation.
        Builds workflow, validates, queues, and waits for result.
        """
        workflow = ComfyWorkflowBuilder.txt2img(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            model=model,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed
        )

        validator = ComfyConnectionValidator()
        issues = validator.validate(workflow)
        if issues:
            logger.warning(f"Workflow has {len(issues)} connection issues, auto-fixing...")
            workflow, fixes = validator.auto_fix(workflow)
            for fix in fixes:
                logger.info(f"Auto-fix: {fix}")

        execution = await self.queue_prompt(workflow)
        if not execution:
            return ComfyExecution(
                prompt_id="",
                status="error",
                error="Failed to queue prompt"
            )

        if wait:
            return await self.wait_for_completion(execution.prompt_id, timeout=timeout)
        return execution

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_comfy_client: Optional[ComfyUIClient] = None


def get_comfy_client() -> ComfyUIClient:
    global _comfy_client
    if _comfy_client is None:
        _comfy_client = ComfyUIClient()
    return _comfy_client


def get_connection_validator() -> ComfyConnectionValidator:
    return ComfyConnectionValidator()


def get_workflow_optimizer() -> ComfyWorkflowOptimizer:
    return ComfyWorkflowOptimizer()
