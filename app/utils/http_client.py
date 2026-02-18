"""
httpx 异步 HTTP 客户端构建器

支持代理配置（HTTP/HTTPS/SOCKS5），按代理配置缓存客户端实例
"""

from typing import Dict, Optional, Tuple

import httpx


# 按代理配置缓存的客户端实例
_client_cache: Dict[Tuple[Optional[str], Optional[str], Optional[str]], httpx.AsyncClient] = {}


def _build_proxy_url(
    proxy_url: str,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None,
) -> str:
    """构建带认证信息的代理 URL

    Args:
        proxy_url: 代理地址（如 socks5://127.0.0.1:1080）
        proxy_username: 代理用户名
        proxy_password: 代理密码

    Returns:
        带认证信息的完整代理 URL
    """
    if proxy_username and proxy_password:
        # 在协议后面插入认证信息
        # socks5://127.0.0.1:1080 → socks5://user:pass@127.0.0.1:1080
        scheme_end = proxy_url.index("://") + 3
        return f"{proxy_url[:scheme_end]}{proxy_username}:{proxy_password}@{proxy_url[scheme_end:]}"
    return proxy_url


def build_client(
    proxy_url: Optional[str] = None,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None,
    timeout: float = 300.0,
) -> httpx.AsyncClient:
    """构建或获取缓存的 httpx AsyncClient

    按代理配置缓存客户端实例，相同代理配置复用同一客户端。
    与 kiro.rs 的 client_cache 模式一致。

    Args:
        proxy_url: 代理地址（支持 http/https/socks5）
        proxy_username: 代理用户名
        proxy_password: 代理密码
        timeout: 请求超时时间（秒）

    Returns:
        httpx.AsyncClient 实例
    """
    cache_key = (proxy_url, proxy_username, proxy_password)

    if cache_key in _client_cache:
        return _client_cache[cache_key]

    # 构建客户端参数
    kwargs: dict = {
        "timeout": httpx.Timeout(timeout, connect=30.0),
        "follow_redirects": True,
        "http2": False,
    }

    # 配置代理
    if proxy_url:
        full_proxy_url = _build_proxy_url(proxy_url, proxy_username, proxy_password)
        kwargs["proxy"] = full_proxy_url

    client = httpx.AsyncClient(**kwargs)
    _client_cache[cache_key] = client
    return client


async def close_all_clients() -> None:
    """关闭所有缓存的客户端

    应在应用关闭时调用
    """
    for client in _client_cache.values():
        await client.aclose()
    _client_cache.clear()


def get_effective_proxy(
    credential_proxy_url: Optional[str],
    credential_proxy_username: Optional[str],
    credential_proxy_password: Optional[str],
    global_proxy_url: Optional[str],
    global_proxy_username: Optional[str],
    global_proxy_password: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """解析有效的代理配置

    优先级：凭据代理 > 全局代理 > 无代理
    特殊值 "direct" 表示显式不使用代理

    Args:
        credential_proxy_url: 凭据级代理 URL
        credential_proxy_username: 凭据级代理用户名
        credential_proxy_password: 凭据级代理密码
        global_proxy_url: 全局代理 URL
        global_proxy_username: 全局代理用户名
        global_proxy_password: 全局代理密码

    Returns:
        (proxy_url, proxy_username, proxy_password) 元组
    """
    if credential_proxy_url:
        # 特殊值 "direct" 表示不使用代理
        if credential_proxy_url.lower() == "direct":
            return (None, None, None)
        return (credential_proxy_url, credential_proxy_username, credential_proxy_password)

    if global_proxy_url:
        return (global_proxy_url, global_proxy_username, global_proxy_password)

    return (None, None, None)
