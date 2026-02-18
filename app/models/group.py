"""
分组表模型

凭据池分组，支持隔离的凭据管理和分组级负载均衡
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Group(Base):
    """凭据池分组"""

    __tablename__ = "groups"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # === 基本信息 ===
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, comment="分组名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="分组描述")

    # === 负载均衡 ===
    load_balancing_mode: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, default=None,
        comment="分组级负载均衡模式（为空时使用全局配置）: priority / balanced"
    )

    # === 时间戳 ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
