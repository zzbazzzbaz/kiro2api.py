"""
API Key 相关 Schema

用于 Admin API 的 API Key 管理请求与响应
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ===== 请求 =====

class CreateApiKeyRequest(BaseModel):
    """创建 API Key 请求"""
    name: str = Field(description="Key 名称（用于标识）")
    group_id: Optional[int] = Field(default=None, description="绑定的分组 ID")
    token_quota: int = Field(default=0, description="Token 额度上限（0 表示无限制）")


# ===== 响应 =====

class ApiKeyResponse(BaseModel):
    """API Key 信息响应"""
    id: int
    name: str
    key_prefix: str = Field(description="Key 前缀（如 sk-abc1...）")
    group_id: Optional[int] = None
    is_enabled: bool = True
    token_quota: int = 0
    tokens_used: int = 0
    request_count: int = 0
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ApiKeyCreatedResponse(BaseModel):
    """API Key 创建成功响应

    注意：raw_key 仅在创建时返回一次，之后不可再获取
    """
    id: int
    name: str
    raw_key: str = Field(description="原始 API Key（仅此次返回）")
    key_prefix: str
    group_id: Optional[int] = None
    token_quota: int = 0
    created_at: Optional[datetime] = None


class UsageLogResponse(BaseModel):
    """消费日志条目"""
    id: int
    api_key_id: Optional[int] = None
    credential_id: Optional[int] = None
    model: str
    endpoint: str
    client_ip: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    status_code: int = 200
    error_message: Optional[str] = None
    duration_ms: int = 0
    created_at: Optional[datetime] = None


class UsageLogListResponse(BaseModel):
    """消费日志列表响应"""
    total: int = 0
    items: List[UsageLogResponse] = Field(default_factory=list)
