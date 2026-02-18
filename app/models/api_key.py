"""
API Key 表模型

外部 API Key 管理，支持绑定分组、Token 额度控制
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApiKey(Base):
    """外部 API Key"""

    __tablename__ = "api_keys"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # === Key 信息 ===
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Key 名称（用于标识）")
    hashed_key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="SHA-256 哈希后的 Key"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="Key 前缀（用于显示，如 sk-abc1...）"
    )

    # === 分组绑定 ===
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=None, comment="绑定的分组 ID（为空表示使用默认分组）"
    )

    # === 状态 ===
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")

    # === Token 额度 ===
    token_quota: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="Token 额度上限（0 表示无限制）"
    )
    tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="已消耗 Token 数"
    )

    # === 使用统计 ===
    request_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="累计请求次数"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最近使用时间")

    # === 时间戳 ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
