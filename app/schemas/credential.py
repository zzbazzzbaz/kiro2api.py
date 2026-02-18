"""
凭据相关 Schema

用于 Admin API 的凭据管理请求与响应
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ===== 请求 =====

class AddCredentialRequest(BaseModel):
    """添加凭据请求"""
    refresh_token: str = Field(description="刷新令牌")
    auth_method: str = Field(default="social", description="认证方式: social / idc")
    client_id: Optional[str] = Field(default=None, description="OIDC Client ID (IdC 认证)")
    client_secret: Optional[str] = Field(default=None, description="OIDC Client Secret (IdC 认证)")
    profile_arn: Optional[str] = Field(default=None, description="Profile ARN")
    group_id: Optional[int] = Field(default=None, description="分组 ID")
    priority: int = Field(default=0, description="优先级（数字越小越高）")
    region: Optional[str] = Field(default=None, description="凭据级 Region")
    auth_region: Optional[str] = Field(default=None, description="凭据级 Auth Region")
    api_region: Optional[str] = Field(default=None, description="凭据级 API Region")
    machine_id: Optional[str] = Field(default=None, description="凭据级 Machine ID")
    proxy_url: Optional[str] = Field(default=None, description="代理 URL")
    proxy_username: Optional[str] = Field(default=None, description="代理用户名")
    proxy_password: Optional[str] = Field(default=None, description="代理密码")


# ===== 响应 =====

class CredentialStatusItem(BaseModel):
    """凭据状态条目"""
    id: int
    auth_method: str
    email: Optional[str] = None
    subscription_title: Optional[str] = None
    priority: int = 0
    is_disabled: bool = False
    group_id: Optional[int] = None
    region: Optional[str] = None
    auth_region: Optional[str] = None
    api_region: Optional[str] = None
    proxy_url: Optional[str] = None
    fail_count: int = 0
    last_used_at: Optional[datetime] = None
    token_valid: bool = Field(default=False, description="Token 是否有效")
    expires_at: Optional[str] = None
    created_at: Optional[datetime] = None


# ===== 账号状态（上游 getUsageLimits）=====

class BonusInfo(BaseModel):
    """奖励额度信息"""
    current_usage: float = 0
    usage_limit: float = 0
    status: Optional[str] = None
    is_active: bool = False


class FreeTrialInfo(BaseModel):
    """免费试用信息"""
    current_usage: int = 0
    current_usage_with_precision: float = 0
    free_trial_expiry: Optional[float] = None
    free_trial_status: Optional[str] = None
    usage_limit: int = 0
    usage_limit_with_precision: float = 0


class UsageBreakdownItem(BaseModel):
    """使用量明细"""
    current_usage: int = 0
    current_usage_with_precision: float = 0
    usage_limit: int = 0
    usage_limit_with_precision: float = 0
    bonuses: List[BonusInfo] = Field(default_factory=list)
    free_trial_info: Optional[FreeTrialInfo] = None
    next_date_reset: Optional[float] = None


class BalanceResponse(BaseModel):
    """账号余额响应（5 分钟缓存）"""
    credential_id: int
    email: Optional[str] = None
    subscription_title: Optional[str] = None
    usage_breakdown: List[UsageBreakdownItem] = Field(default_factory=list)
    next_date_reset: Optional[float] = None
    cached: bool = False


class AccountStatusResponse(BaseModel):
    """账号状态响应"""
    credential_id: int
    email: Optional[str] = None
    subscription_title: Optional[str] = None
    is_banned: bool = Field(default=False, description="是否被封禁")
    remaining_credits: float = Field(default=0, description="剩余积分")
    usage_breakdown: List[UsageBreakdownItem] = Field(default_factory=list)
    next_date_reset: Optional[float] = None
    error: Optional[str] = Field(default=None, description="查询错误（如有）")
