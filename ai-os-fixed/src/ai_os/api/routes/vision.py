"""AI Operating System - Vision API Route"""

from fastapi import APIRouter, HTTPException
from ai_os.models.schemas import VisionRequest, VisionResponse
from ai_os.core.vision.processor import get_vision_pipeline
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData


router = APIRouter()


@router.post("/process", response_model=VisionResponse)
async def process_vision(request: VisionRequest,
    user: TokenData = Depends(require_auth)
):
    """Process an image with vision capabilities"""
    vision = get_vision_pipeline()
    
    try:
        result = await vision.process_image(request)
        
        return VisionResponse(
            text=result.text,
            detected_objects=result.detected_objects,
            text_regions=result.text_regions,
            ui_components=result.ui_components
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr")
async def perform_ocr(image_url: str,
    user: TokenData = Depends(require_auth)
):
    """Perform OCR on an image"""
    vision = get_vision_pipeline()
    regions = await vision.perform_ocr(image_url)
    return {"regions": [r.dict() for r in regions]}


@router.post("/detect")
async def detect_objects(image_url: str,
    user: TokenData = Depends(require_auth)
):
    """Detect objects in an image"""
    vision = get_vision_pipeline()
    objects = await vision.detect_objects(image_url)
    return {"objects": [o.dict() for o in objects]}


@router.post("/analyze-ui")
async def analyze_ui(image_url: str,
    user: TokenData = Depends(require_auth)
):
    """Analyze UI components"""
    vision = get_vision_pipeline()
    components = await vision.analyze_ui(image_url)
    return {"components": [c.dict() for c in components]}