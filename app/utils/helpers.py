"""
通用工具函数
"""

import time
import uuid
from datetime import datetime, timezone


def now_rfc3339() -> str:
    """获取当前时间的 RFC3339 格式字符串

    Returns:
        如 "2025-02-18T12:00:00Z"
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_unix_ms() -> int:
    """获取当前时间的 Unix 毫秒时间戳"""
    return int(time.time() * 1000)


def now_unix() -> int:
    """获取当前时间的 Unix 秒级时间戳"""
    return int(time.time())


def generate_uuid() -> str:
    """生成随机 UUID（不带连字符）"""
    return uuid.uuid4().hex


def generate_message_id() -> str:
    """生成 Anthropic 格式的消息 ID

    Returns:
        如 "msg_01abc..."
    """
    return f"msg_{generate_uuid()[:24]}"


def generate_conversation_id() -> str:
    """生成对话 ID

    Returns:
        如 "conv-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    """
    return f"conv-{uuid.uuid4()}"


def truncate_key(key: str, visible_chars: int = 8) -> str:
    """截断 API Key 用于显示

    Args:
        key: 原始 Key
        visible_chars: 前缀保留的可见字符数

    Returns:
        如 "sk-abc123...***"
    """
    if len(key) <= visible_chars:
        return key
    return f"{key[:visible_chars]}..."


def parse_rfc3339(time_str: str) -> datetime:
    """解析 RFC3339 时间字符串

    Args:
        time_str: RFC3339 格式字符串

    Returns:
        datetime 对象（UTC 时区）
    """
    # 处理 "Z" 后缀
    if time_str.endswith("Z"):
        time_str = time_str[:-1] + "+00:00"
    return datetime.fromisoformat(time_str)


def is_token_expired(expires_at: str, buffer_minutes: int = 5) -> bool:
    """检查 Token 是否已过期或即将过期

    Args:
        expires_at: RFC3339 格式的过期时间
        buffer_minutes: 提前量（分钟），默认 5 分钟

    Returns:
        True 表示已过期或即将过期
    """
    try:
        expiry = parse_rfc3339(expires_at)
        now = datetime.now(timezone.utc)
        remaining = (expiry - now).total_seconds()
        return remaining < buffer_minutes * 60
    except (ValueError, TypeError):
        # 解析失败视为已过期
        return True
