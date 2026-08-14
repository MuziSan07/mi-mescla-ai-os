"""AI-OS Browser Engine — real httpx-based implementation"""

import asyncio
import logging
import os
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class LightBrowser:
    """
    Lightweight browser for web scraping and HTTP automation.
    Uses httpx for real HTTP requests with cookie/session support.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._client: Optional[httpx.AsyncClient] = None
        self._current_url: str = ""
        self._last_response: Optional[httpx.Response] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }
            )
        return self._client

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL and return page info"""
        try:
            client = self._get_client()
            response = await client.get(url)
            self._current_url = str(response.url)
            self._last_response = response

            content_type = response.headers.get("content-type", "")
            is_html = "text/html" in content_type

            return {
                "url": self._current_url,
                "status": response.status_code,
                "content_type": content_type,
                "is_html": is_html,
                "body_length": len(response.content),
                "body_preview": response.text[:3000] if is_html else f"[binary {len(response.content)} bytes]",
                "headers": dict(response.headers),
            }
        except httpx.ConnectError as e:
            logger.error(f"Navigation failed: {e}")
            return {"url": url, "status": 0, "error": f"Connection failed: {e}"}
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return {"url": url, "status": 0, "error": str(e)}

    async def get_text(self) -> str:
        """Get text content of current page"""
        if self._last_response is None:
            return ""
        try:
            text = self._last_response.text
            # Simple tag stripping
            import re
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except Exception:
            return ""

    async def screenshot(self) -> bytes:
        """
        Screenshot requires a real browser (Playwright/Puppeteer).
        Returns empty bytes and logs a warning.
        To enable real screenshots: install playwright and set USE_PLAYWRIGHT=true
        """
        use_playwright = os.getenv("USE_PLAYWRIGHT", "false").lower() == "true"
        if not use_playwright:
            logger.warning(
                "Screenshot requires Playwright. Set USE_PLAYWRIGHT=true and "
                "install: pip install playwright && playwright install chromium"
            )
            return b""

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(self._current_url or "about:blank")
                screenshot = await page.screenshot()
                await browser.close()
                return screenshot
        except ImportError:
            logger.warning("Playwright not installed")
            return b""
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return b""

    async def execute_js(self, js: str) -> Dict[str, Any]:
        """
        JS execution requires a real browser (Playwright).
        Returns not_available if Playwright not configured.
        """
        use_playwright = os.getenv("USE_PLAYWRIGHT", "false").lower() == "true"
        if not use_playwright:
            return {
                "result": None,
                "status": "unavailable",
                "note": "JS execution requires Playwright. Set USE_PLAYWRIGHT=true."
            }

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                if self._current_url:
                    await page.goto(self._current_url)
                result = await page.evaluate(js)
                await browser.close()
                return {"result": result, "status": "ok"}
        except ImportError:
            return {"result": None, "status": "playwright_not_installed"}
        except Exception as e:
            return {"result": None, "status": "error", "error": str(e)}

    async def post(self, url: str, data: Dict = None, json: Dict = None) -> Dict[str, Any]:
        """POST request"""
        try:
            client = self._get_client()
            response = await client.post(url, data=data, json=json)
            return {
                "url": str(response.url),
                "status": response.status_code,
                "body": response.text[:3000],
            }
        except Exception as e:
            return {"url": url, "status": 0, "error": str(e)}

    async def get_links(self) -> List[str]:
        """Extract all links from current page"""
        if self._last_response is None:
            return []
        import re
        text = self._last_response.text
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', text)
        return [h for h in hrefs if h.startswith("http")]

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class BrowserPool:
    """Pool of browser instances"""

    def __init__(self, size: int = 5):
        self.size = size
        self._pool: asyncio.Queue = asyncio.Queue()
        self._initialized = False

    async def _ensure_initialized(self):
        if not self._initialized:
            for _ in range(self.size):
                await self._pool.put(LightBrowser())
            self._initialized = True

    async def acquire(self) -> LightBrowser:
        """Acquire browser from pool"""
        await self._ensure_initialized()
        try:
            return self._pool.get_nowait()
        except asyncio.QueueEmpty:
            # Pool exhausted — return a new one
            logger.warning("Browser pool exhausted, creating temporary instance")
            return LightBrowser()

    async def release(self, browser: LightBrowser):
        """Release browser back to pool"""
        if self._pool.qsize() < self.size:
            await self._pool.put(browser)
        else:
            await browser.close()


_browser_pool: Optional[BrowserPool] = None


def get_browser_pool() -> BrowserPool:
    """Get singleton browser pool"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool()
    return _browser_pool
