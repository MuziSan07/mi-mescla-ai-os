"""
AI Operating System - Computer Vision Pipeline

Provides OCR, object detection, segmentation, UI analysis, and screenshot understanding.
"""

import asyncio
import logging
import base64
import httpx
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from io import BytesIO

from ai_os.models.schemas import (
    VisionRequest, VisionResponse, BoundingBox, TextRegion, UIComponent
)

logger = logging.getLogger(__name__)


@dataclass
class VisionResult:
    """Result from vision processing"""
    text: Optional[str] = None
    detected_objects: List[BoundingBox] = None
    text_regions: List[TextRegion] = None
    ui_components: List[UIComponent] = None

    def __post_init__(self):
        if self.detected_objects is None:
            self.detected_objects = []
        if self.text_regions is None:
            self.text_regions = []
        if self.ui_components is None:
            self.ui_components = []


class VisionPipeline:
    """
    Comprehensive computer vision processing pipeline.
    Uses Ollama (llava) for vision-language tasks and
    httpx for image fetching.
    """

    def __init__(self, ollama_endpoint: str = "http://localhost:11434"):
        self._initialized = False
        self._ollama_endpoint = ollama_endpoint
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize the vision pipeline"""
        self._client = httpx.AsyncClient(timeout=60.0)
        self._initialized = True
        logger.info("Vision pipeline initialized")

    async def _fetch_image_as_base64(self, image_url: str) -> str:
        """Fetch an image from URL and return as base64 string"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=60.0)
        try:
            response = await self._client.get(image_url)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to fetch image {image_url}: {e}")
            return ""

    async def process_image(self, request: VisionRequest) -> VisionResult:
        """Process image according to request"""
        result = VisionResult()

        if request.ui_analysis:
            result.ui_components = await self.analyze_ui(request.image_url)

        if request.object_detection:
            result.detected_objects = await self.detect_objects(request.image_url)

        if request.OCR:
            result.text_regions = await self.perform_ocr(request.image_url)

        if request.prompt:
            result.text = await self.analyze_with_prompt(
                request.image_url,
                request.prompt
            )

        return result

    async def perform_ocr(self, image_url: str) -> List[TextRegion]:
        """
        Perform OCR using the vision-language model (llava via Ollama).
        Falls back to empty list if Ollama is not reachable.
        """
        logger.debug(f"Performing OCR on: {image_url}")
        try:
            image_b64 = await self._fetch_image_as_base64(image_url)
            if not image_b64:
                return []

            prompt = (
                "Extract ALL text visible in this image. "
                "Return each text block on a new line prefixed with 'TEXT:'. "
                "Do not add any explanation."
            )
            raw = await self._call_vision_model(image_b64, prompt)
            regions = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("TEXT:"):
                    text = line[5:].strip()
                    if text:
                        regions.append(
                            TextRegion(
                                text=text,
                                bounding_box=BoundingBox(
                                    x=0, y=0, width=0, height=0,
                                    label="ocr", confidence=0.9
                                ),
                                confidence=0.9
                            )
                        )
            return regions
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return []

    async def detect_objects(self, image_url: str) -> List[BoundingBox]:
        """
        Detect objects using the vision-language model.
        Returns a list of labeled bounding boxes (no pixel coords without a
        dedicated detection model, so coords default to 0).
        """
        logger.debug(f"Detecting objects in: {image_url}")
        try:
            image_b64 = await self._fetch_image_as_base64(image_url)
            if not image_b64:
                return []

            prompt = (
                "List every distinct object or element visible in this image. "
                "Return one object per line prefixed with 'OBJECT:'. "
                "Do not add any explanation."
            )
            raw = await self._call_vision_model(image_b64, prompt)
            boxes = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("OBJECT:"):
                    label = line[7:].strip()
                    if label:
                        boxes.append(
                            BoundingBox(
                                x=0, y=0, width=0, height=0,
                                label=label, confidence=0.8
                            )
                        )
            return boxes
        except Exception as e:
            logger.warning(f"Object detection failed: {e}")
            return []

    async def segment_region(
        self,
        image_url: str,
        points: List[tuple]
    ) -> str:
        """
        Segment a region. Without SAM available, describes the region
        using the vision model and returns the description as base64.
        """
        logger.debug(f"Segmenting region in: {image_url}")
        try:
            image_b64 = await self._fetch_image_as_base64(image_url)
            if not image_b64:
                return ""
            description = await self._call_vision_model(
                image_b64,
                f"Describe the region around points {points} in this image."
            )
            return base64.b64encode(description.encode()).decode()
        except Exception as e:
            logger.warning(f"Segmentation failed: {e}")
            return ""

    async def analyze_ui(self, image_url: str) -> List[UIComponent]:
        """
        Analyze UI components in a screenshot using the vision model.
        """
        logger.debug(f"Analyzing UI in: {image_url}")
        try:
            image_b64 = await self._fetch_image_as_base64(image_url)
            if not image_b64:
                return []

            prompt = (
                "Identify all UI components in this screenshot (buttons, inputs, "
                "menus, dropdowns, links, forms, images, modals, etc). "
                "Return one component per line as: COMPONENT:<type>|<description>. "
                "Do not add any explanation."
            )
            raw = await self._call_vision_model(image_b64, prompt)
            components = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("COMPONENT:"):
                    parts = line[10:].split("|", 1)
                    comp_type = parts[0].strip() if parts else "unknown"
                    props = {"description": parts[1].strip()} if len(parts) > 1 else {}
                    components.append(
                        UIComponent(
                            component_type=comp_type,
                            bounding_box=BoundingBox(
                                x=0, y=0, width=0, height=0,
                                label=comp_type, confidence=0.85
                            ),
                            properties=props
                        )
                    )
            return components
        except Exception as e:
            logger.warning(f"UI analysis failed: {e}")
            return []

    async def analyze_with_prompt(self, image_url: str, prompt: str) -> str:
        """
        Analyze image with a text prompt using llava via Ollama.
        """
        logger.debug(f"Analyzing image with prompt: {prompt}")
        try:
            image_b64 = await self._fetch_image_as_base64(image_url)
            if not image_b64:
                return "Could not fetch image."
            return await self._call_vision_model(image_b64, prompt)
        except Exception as e:
            logger.warning(f"Vision prompt failed: {e}")
            return f"Vision analysis unavailable: {e}"

    async def _call_vision_model(self, image_b64: str, prompt: str) -> str:
        """Call the Ollama llava model with an image and prompt"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=60.0)
        payload = {
            "model": "llava",
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        response = await self._client.post(
            f"{self._ollama_endpoint}/api/generate",
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    async def detect_web_elements(self, screenshot_url: str) -> Dict[str, Any]:
        """Detect web page elements from a screenshot"""
        logger.debug(f"Detecting web elements in: {screenshot_url}")
        try:
            components = await self.analyze_ui(screenshot_url)
            result: Dict[str, Any] = {
                "buttons": [],
                "inputs": [],
                "links": [],
                "images": [],
                "forms": []
            }
            for comp in components:
                ct = comp.component_type.lower()
                entry = {"type": ct, **comp.properties}
                if "button" in ct:
                    result["buttons"].append(entry)
                elif "input" in ct or "field" in ct or "form" in ct:
                    result["inputs"].append(entry)
                elif "link" in ct or "anchor" in ct:
                    result["links"].append(entry)
                elif "image" in ct or "img" in ct:
                    result["images"].append(entry)
                elif "form" in ct:
                    result["forms"].append(entry)
            return result
        except Exception as e:
            logger.warning(f"Web element detection failed: {e}")
            return {"buttons": [], "inputs": [], "links": [], "images": [], "forms": []}


class AILassoTool:
    """
    Visual selection tool - AI Lasso.
    Allows users to draw regions and apply AI instructions.
    """

    def __init__(self, vision_pipeline: VisionPipeline):
        self.vision = vision_pipeline

    async def process_selection(
        self,
        image_url: str,
        region: Dict[str, int],
        instruction: str
    ) -> str:
        """Process a visual selection with an instruction"""
        x = region.get("x", 0)
        y = region.get("y", 0)
        width = region.get("width", 100)
        height = region.get("height", 100)

        region_understanding = await self.understand_region(
            image_url,
            (x, y, width, height)
        )
        result = await self.apply_instruction(region_understanding, instruction)
        return result

    async def understand_region(self, image_url: str, region: tuple) -> str:
        """Understand what's in the selected region using the vision model"""
        prompt = (
            f"Focus on the rectangular region at x={region[0]}, y={region[1]}, "
            f"width={region[2]}, height={region[3]}. "
            "Describe what UI elements or content are present in that area."
        )
        return await self.vision.analyze_with_prompt(image_url, prompt)

    async def apply_instruction(
        self,
        region_understanding: str,
        instruction: str
    ) -> str:
        """Apply instruction to the understood region"""
        return (
            f"Instruction '{instruction}' applied to region containing: "
            f"{region_understanding}"
        )


# Singleton instance
_vision_pipeline_instance: Optional[VisionPipeline] = None


def get_vision_pipeline() -> VisionPipeline:
    """Get the vision pipeline singleton"""
    global _vision_pipeline_instance
    if _vision_pipeline_instance is None:
        _vision_pipeline_instance = VisionPipeline()
    return _vision_pipeline_instance
