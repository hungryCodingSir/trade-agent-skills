"""Redis 连接管理"""
import redis.asyncio as async_redis
from loguru import logger
from typing import Optional
from app.config.settings import settings


class RedisManager:
    _pool: Optional[async_redis.ConnectionPool] = None
    _client: Optional[async_redis.Redis] = None

    @classmethod
    async def get_client(cls) -> async_redis.Redis:
        if cls._client is None:
            cls._pool = async_redis.ConnectionPool.from_url(
                settings.redis_url, max_connections=20, decode_responses=True,
            )
            cls._client = async_redis.Redis(connection_pool=cls._pool)
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None
        if cls._pool:
            await cls._pool.disconnect()
            cls._pool = None


async def check_redis_connection() -> bool:
    try:
        client = await RedisManager.get_client()
        await client.ping()
        logger.info("Redis connection OK")
        return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return False
