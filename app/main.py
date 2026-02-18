"""
FastAPI 应用入口

包含应用创建、lifespan 生命周期管理、路由注册、中间件注册
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.database import engine, get_db, AsyncSessionLocal
from app.core.logging import setup_logging
from app.models.base import Base
from app.utils.http_client import close_all_clients

# 初始化 loguru 结构化日志
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动时：
    1. 创建数据库表
    2. 从数据库加载凭据
    3. 创建 MultiTokenManager
    4. 创建 KiroProvider
    5. 启动后台 Token 刷新任务

    关闭时：
    1. 取消后台任务
    2. 关闭 httpx 客户端
    3. 释放数据库连接
    """
    settings = get_settings()

    # === 启动 ===
    # 1. 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 从数据库加载凭据
    from app.models.credential import Credential
    from app.services.token_manager import MultiTokenManager
    from app.services.kiro_provider import KiroProvider
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Credential).where(Credential.is_disabled == False).order_by(Credential.priority)
        )
        credentials = list(result.scalars().all())

    logger.info("已加载 {} 个凭据", len(credentials))

    # 3. 创建 MultiTokenManager
    token_manager = MultiTokenManager(
        settings=settings,
        credentials=credentials,
        load_balancing_mode=settings.LOAD_BALANCING_MODE,
    )

    # 设置数据库持久化回调
    async def persist_credential(credential: Credential):
        async with AsyncSessionLocal() as db:
            await db.merge(credential)
            await db.commit()

    token_manager.set_persist_callback(persist_credential)

    # 4. 创建 KiroProvider
    kiro_provider = KiroProvider(token_manager)

    # 5. 注入到 app.state
    app.state.token_manager = token_manager
    app.state.kiro_provider = kiro_provider

    # 6. 启动后台 Token 刷新任务
    bg_task: Optional[asyncio.Task] = None
    if credentials:
        bg_task = asyncio.create_task(token_manager.background_refresh_loop(300))

    logger.info("kiro2api 启动完成 (host={}, port={})", settings.HOST, settings.PORT)

    yield

    # === 关闭 ===
    # 1. 取消后台任务
    if bg_task:
        bg_task.cancel()
        try:
            await bg_task
        except asyncio.CancelledError:
            pass

    # 2. 关闭 httpx 客户端
    await close_all_clients()

    # 3. 释放数据库连接
    await engine.dispose()
    logger.info("kiro2api 已关闭")


app = FastAPI(
    title="kiro2api",
    description="Kiro API 代理服务 — 支持 Anthropic/OpenAI 兼容接口",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 中间件（允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
from app.api.v1.anthropic.router import router as anthropic_router
from app.api.v1.openai.router import router as openai_router
from app.api.v1.admin.router import router as admin_router

app.include_router(anthropic_router)
app.include_router(openai_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}
