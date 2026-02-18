"""
分组业务服务

提供分组的 CRUD 操作
"""

import logging
from typing import List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.credential import Credential
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)


async def create_group(
    db: AsyncSession,
    name: str,
    description: Optional[str] = None,
    load_balancing_mode: Optional[str] = None,
) -> Group:
    """创建分组"""
    group = Group(name=name, description=description, load_balancing_mode=load_balancing_mode)
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


async def update_group(
    db: AsyncSession,
    group_id: int,
    **kwargs,
) -> Optional[Group]:
    """更新分组"""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalars().first()
    if not group:
        return None
    for key, value in kwargs.items():
        if value is not None and hasattr(group, key):
            setattr(group, key, value)
    return group


async def delete_group(db: AsyncSession, group_id: int) -> bool:
    """删除分组（检查关联）

    Raises:
        ValueError: 分组下仍有关联的凭据或 API Key
    """
    # 检查关联的凭据
    cred_count = await db.execute(
        select(func.count()).select_from(Credential).where(Credential.group_id == group_id)
    )
    if (cred_count.scalar() or 0) > 0:
        raise ValueError("分组下仍有凭据，请先移除或重新分配")

    # 检查关联的 API Key
    key_count = await db.execute(
        select(func.count()).select_from(ApiKey).where(ApiKey.group_id == group_id)
    )
    if (key_count.scalar() or 0) > 0:
        raise ValueError("分组下仍有 API Key，请先移除或重新分配")

    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalars().first()
    if not group:
        return False

    await db.delete(group)
    return True


async def list_groups(db: AsyncSession) -> List[dict]:
    """列出所有分组（含统计信息）"""
    result = await db.execute(select(Group).order_by(Group.id))
    groups = result.scalars().all()

    group_list = []
    for g in groups:
        # 统计关联数量
        cred_count = await db.execute(
            select(func.count()).select_from(Credential).where(Credential.group_id == g.id)
        )
        key_count = await db.execute(
            select(func.count()).select_from(ApiKey).where(ApiKey.group_id == g.id)
        )

        group_list.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "load_balancing_mode": g.load_balancing_mode,
            "credential_count": cred_count.scalar() or 0,
            "api_key_count": key_count.scalar() or 0,
            "created_at": g.created_at,
            "updated_at": g.updated_at,
        })

    return group_list
