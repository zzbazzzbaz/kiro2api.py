"""
安全工具模块

提供 API Key 的哈希生成与常量时间比较
"""

import hashlib
import hmac
import secrets


def generate_api_key(prefix: str = "sk-") -> str:
    """生成密码学安全的随机 API Key

    Args:
        prefix: Key 前缀，默认 "sk-"

    Returns:
        带前缀的随机 API Key，如 "sk-abc123..."
    """
    random_part = secrets.token_hex(32)
    return f"{prefix}{random_part}"


def hash_api_key(raw_key: str) -> str:
    """对 API Key 进行 SHA-256 哈希

    用于数据库存储，避免明文保存

    Args:
        raw_key: 原始 API Key

    Returns:
        十六进制 SHA-256 哈希值
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """常量时间比较 API Key 哈希

    防止时序攻击

    Args:
        raw_key: 客户端提供的原始 Key
        hashed_key: 数据库中存储的哈希值

    Returns:
        是否匹配
    """
    computed = hash_api_key(raw_key)
    return hmac.compare_digest(computed, hashed_key)
