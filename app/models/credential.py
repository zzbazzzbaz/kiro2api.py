"""
凭据表模型

存储 Kiro OAuth 凭据信息，支持 Social 和 IdC 两种认证方式
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Credential(Base):
    """Kiro OAuth 凭据"""

    __tablename__ = "credentials"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # === Token 相关 ===
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="访问令牌")
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False, comment="刷新令牌")
    profile_arn: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="Profile ARN")
    expires_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="过期时间 (RFC3339)")

    # === 认证方式 ===
    auth_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="social", comment="认证方式: social / idc"
    )
    client_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="OIDC Client ID (IdC)")
    client_secret: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="OIDC Client Secret (IdC)")

    # === 分组与优先级 ===
    group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None, comment="所属分组 ID")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级（数字越小越高）")
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已禁用")

    # === 区域配置（可选，覆盖全局） ===
    region: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="凭据级 Region")
    auth_region: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="凭据级 Auth Region")
    api_region: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="凭据级 API Region")

    # === 设备指纹 ===
    machine_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="凭据级 Machine ID")

    # === 账号信息 ===
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="用户邮箱")
    subscription_title: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="订阅等级 (KIRO PRO+ / KIRO FREE)"
    )

    # === 代理配置（可选，覆盖全局）===
    proxy_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="代理 URL（'direct' 表示不使用代理）")
    proxy_username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="代理用户名")
    proxy_password: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="代理密码")

    # === 运行时状态（非持久化到凭据文件，仅数据库） ===
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="连续失败次数")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最近使用时间")

    # === 时间戳 ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
