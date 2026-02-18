"""
Admin API — 分组 CRUD 端点
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_admin_key
from app.core.database import get_db
from app.schemas.group import CreateGroupRequest, UpdateGroupRequest
from app.schemas.admin import SuccessResponse
from app.services import group_service

router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("")
async def list_groups(db: AsyncSession = Depends(get_db)):
    """列出所有分组"""
    return await group_service.list_groups(db)


@router.post("")
async def create_group(
    payload: CreateGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建分组"""
    group = await group_service.create_group(
        db, name=payload.name, description=payload.description,
        load_balancing_mode=payload.load_balancing_mode,
    )
    return {"id": group.id, "name": group.name, "message": "分组已创建"}


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    payload: UpdateGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新分组"""
    update_data = payload.model_dump(exclude_unset=True)
    group = await group_service.update_group(db, group_id, **update_data)
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    return SuccessResponse.create("分组已更新")


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """删除分组"""
    try:
        success = await group_service.delete_group(db, group_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="分组不存在")
    return SuccessResponse.create("分组已删除")
