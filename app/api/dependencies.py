"""
公共依赖项

提供 DB Session、当前 API Key 信息、KiroProvider 等依赖注入
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import hash_api_key
from app.models.api_key import ApiKey
from sqlalchemy import select


async def get_api_key_from_header(
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """从请求头提取 API Key

    支持两种方式：
    1. x-api-key header
    2. Authorization: Bearer <key>
    """
    if x_api_key:
        return x_api_key
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def verify_api_key(
    request: Request,
    raw_key: Optional[str] = Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Optional[ApiKey]:
    """验证外部 API Key（如果启用了 REQUIRE_API_KEY）

    验证通过后将 group_id 注入到 request.state
    """
    if not settings.REQUIRE_API_KEY:
        request.state.group_id = None
        request.state.api_key_id = None
        return None

    if not raw_key:
        raise HTTPException(status_code=401, detail="缺少 API Key")

    hashed = hash_api_key(raw_key)
    result = await db.execute(select(ApiKey).where(ApiKey.hashed_key == hashed))
    api_key = result.scalars().first()

    if not api_key:
        raise HTTPException(status_code=401, detail="无效的 API Key")

    if not api_key.is_enabled:
        raise HTTPException(status_code=403, detail="API Key 已禁用")

    # 检查 Token 额度
    if api_key.token_quota > 0 and api_key.tokens_used >= api_key.token_quota:
        raise HTTPException(status_code=429, detail="Token 额度已用尽")

    # 注入状态
    request.state.group_id = api_key.group_id
    request.state.api_key_id = api_key.id

    return api_key


async def verify_admin_key(
    raw_key: Optional[str] = Depends(get_api_key_from_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """验证 Admin API Key"""
    if not settings.ADMIN_API_KEY:
        return  # 未配置则不鉴权

    if not raw_key or raw_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="无效的 Admin API Key")
