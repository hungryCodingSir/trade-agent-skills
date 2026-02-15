"""Trade Agent Brain — FastAPI 入口"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.redis import AsyncRedisSaver
from loguru import logger

from app.config.database import check_mysql_connection, engine
from app.config.redis_config import check_redis_connection, RedisManager
from app.config.settings import settings

checkpointer: Optional[AsyncRedisSaver] = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("Starting Trade Agent Brain...")

    # ── 启动阶段：所有初始化在 yield 之前 ──
    if not await check_mysql_connection():
        logger.error("MySQL 连接失败!")

    if not await check_redis_connection():
        logger.error("Redis 连接失败!")

    global checkpointer, _saver_cm
    _saver_cm = AsyncRedisSaver.from_conn_string(settings.redis_url)
    checkpointer = await _saver_cm.__aenter__()
    logger.info("Redis Checkpointer started")

    try:
        from app.services.summary_milvus_service import check_milvus_connection
        if not await check_milvus_connection():
            logger.warning("Milvus 连接失败（可选服务）")
    except Exception as e:
        logger.warning(f"Milvus 初始化失败: {e}")

    try:
        from app.tools import call_mcp_tool
        logger.info(f"MCP Server: {settings.mcp_server_url}")
    except Exception as e:
        logger.warning(f"MCP 初始化失败: {e}")

    logger.info("Ready — Swagger: http://localhost:8000/docs")

    yield

    # 关闭阶段
    logger.info("Shutting down...")
    try:
        await _saver_cm.__aexit__(None, None, None)
        logger.info("Redis Checkpointer closed")
    except Exception as e:
        logger.warning(f"Checkpointer 关闭异常: {e}")
    try:
        engine.dispose()
    except Exception:
        pass
    await RedisManager.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Trade Agent Brain",
    description="跨境电商智能体系统",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import agent_router
app.include_router(agent_router.router, prefix="/api/v1/agent", tags=["Agent"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=settings.debug)