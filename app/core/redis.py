"""
Redis client for token blacklist
Uses Upstash Redis REST API for multi-instance token blacklist support
Reference: https://upstash.com/docs/redis/overall/getstarted
"""
import httpx
import logging
from typing import Optional
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_redis_client() -> Optional['RedisClient']:
    """
    Get a singleton RedisClient instance.
    
    Returns None if Redis is not configured (falls back to in-memory blacklist).
    
    Reference: https://docs.python.org/3/library/functools.html#functools.lru_cache
    """
    if not settings.UPSTASH_REDIS_REST_URL or not settings.UPSTASH_REDIS_REST_TOKEN:
        logger.warning("Redis not configured - token blacklist will use in-memory storage (not suitable for multi-instance)")
        return None
    return RedisClient()


class RedisClient:
    """
    Redis client using Upstash REST API.
    
    Uses HTTP requests to interact with Upstash Redis, making it suitable
    for serverless environments where persistent connections aren't available.
    
    Reference: https://upstash.com/docs/redis/overall/getstarted
    """
    
    def __init__(self):
        if not settings.UPSTASH_REDIS_REST_URL or not settings.UPSTASH_REDIS_REST_TOKEN:
            raise ValueError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be set")
        
        self.url = settings.UPSTASH_REDIS_REST_URL.rstrip('/')
        self.token = settings.UPSTASH_REDIS_REST_TOKEN
        self.base_url = f"{self.url}"
    
    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """
        Set a key with expiration time.
        
        Upstash REST API format: POST /setex/{key}/{seconds} with value in body
        
        Args:
            key: Redis key
            seconds: Expiration time in seconds
            value: Value to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Upstash REST API: POST /setex/{key}/{seconds} with value in request body
                response = await client.post(
                    f"{self.base_url}/setex/{key}/{seconds}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                    content=value,  # Send value as plain text in body
                )
                response.raise_for_status()
                result = response.json()
                # Upstash returns {"result": "OK"} on success
                return result.get("result") == "OK"
        except Exception as e:
            logger.error(f"Failed to set Redis key {key}: {type(e).__name__}: {e}", exc_info=True)
            return False
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get a value by key.
        
        Args:
            key: Redis key
            
        Returns:
            Value if found, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/get/{key}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                )
                response.raise_for_status()
                result = response.json()
                # Upstash REST API returns {"result": "value"} or {"result": null}
                return result.get("result") if result else None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to get Redis key {key}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Failed to get Redis key {key}: {type(e).__name__}: {e}", exc_info=True)
            return None
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Upstash REST API format: GET /exists/{key}
        
        Args:
            key: Redis key
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/exists/{key}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                )
                response.raise_for_status()
                result = response.json()
                # Upstash REST API returns {"result": 1} if exists, {"result": 0} if not
                return result.get("result", 0) == 1
        except Exception as e:
            logger.error(f"Failed to check Redis key {key}: {type(e).__name__}: {e}", exc_info=True)
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete a key.
        
        Upstash REST API format: POST /del/{key}
        
        Args:
            key: Redis key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Upstash REST API uses POST for del command
                response = await client.post(
                    f"{self.base_url}/del/{key}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                )
                response.raise_for_status()
                result = response.json()
                # Upstash returns {"result": 1} if deleted, {"result": 0} if not found
                return result.get("result", 0) >= 1
        except Exception as e:
            logger.error(f"Failed to delete Redis key {key}: {type(e).__name__}: {e}", exc_info=True)
            return False

