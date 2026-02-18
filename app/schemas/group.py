"""
分组相关 Schema

用于 Admin API 的分组管理请求与响应
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ===== 请求 =====

class CreateGroupRequest(BaseModel):
    """创建分组请求"""
    name: str = Field(description="分组名称")
    description: Optional[str] = Field(default=None, description="分组描述")
    load_balancing_mode: Optional[str] = Field(
        default=None, description="负载均衡模式: priority / balanced（为空使用全局配置）"
    )


class UpdateGroupRequest(BaseModel):
    """更新分组请求"""
    name: Optional[str] = Field(default=None, description="分组名称")
    description: Optional[str] = Field(default=None, description="分组描述")
    load_balancing_mode: Optional[str] = Field(
        default=None, description="负载均衡模式: priority / balanced"
    )


# ===== 响应 =====

class GroupResponse(BaseModel):
    """分组信息响应"""
    id: int
    name: str
    description: Optional[str] = None
    load_balancing_mode: Optional[str] = None
    credential_count: int = Field(default=0, description="分组内凭据数量")
    api_key_count: int = Field(default=0, description="绑定的 API Key 数量")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
