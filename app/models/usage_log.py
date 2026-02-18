"""
消费日志表模型

记录每次 API 请求的详细消费信息
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UsageLog(Base):
    """消费日志"""

    __tablename__ = "usage_logs"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # === 关联信息 ===
    api_key_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="关联的 API Key ID"
    )
    credential_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="使用的凭据 ID"
    )

    # === 请求信息 ===
    model: Mapped[str] = mapped_column(String(128), nullable=False, comment="请求的模型名称")
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False, comment="请求的端点路径")
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="客户端 IP")

    # === Token 消耗 ===
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="输入 Token 数")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="输出 Token 数")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总 Token 数")

    # === 请求状态 ===
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200, comment="HTTP 状态码")
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="错误信息（如有）")

    # === 耗时 ===
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="请求耗时（毫秒）")

    # === 时间戳 ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True, comment="创建时间"
    )
