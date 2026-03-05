"""Desktop Open Agent — FastAPI 入口"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info(f"Starting {settings.app_name} v{settings.app_version} ...")

    # ── 初始化桌面 Agent ──
    from app.agents.desktop_orchestrator import init_agent
    init_agent()

    logger.info(f"Ready — Swagger: http://{settings.host}:{settings.port}/docs")

    yield

    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description=(
        "🖥️ 桌面应用启动助手\n\n"
        "通过自然语言打开 Windows 上的应用程序。\n\n"
        '示例: `{"message": "帮我打开微信"}`'
    ),
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

from app.routers.desktop_router import router as desktop_router

app.include_router(desktop_router, prefix="/api/v1/desktop", tags=["Desktop"])


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": settings.app_version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
