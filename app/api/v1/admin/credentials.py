"""
Admin API — 凭据 CRUD 端点
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_admin_key
from app.core.database import get_db
from app.schemas.credential import AddCredentialRequest
from app.schemas.admin import SuccessResponse
from app.services import credential_service

router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("")
async def list_credentials(db: AsyncSession = Depends(get_db)):
    """获取所有凭据列表"""
    credentials = await credential_service.get_all_credentials(db)
    return [
        {
            "id": c.id,
            "auth_method": c.auth_method,
            "email": c.email,
            "subscription_title": c.subscription_title,
            "priority": c.priority,
            "is_disabled": c.is_disabled,
            "group_id": c.group_id,
            "region": c.region,
            "auth_region": c.auth_region,
            "api_region": c.api_region,
            "proxy_url": c.proxy_url,
            "fail_count": c.fail_count,
            "last_used_at": c.last_used_at,
            "expires_at": c.expires_at,
            "created_at": c.created_at,
        }
        for c in credentials
    ]


@router.post("")
async def add_credential(
    payload: AddCredentialRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加新凭据"""
    cred = await credential_service.add_credential(
        db,
        refresh_token=payload.refresh_token,
        auth_method=payload.auth_method,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        profile_arn=payload.profile_arn,
        group_id=payload.group_id,
        priority=payload.priority,
        region=payload.region,
        auth_region=payload.auth_region,
        api_region=payload.api_region,
        machine_id=payload.machine_id,
        proxy_url=payload.proxy_url,
        proxy_username=payload.proxy_username,
        proxy_password=payload.proxy_password,
    )
    return {"id": cred.id, "message": "凭据已添加"}


@router.delete("/{credential_id}")
async def delete_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除凭据（要求先禁用）"""
    try:
        success = await credential_service.delete_credential(db, credential_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="凭据不存在")
    return SuccessResponse.create("凭据已删除")


@router.post("/{credential_id}/disable")
async def disable_credential(credential_id: int, db: AsyncSession = Depends(get_db)):
    """禁用凭据"""
    if not await credential_service.set_disabled(db, credential_id, True):
        raise HTTPException(status_code=404, detail="凭据不存在")
    return SuccessResponse.create("凭据已禁用")


@router.post("/{credential_id}/enable")
async def enable_credential(credential_id: int, db: AsyncSession = Depends(get_db)):
    """启用凭据"""
    if not await credential_service.set_disabled(db, credential_id, False):
        raise HTTPException(status_code=404, detail="凭据不存在")
    return SuccessResponse.create("凭据已启用")


@router.post("/{credential_id}/reset")
async def reset_credential(credential_id: int, db: AsyncSession = Depends(get_db)):
    """重置凭据失败计数并重新启用"""
    if not await credential_service.reset_and_enable(db, credential_id):
        raise HTTPException(status_code=404, detail="凭据不存在")
    return SuccessResponse.create("凭据已重置并启用")


@router.put("/{credential_id}/priority")
async def set_priority(
    credential_id: int,
    priority: int,
    db: AsyncSession = Depends(get_db),
):
    """设置凭据优先级"""
    if not await credential_service.set_priority(db, credential_id, priority):
        raise HTTPException(status_code=404, detail="凭据不存在")
    return SuccessResponse.create(f"优先级已设置为 {priority}")
