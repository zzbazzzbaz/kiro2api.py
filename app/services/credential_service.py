"""
凭据业务服务

提供凭据的 CRUD 操作、状态查询、余额查询、账号状态检测
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import Credential

logger = logging.getLogger(__name__)

# 余额缓存（credential_id → (timestamp, data)）
_balance_cache: Dict[int, Tuple[float, dict]] = {}
BALANCE_CACHE_TTL = 300  # 5 分钟


async def get_all_credentials(db: AsyncSession) -> List[Credential]:
    """获取所有凭据"""
    result = await db.execute(select(Credential).order_by(Credential.priority, Credential.id))
    return list(result.scalars().all())


async def add_credential(db: AsyncSession, **kwargs) -> Credential:
    """添加凭据"""
    cred = Credential(**kwargs)
    db.add(cred)
    await db.flush()
    await db.refresh(cred)
    return cred


async def get_credential(db: AsyncSession, credential_id: int) -> Optional[Credential]:
    """获取单个凭据"""
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    return result.scalars().first()


async def delete_credential(db: AsyncSession, credential_id: int) -> bool:
    """删除凭据（要求先禁用）

    Returns:
        是否成功删除

    Raises:
        ValueError: 凭据未禁用
    """
    cred = await get_credential(db, credential_id)
    if not cred:
        return False
    if not cred.is_disabled:
        raise ValueError(f"只能删除已禁用的凭据（请先禁用凭据 #{credential_id}）")

    await db.execute(delete(Credential).where(Credential.id == credential_id))
    return True


async def set_disabled(db: AsyncSession, credential_id: int, disabled: bool) -> bool:
    """设置凭据禁用状态"""
    cred = await get_credential(db, credential_id)
    if not cred:
        return False
    cred.is_disabled = disabled
    if not disabled:
        cred.fail_count = 0
    return True


async def set_priority(db: AsyncSession, credential_id: int, priority: int) -> bool:
    """设置凭据优先级"""
    cred = await get_credential(db, credential_id)
    if not cred:
        return False
    cred.priority = priority
    return True


async def reset_and_enable(db: AsyncSession, credential_id: int) -> bool:
    """重置凭据失败计数并重新启用"""
    cred = await get_credential(db, credential_id)
    if not cred:
        return False
    cred.fail_count = 0
    cred.is_disabled = False
    return True
