import sys
sys.path.insert(0, '/app/src')

# Test the services endpoint directly
import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Test metrics
        try:
            r = await client.get("http://localhost:8080/api/v1/dashboard/metrics")
            print("Metrics status:", r.status_code)
            print("Metrics:", r.text[:200])
        except Exception as e:
            print("Metrics error:", e)

        # Test services
        try:
            r = await client.get("http://localhost:8080/api/v1/dashboard/services")
            print("Services status:", r.status_code)
            print("Services:", r.text[:300])
        except Exception as e:
            print("Services error:", e)

        # Test fs list
        try:
            r = await client.get("http://localhost:8080/api/v1/desktop/fs/list?path=/app/src")
            print("FS status:", r.status_code)
            print("FS:", r.text[:300])
        except Exception as e:
            print("FS error:", e)

asyncio.run(test())