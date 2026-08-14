"""
AI-OS Browser API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import base64
import logging

from ai_os.browser.engine import LightBrowser, BrowserPool, get_browser_pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["browser"])  # prefix supplied by main.py (/api/v1/browser)


class NavigateRequest(BaseModel):
    """Request to navigate to URL"""
    url: str
    headless: bool = True
    wait_until: str = "domcontentloaded"


class ScreenshotRequest(BaseModel):
    """Request to take screenshot"""
    full_page: bool = False


class ExecuteJSRequest(BaseModel):
    """Request to execute JavaScript"""
    js_code: str


@router.post("/navigate")
async def navigate(request: NavigateRequest):
    """Navigate to a URL"""
    try:
        browser = LightBrowser()
        await browser.start()
        
        result = await browser.navigate(request.url, request.wait_until)
        
        await browser.close()
        
        if result.error:
            raise HTTPException(status_code=400, detail=result.error)
        
        return {
            "url": result.url,
            "title": result.title,
            "content_length": len(result.content) if result.content else 0
        }
        
    except Exception as e:
        logger.error(f"Browser error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/screenshot")
async def take_screenshot(request: NavigateRequest, full_page: bool = False):
    """Navigate and take screenshot"""
    try:
        browser = LightBrowser()
        await browser.start()
        
        await browser.navigate(request.url)
        screenshot = await browser.screenshot(full_page)
        
        await browser.close()
        
        return {
            "screenshot": base64.b64encode(screenshot).decode()
        }
        
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_javascript(request: ExecuteJSRequest):
    """Execute JavaScript in browser"""
    try:
        browser = LightBrowser()
        await browser.start()
        
        # Navigate to blank page first
        await browser.navigate("about:blank")
        
        result = await browser.execute_js(request.js_code)
        
        await browser.close()
        
        return {"result": result}
        
    except Exception as e:
        logger.error(f"JS execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pool/status")
async def get_pool_status():
    """Get browser pool status"""
    try:
        pool = await get_browser_pool()
        return pool.get_stats()
    except:
        return {"status": "not_initialized"}


@router.get("/health")
async def browser_health():
    """Browser service health check"""
    return {"status": "healthy"}