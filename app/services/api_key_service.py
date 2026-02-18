"""
API Key 业务服务

提供 API Key 的生成、吊销、启用/禁用、额度管理、使用日志查询
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, hash_api_key
from app.models.api_key import ApiKey
from app.models.usage_log import UsageLog
from app.utils.helpers import truncate_key

logger = logging.getLogger(__name__)


async def create_api_key(
    db: AsyncSession,
    name: str,
    group_id: Optional[int] = None,
    token_quota: int = 0,
) -> tuple:
    """生成新的 API Key

    Returns:
        (raw_key, api_key_obj)
    """
    raw_key = generate_api_key()
    hashed = hash_api_key(raw_key)
    prefix = truncate_key(raw_key, 12)

    api_key = ApiKey(
        name=name,
        hashed_key=hashed,
        key_prefix=prefix,
        group_id=group_id,
        token_quota=token_quota,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return (raw_key, api_key)


async def revoke_api_key(db: AsyncSession, key_id: int) -> bool:
    """吊销（删除）API Key"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalars().first()
    if not api_key:
        return False
    await db.delete(api_key)
    return True


async def set_enabled(db: AsyncSession, key_id: int, enabled: bool) -> bool:
    """启用/禁用 API Key"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalars().first()
    if not api_key:
        return False
    api_key.is_enabled = enabled
    return True


async def set_quota(db: AsyncSession, key_id: int, token_quota: int) -> bool:
    """设置 Token 额度"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalars().first()
    if not api_key:
        return False
    api_key.token_quota = token_quota
    return True


async def reset_usage(db: AsyncSession, key_id: int) -> bool:
    """重置已用 Token 数"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalars().first()
    if not api_key:
        return False
    api_key.tokens_used = 0
    return True


async def list_api_keys(db: AsyncSession) -> List[ApiKey]:
    """列出所有 API Key"""
    result = await db.execute(select(ApiKey).order_by(ApiKey.id))
    return list(result.scalars().all())


async def get_usage_logs(
    db: AsyncSession,
    api_key_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple:
    """获取消费日志

    Returns:
        (total_count, logs_list)
    """
    query = select(UsageLog)
    count_query = select(func.count()).select_from(UsageLog)

    if api_key_id is not None:
        query = query.where(UsageLog.api_key_id == api_key_id)
        count_query = count_query.where(UsageLog.api_key_id == api_key_id)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(UsageLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    logs = list(result.scalars().all())

    return (total, logs)
