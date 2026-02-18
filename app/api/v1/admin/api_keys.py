"""
Admin API — API Key 端点
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_admin_key
from app.core.database import get_db
from app.schemas.api_key import CreateApiKeyRequest
from app.schemas.admin import SuccessResponse
from app.services import api_key_service

router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("")
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    """列出所有 API Key"""
    keys = await api_key_service.list_api_keys(db)
    return [
        {
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix,
            "group_id": k.group_id,
            "is_enabled": k.is_enabled,
            "token_quota": k.token_quota,
            "tokens_used": k.tokens_used,
            "request_count": k.request_count,
            "last_used_at": k.last_used_at,
            "created_at": k.created_at,
        }
        for k in keys
    ]


@router.post("")
async def create_api_key(
    payload: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建新的 API Key"""
    raw_key, api_key = await api_key_service.create_api_key(
        db, name=payload.name, group_id=payload.group_id, token_quota=payload.token_quota,
    )
    return {
        "id": api_key.id,
        "name": api_key.name,
        "raw_key": raw_key,
        "key_prefix": api_key.key_prefix,
        "group_id": api_key.group_id,
        "token_quota": api_key.token_quota,
        "created_at": api_key.created_at,
    }


@router.delete("/{key_id}")
async def revoke_api_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """吊销 API Key"""
    if not await api_key_service.revoke_api_key(db, key_id):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return SuccessResponse.create("API Key 已吊销")


@router.post("/{key_id}/enable")
async def enable_api_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """启用 API Key"""
    if not await api_key_service.set_enabled(db, key_id, True):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return SuccessResponse.create("API Key 已启用")


@router.post("/{key_id}/disable")
async def disable_api_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """禁用 API Key"""
    if not await api_key_service.set_enabled(db, key_id, False):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return SuccessResponse.create("API Key 已禁用")


@router.put("/{key_id}/quota")
async def set_quota(key_id: int, token_quota: int, db: AsyncSession = Depends(get_db)):
    """设置 Token 额度"""
    if not await api_key_service.set_quota(db, key_id, token_quota):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return SuccessResponse.create(f"Token 额度已设置为 {token_quota}")


@router.post("/{key_id}/reset-usage")
async def reset_usage(key_id: int, db: AsyncSession = Depends(get_db)):
    """重置已用 Token 数"""
    if not await api_key_service.reset_usage(db, key_id):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return SuccessResponse.create("已用 Token 数已重置")


@router.get("/usage-logs")
async def get_usage_logs(
    api_key_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取消费日志"""
    total, logs = await api_key_service.get_usage_logs(db, api_key_id, limit, offset)
    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "api_key_id": log.api_key_id,
                "credential_id": log.credential_id,
                "model": log.model,
                "endpoint": log.endpoint,
                "client_ip": log.client_ip,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "status_code": log.status_code,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }
