import sys
sys.path.insert(0, '/app')

import asyncio
import aiohttp
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()

class APIClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error("api_get_error", endpoint=endpoint, status=resp.status)
                        return None
        except asyncio.TimeoutError:
            logger.error("api_timeout", endpoint=endpoint)
            return None
        except Exception as e:
            logger.error("api_exception", endpoint=endpoint, error=str(e))
            return None
    
    async def post(self, endpoint: str, json: Optional[Dict] = None) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(f"{self.base_url}{endpoint}", json=json) as resp:
                    if resp.status in [200, 201]:
                        return await resp.json()
                    else:
                        logger.error("api_post_error", endpoint=endpoint, status=resp.status)
                        return None
        except asyncio.TimeoutError:
            logger.error("api_timeout", endpoint=endpoint)
            return None
        except Exception as e:
            logger.error("api_exception", endpoint=endpoint, error=str(e))
            return None
    
    async def put(self, endpoint: str, json: Optional[Dict] = None) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.put(f"{self.base_url}{endpoint}", json=json) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error("api_put_error", endpoint=endpoint, status=resp.status)
                        return None
        except asyncio.TimeoutError:
            logger.error("api_timeout", endpoint=endpoint)
            return None
        except Exception as e:
            logger.error("api_exception", endpoint=endpoint, error=str(e))
            return None
    
    async def delete(self, endpoint: str) -> bool:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.delete(f"{self.base_url}{endpoint}") as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error("api_exception", endpoint=endpoint, error=str(e))
            return False
