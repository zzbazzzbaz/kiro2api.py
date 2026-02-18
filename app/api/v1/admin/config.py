"""
Admin API — 配置端点
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import verify_admin_key
from app.schemas.admin import LoadBalancingModeResponse, SuccessResponse

router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("/load-balancing-mode")
async def get_load_balancing_mode(request: Request):
    """获取当前负载均衡模式"""
    token_manager = getattr(request.app.state, "token_manager", None)
    if token_manager:
        return LoadBalancingModeResponse(mode=token_manager.get_load_balancing_mode())
    return LoadBalancingModeResponse(mode="priority")


@router.put("/load-balancing-mode")
async def set_load_balancing_mode(request: Request, mode: str):
    """设置负载均衡模式"""
    if mode not in ("priority", "balanced"):
        raise HTTPException(status_code=400, detail=f"无效的负载均衡模式: {mode}")

    token_manager = getattr(request.app.state, "token_manager", None)
    if token_manager:
        try:
            token_manager.set_load_balancing_mode(mode)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return SuccessResponse.create(f"负载均衡模式已设置为 {mode}")
