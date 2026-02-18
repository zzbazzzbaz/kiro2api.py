"""
设备指纹生成模块

基于 SHA-256 生成稳定的设备指纹，与 kiro.rs 行为完全一致。
使用 "KotlinNativeAPI/" 前缀 + refresh_token 作为哈希输入。
"""

import hashlib
from typing import Optional


def _sha256_hex(input_str: str) -> str:
    """SHA-256 哈希（返回 64 字符十六进制字符串）"""
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()


def _normalize_machine_id(machine_id: str) -> Optional[str]:
    """标准化 machineId 格式

    支持以下格式：
    - 64 字符十六进制字符串（直接返回）
    - UUID 格式（如 "2582956e-cc88-4669-b546-07adbffcb894"，移除连字符后重复补齐到 64 字符）

    Args:
        machine_id: 原始 machineId

    Returns:
        标准化后的 64 字符十六进制字符串，或 None（无法识别的格式）
    """
    trimmed = machine_id.strip()

    if not trimmed:
        return None

    # 如果已经是 64 字符十六进制，直接返回
    if len(trimmed) == 64 and all(c in "0123456789abcdefABCDEF" for c in trimmed):
        return trimmed

    # 尝试解析 UUID 格式（移除连字符）
    without_dashes = trimmed.replace("-", "")

    # UUID 去掉连字符后是 32 字符
    if len(without_dashes) == 32 and all(c in "0123456789abcdefABCDEF" for c in without_dashes):
        # 补齐到 64 字符（重复一次）
        return without_dashes + without_dashes

    # 无法识别的格式
    return None


def generate_from_refresh_token(refresh_token: str) -> str:
    """从 refresh_token 派生 machine_id

    与 kiro.rs 完全一致：SHA256("KotlinNativeAPI/" + refresh_token)

    Args:
        refresh_token: 刷新令牌

    Returns:
        64 字符的十六进制 SHA-256 哈希值
    """
    return _sha256_hex(f"KotlinNativeAPI/{refresh_token}")


def get_effective_machine_id(
    credential_machine_id: Optional[str],
    refresh_token: Optional[str],
) -> str:
    """获取有效的 Machine ID

    优先级：
    1. 凭据级 machine_id（手动配置，标准化后使用）
    2. 由 refresh_token 派生：SHA256("KotlinNativeAPI/" + refresh_token)

    Args:
        credential_machine_id: 凭据级配置
        refresh_token: 刷新令牌（用于派生）

    Returns:
        Machine ID 字符串（64 字符十六进制）
    """
    # 1. 凭据级 machine_id
    if credential_machine_id:
        normalized = _normalize_machine_id(credential_machine_id)
        if normalized:
            return normalized

    # 2. 由 refresh_token 派生
    return generate_from_refresh_token(refresh_token)
