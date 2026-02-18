"""
外部 API Key 认证中间件

从 x-api-key 或 Authorization Bearer 提取 Key，
在数据库中查找 SHA-256 哈希，检查启用状态和 Token 额度
"""

import logging
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_api_key
from app.models.api_key import ApiKey

from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# 不需要 API Key 认证的路径
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
# Admin API 路径前缀（使用独立的 Admin Key 认证）
ADMIN_PREFIX = "/api/admin"


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """外部 API Key 认证中间件"""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # 不要求 API Key 时直接放行
        if not settings.REQUIRE_API_KEY:
            request.state.group_id = None
            request.state.api_key_id = None
            return await call_next(request)

        # 豁免路径
        path = request.url.path
        if path in EXEMPT_PATHS or path.startswith(ADMIN_PREFIX):
            return await call_next(request)

        # 提取 Key
        raw_key = request.headers.get("x-api-key")
        if not raw_key:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                raw_key = auth[7:]

        if not raw_key:
            return JSONResponse(
                status_code=401,
                content={"type": "error", "error": {"type": "authentication_error", "message": "缺少 API Key"}},
            )

        # 查找并验证
        hashed = hash_api_key(raw_key)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ApiKey).where(ApiKey.hashed_key == hashed))
            api_key = result.scalars().first()

            if not api_key:
                return JSONResponse(
                    status_code=401,
                    content={"type": "error", "error": {"type": "authentication_error", "message": "无效的 API Key"}},
                )

            if not api_key.is_enabled:
                return JSONResponse(
                    status_code=403,
                    content={"type": "error", "error": {"type": "permission_error", "message": "API Key 已禁用"}},
                )

            # 检查额度
            if api_key.token_quota > 0 and api_key.tokens_used >= api_key.token_quota:
                return JSONResponse(
                    status_code=429,
                    content={"type": "error", "error": {"type": "rate_limit_error", "message": "Token 额度已用尽"}},
                )

            # 注入状态
            request.state.group_id = api_key.group_id
            request.state.api_key_id = api_key.id

            # 异步更新 last_used_at 和 request_count
            await db.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key.id)
                .values(
                    last_used_at=datetime.now(timezone.utc),
                    request_count=ApiKey.request_count + 1,
                )
            )
            await db.commit()

        return await call_next(request)
