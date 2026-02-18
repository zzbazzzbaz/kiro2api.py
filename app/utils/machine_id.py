"""
设备指纹生成模块

基于 SHA-256 生成稳定的设备指纹，与 kiro.rs 行为一致
"""

import hashlib
import uuid
from typing import Optional


def generate_machine_id(seed: Optional[str] = None) -> str:
    """生成设备指纹

    使用 SHA-256 对种子值进行哈希，生成稳定且不可逆的设备标识。
    与 kiro.rs 的 machine_id 生成逻辑一致。

    优先级：
    1. 凭据级 machine_id
    2. 全局 MACHINE_ID 配置
    3. 由 refresh_token 派生

    Args:
        seed: 用于生成指纹的种子值（通常为 refresh_token）。
              如果为 None，则使用随机 UUID。

    Returns:
        64 字符的十六进制 SHA-256 哈希值
    """
    if seed is None:
        seed = str(uuid.uuid4())

    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def get_effective_machine_id(
    credential_machine_id: Optional[str],
    global_machine_id: Optional[str],
    refresh_token: Optional[str],
) -> str:
    """获取有效的 Machine ID

    按优先级链解析：
    1. 凭据级 machine_id（如果已配置）
    2. 全局 MACHINE_ID 配置
    3. 由 refresh_token 派生

    Args:
        credential_machine_id: 凭据级配置
        global_machine_id: 全局配置
        refresh_token: 刷新令牌（用于派生）

    Returns:
        Machine ID 字符串
    """
    if credential_machine_id:
        return credential_machine_id
    if global_machine_id:
        return global_machine_id
    return generate_machine_id(refresh_token)
