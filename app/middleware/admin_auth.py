"""
Admin API Key 认证中间件
"""

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

ADMIN_PREFIX = "/api/admin"


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Admin API Key 认证中间件"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(ADMIN_PREFIX):
            return await call_next(request)

        settings = get_settings()
        if not settings.ADMIN_API_KEY:
            # 未配置 Admin Key，不鉴权
            return await call_next(request)

        # 提取 Key
        raw_key = request.headers.get("x-api-key")
        if not raw_key:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                raw_key = auth[7:]

        if not raw_key or raw_key != settings.ADMIN_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": "无效的 Admin API Key"},
            )

        return await call_next(request)
