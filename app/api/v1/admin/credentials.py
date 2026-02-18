"""
Admin API — 凭据 CRUD 端点
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_admin_key
from app.core.database import get_db
from app.schemas.credential import AddCredentialRequest
from app.schemas.admin import SuccessResponse
from app.services import credential_service

# 余额缓存（credential_id → (timestamp, data)）
_balance_cache: dict = {}
BALANCE_CACHE_TTL = 300  # 5 分钟

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
            "machine_id": c.machine_id,
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


@router.get("/{credential_id}/balance")
async def get_credential_balance(
    credential_id: int,
    request: Request,
    force: bool = False,
):
    """获取凭据的 Kiro 账号使用额度

    调用上游 getUsageLimits API 查询配额和使用量。
    默认 5 分钟缓存，传入 force=true 跳过缓存。

    返回：已用积分、总积分、剩余积分、订阅类型、下次重置时间。
    """
    # 检查缓存
    now = time.time()
    if not force and credential_id in _balance_cache:
        cached_at, cached_data = _balance_cache[credential_id]
        if now - cached_at < BALANCE_CACHE_TTL:
            return {**cached_data, "cached": True}

    # 获取 KiroProvider
    provider = getattr(request.app.state, "kiro_provider", None)
    if not provider:
        raise HTTPException(status_code=503, detail="Kiro API provider 未配置")

    try:
        raw = await provider.get_usage_limits(credential_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 解析上游响应（与 kiro.rs admin service 一致）
    breakdown = (raw.get("usageBreakdownList") or [{}])[0] if raw.get("usageBreakdownList") else {}
    subscription_info = raw.get("subscriptionInfo") or {}

    # 计算总额度和已用量（累加基础 + freeTrial + bonuses）
    usage_limit = breakdown.get("usageLimitWithPrecision", 0)
    current_usage = breakdown.get("currentUsageWithPrecision", 0)

    free_trial = breakdown.get("freeTrialInfo") or {}
    if free_trial.get("freeTrialStatus") == "ACTIVE":
        usage_limit += free_trial.get("usageLimitWithPrecision", 0)
        current_usage += free_trial.get("currentUsageWithPrecision", 0)

    for bonus in (breakdown.get("bonuses") or []):
        if bonus.get("status") == "ACTIVE":
            usage_limit += bonus.get("usageLimit", 0)
            current_usage += bonus.get("currentUsage", 0)

    remaining = max(0, usage_limit - current_usage)
    usage_percentage = min(100, current_usage / usage_limit * 100) if usage_limit > 0 else 0

    result = {
        "credential_id": credential_id,
        "subscription_title": subscription_info.get("subscriptionTitle"),
        "current_usage": round(current_usage, 2),
        "usage_limit": round(usage_limit, 2),
        "remaining": round(remaining, 2),
        "usage_percentage": round(usage_percentage, 1),
        "next_reset_at": raw.get("nextDateReset"),
        "free_trial_info": free_trial if free_trial else None,
        "cached": False,
    }

    # 写入缓存
    _balance_cache[credential_id] = (now, result)

    return result
