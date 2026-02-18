"""
Token 管理模块

从 kiro.rs 移植，负责：
- Social / IdC Token 刷新
- Token 过期检测（5 分钟提前量）
- 单凭据 TokenManager
- 多凭据 MultiTokenManager（优先级/均衡模式、故障转移、Admin API 操作）
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import httpx
from loguru import logger

from app.core.config import Settings
from app.models.credential import Credential
from app.utils.helpers import now_rfc3339, parse_rfc3339
from app.utils.http_client import build_client, get_effective_proxy
from app.utils.machine_id import get_effective_machine_id

# 每个凭据最大 API 调用连续失败次数
MAX_FAILURES_PER_CREDENTIAL: int = 3

# IdC Token 刷新所需的 x-amz-user-agent header
IDC_AMZ_USER_AGENT: str = (
    "aws-sdk-js/3.738.0 ua/2.1 os/other lang/js md/browser#unknown_unknown "
    "api/sso-oidc#3.738.0 m/E KiroIDE"
)


# ============================================================================
# Token 过期检测
# ============================================================================


def is_token_expiring_within(expires_at: Optional[str], minutes: int) -> Optional[bool]:
    """检查 Token 是否在指定分钟内过期

    Args:
        expires_at: RFC3339 格式的过期时间
        minutes: 检查的分钟数

    Returns:
        True/False 或 None（无法判断时）
    """
    if not expires_at:
        return None
    try:
        expiry = parse_rfc3339(expires_at)
        threshold = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return expiry <= threshold
    except (ValueError, TypeError):
        return None


def is_token_expired(expires_at: Optional[str]) -> bool:
    """检查 Token 是否已过期（提前 5 分钟判断）"""
    result = is_token_expiring_within(expires_at, 5)
    return result if result is not None else True


def is_token_expiring_soon(expires_at: Optional[str]) -> bool:
    """检查 Token 是否即将过期（10 分钟内）"""
    result = is_token_expiring_within(expires_at, 10)
    return result if result is not None else False


def validate_refresh_token(refresh_token: Optional[str]) -> None:
    """验证 refreshToken 的基本有效性

    Raises:
        ValueError: Token 无效时
    """
    if not refresh_token:
        raise ValueError("缺少 refreshToken")
    if len(refresh_token) < 100 or refresh_token.endswith("...") or "..." in refresh_token:
        raise ValueError(
            f"refreshToken 已被截断（长度: {len(refresh_token)} 字符）。"
            "这通常是 Kiro IDE 为了防止凭证被第三方工具使用而故意截断的。"
        )


# ============================================================================
# Token 刷新
# ============================================================================


def _get_effective_auth_region(credential: Credential, settings: Settings) -> str:
    """获取有效的 Auth Region

    优先级：凭据.auth_region > 凭据.region > 全局 AUTH_REGION > 全局 REGION
    """
    return (
        credential.auth_region
        or credential.region
        or settings.effective_auth_region
    )


def _get_machine_id(credential: Credential, settings: Settings) -> str:
    """获取凭据的 Machine ID"""
    return get_effective_machine_id(
        credential.machine_id,
        credential.refresh_token,
    )


async def refresh_social_token(
    credential: Credential,
    settings: Settings,
) -> dict:
    """刷新 Social Token

    POST https://prod.{region}.auth.desktop.kiro.dev/refreshToken

    Args:
        credential: 凭据对象
        settings: 全局配置

    Returns:
        包含新 Token 信息的字典：
        {access_token, refresh_token?, profile_arn?, expires_at?}

    Raises:
        httpx.HTTPStatusError: 刷新失败
        ValueError: 凭据无效
    """
    logger.info("正在刷新 Social Token (凭据 #{})...", credential.id)
    validate_refresh_token(credential.refresh_token)

    region = _get_effective_auth_region(credential, settings)
    machine_id = _get_machine_id(credential, settings)

    refresh_url = f"https://prod.{region}.auth.desktop.kiro.dev/refreshToken"
    refresh_domain = f"prod.{region}.auth.desktop.kiro.dev"

    proxy_url, proxy_username, proxy_password = get_effective_proxy(
        credential.proxy_url, credential.proxy_username, credential.proxy_password,
        settings.PROXY_URL, settings.PROXY_USERNAME, settings.PROXY_PASSWORD,
    )
    client = build_client(proxy_url, proxy_username, proxy_password, timeout=60.0)

    body = {"refreshToken": credential.refresh_token}

    response = await client.post(
        refresh_url,
        json=body,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": f"KiroIDE-{settings.KIRO_VERSION}-{machine_id}",
            "Accept-Encoding": "gzip, compress, deflate, br",
            "host": refresh_domain,
            "Connection": "close",
        },
    )

    if response.status_code != 200:
        error_messages = {
            401: "OAuth 凭证已过期或无效，需要重新认证",
            403: "权限不足，无法刷新 Token",
            429: "请求过于频繁，已被限流",
        }
        msg = error_messages.get(
            response.status_code,
            "服务器错误" if response.status_code >= 500 else "Token 刷新失败",
        )
        raise ValueError(f"{msg}: {response.status_code} {response.text}")

    data = response.json()

    result = {"access_token": data["accessToken"]}
    if "refreshToken" in data and data["refreshToken"]:
        result["refresh_token"] = data["refreshToken"]
    if "profileArn" in data and data["profileArn"]:
        result["profile_arn"] = data["profileArn"]
    if "expiresIn" in data and data["expiresIn"]:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expiresIn"])
        result["expires_at"] = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    return result


async def refresh_idc_token(
    credential: Credential,
    settings: Settings,
) -> dict:
    """刷新 IdC Token (AWS SSO OIDC)

    POST https://oidc.{region}.amazonaws.com/token

    Args:
        credential: 凭据对象（需包含 client_id 和 client_secret）
        settings: 全局配置

    Returns:
        包含新 Token 信息的字典

    Raises:
        ValueError: 凭据缺少必要字段或刷新失败
    """
    logger.info("正在刷新 IdC Token (凭据 #{})...", credential.id)
    validate_refresh_token(credential.refresh_token)

    if not credential.client_id:
        raise ValueError("IdC 刷新需要 clientId")
    if not credential.client_secret:
        raise ValueError("IdC 刷新需要 clientSecret")

    region = _get_effective_auth_region(credential, settings)
    refresh_url = f"https://oidc.{region}.amazonaws.com/token"

    proxy_url, proxy_username, proxy_password = get_effective_proxy(
        credential.proxy_url, credential.proxy_username, credential.proxy_password,
        settings.PROXY_URL, settings.PROXY_USERNAME, settings.PROXY_PASSWORD,
    )
    client = build_client(proxy_url, proxy_username, proxy_password, timeout=60.0)

    body = {
        "clientId": credential.client_id,
        "clientSecret": credential.client_secret,
        "refreshToken": credential.refresh_token,
        "grantType": "refresh_token",
    }

    response = await client.post(
        refresh_url,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Host": f"oidc.{region}.amazonaws.com",
            "Connection": "keep-alive",
            "x-amz-user-agent": IDC_AMZ_USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "*",
            "sec-fetch-mode": "cors",
            "User-Agent": "node",
            "Accept-Encoding": "br, gzip, deflate",
        },
    )

    if response.status_code != 200:
        error_messages = {
            401: "IdC 凭证已过期或无效，需要重新认证",
            403: "权限不足，无法刷新 Token",
            429: "请求过于频繁，已被限流",
        }
        msg = error_messages.get(
            response.status_code,
            "服务器错误" if response.status_code >= 500 else "IdC Token 刷新失败",
        )
        raise ValueError(f"{msg}: {response.status_code} {response.text}")

    data = response.json()

    result = {"access_token": data["accessToken"]}
    if "refreshToken" in data and data["refreshToken"]:
        result["refresh_token"] = data["refreshToken"]
    if "expiresIn" in data and data["expiresIn"]:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expiresIn"])
        result["expires_at"] = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    return result


async def refresh_token(credential: Credential, settings: Settings) -> dict:
    """根据认证方式自动选择刷新方法

    如果未指定 auth_method，根据是否有 client_id/client_secret 自动判断

    Args:
        credential: 凭据对象
        settings: 全局配置

    Returns:
        包含新 Token 信息的字典
    """
    auth_method = credential.auth_method or (
        "idc" if credential.client_id and credential.client_secret else "social"
    )

    if auth_method.lower() in ("idc", "builder-id", "iam"):
        return await refresh_idc_token(credential, settings)
    else:
        return await refresh_social_token(credential, settings)


# ============================================================================
# 凭据条目（内存状态）
# ============================================================================


class DisabledReason(Enum):
    """禁用原因"""
    MANUAL = "manual"                   # Admin API 手动禁用
    TOO_MANY_FAILURES = "too_many_failures"  # 连续失败达到阈值
    QUOTA_EXCEEDED = "quota_exceeded"   # 额度已用尽


@dataclass
class CredentialEntry:
    """单个凭据的运行时状态"""
    id: int
    credential: Credential
    failure_count: int = 0
    disabled: bool = False
    disabled_reason: Optional[DisabledReason] = None
    success_count: int = 0
    last_used_at: Optional[str] = None


@dataclass
class CallContext:
    """API 调用上下文

    绑定特定凭据的调用上下文，确保 token、credential 和 id 的一致性。
    用于解决并发调用时 current_id 竞态问题。
    """
    id: int
    credential: Credential
    token: str


@dataclass
class CredentialEntrySnapshot:
    """凭据条目快照（用于 Admin API 读取）"""
    id: int
    priority: int
    disabled: bool
    failure_count: int
    auth_method: Optional[str]
    has_profile_arn: bool
    expires_at: Optional[str]
    email: Optional[str]
    subscription_title: Optional[str]
    success_count: int
    last_used_at: Optional[str]
    has_proxy: bool
    proxy_url: Optional[str]
    token_valid: bool


@dataclass
class ManagerSnapshot:
    """管理器状态快照"""
    entries: List[CredentialEntrySnapshot]
    current_id: int
    total: int
    available: int


# ============================================================================
# TokenManager — 单凭据管理
# ============================================================================


class TokenManager:
    """单凭据 Token 生命周期管理

    负责单个凭据的 Token 过期检测和自动刷新
    """

    def __init__(self, credential: Credential, settings: Settings):
        self._credential = credential
        self._settings = settings

    @property
    def credential(self) -> Credential:
        return self._credential

    async def ensure_valid_token(self) -> str:
        """确保获取有效的访问 Token

        如果 Token 过期或即将过期，会自动刷新

        Returns:
            有效的 access_token

        Raises:
            ValueError: 无法获取有效 Token
        """
        if is_token_expired(self._credential.expires_at) or is_token_expiring_soon(self._credential.expires_at):
            result = await refresh_token(self._credential, self._settings)
            self._apply_refresh_result(result)

            if is_token_expired(self._credential.expires_at):
                raise ValueError("刷新后的 Token 仍然无效或已过期")

        if not self._credential.access_token:
            raise ValueError("没有可用的 accessToken")

        return self._credential.access_token

    def _apply_refresh_result(self, result: dict) -> None:
        """将刷新结果应用到凭据"""
        self._credential.access_token = result["access_token"]
        if "refresh_token" in result:
            self._credential.refresh_token = result["refresh_token"]
        if "profile_arn" in result:
            self._credential.profile_arn = result["profile_arn"]
        if "expires_at" in result:
            self._credential.expires_at = result["expires_at"]


# ============================================================================
# MultiTokenManager — 多凭据管理
# ============================================================================


class MultiTokenManager:
    """多凭据 Token 管理器

    支持多个凭据的管理，实现固定优先级 + 故障转移策略。
    故障统计基于 API 调用结果，而非 Token 刷新结果。

    核心特性：
    - 每凭据独立的 asyncio.Lock 防止并发刷新
    - 优先级模式 / 均衡模式凭据选择
    - Admin API 查询用快照方法
    - set_disabled / set_priority / reset_and_enable 操作
    - 失败时切换到下一个凭据
    - 刷新后将 Token 持久化到数据库
    """

    def __init__(
        self,
        settings: Settings,
        credentials: List[Credential],
        load_balancing_mode: str = "priority",
    ):
        self._settings = settings
        self._load_balancing_mode = load_balancing_mode

        # 构建凭据条目，并为未配置 machine_id 的凭据预先派生
        # 与 kiro.rs MultiTokenManager::new() 行为一致：
        # 每个凭据拥有独立的 machine_id，避免多账号共用同一设备指纹
        self._entries: List[CredentialEntry] = []
        for cred in credentials:
            # 预生成 machine_id（优先级：凭据级 > refresh_token 派生）
            # 注意：跳过全局 MACHINE_ID，确保多凭据各自独立
            if not cred.machine_id or not cred.machine_id.strip():
                if cred.refresh_token and cred.refresh_token.strip():
                    from app.utils.machine_id import generate_from_refresh_token
                    cred.machine_id = generate_from_refresh_token(cred.refresh_token)
                    logger.debug("凭据 #{} 已从 refresh_token 派生 machine_id", cred.id)

            self._entries.append(CredentialEntry(
                id=cred.id,
                credential=cred,
                disabled=cred.is_disabled,
                disabled_reason=DisabledReason.MANUAL if cred.is_disabled else None,
            ))

        # 当前活动凭据 ID：选择优先级最高（priority 最小）的可用凭据
        available = [e for e in self._entries if not e.disabled]
        self._current_id: int = (
            min(available, key=lambda e: e.credential.priority).id
            if available else 0
        )

        # Token 刷新锁（确保同一时间只有一个刷新操作）
        self._refresh_lock = asyncio.Lock()

        # 数据库持久化回调（由外部注入）
        self._persist_callback = None

    def set_persist_callback(self, callback) -> None:
        """设置数据库持久化回调

        callback 签名: async def callback(credential: Credential) -> None
        """
        self._persist_callback = callback

    # ========================================================================
    # 基础查询
    # ========================================================================

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def total_count(self) -> int:
        """凭据总数"""
        return len(self._entries)

    @property
    def available_count(self) -> int:
        """可用凭据数量"""
        return sum(1 for e in self._entries if not e.disabled)

    def credentials(self) -> Optional[Credential]:
        """获取当前活动凭据"""
        entry = self._find_entry(self._current_id)
        return entry.credential if entry else None

    def _find_entry(self, entry_id: int) -> Optional[CredentialEntry]:
        """根据 ID 查找凭据条目"""
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    # ========================================================================
    # 凭据选择
    # ========================================================================

    def _select_next_credential(self, model: Optional[str] = None) -> Optional[Tuple[int, Credential]]:
        """根据负载均衡模式选择下一个凭据

        - priority 模式：选择优先级最高（priority 最小）的可用凭据
        - balanced 模式：选择成功次数最少的可用凭据（平局按优先级）

        Args:
            model: 可选的模型名称，用于过滤（如 opus 需要付费订阅）
        """
        # 检查是否是 opus 模型
        is_opus = model and "opus" in model.lower() if model else False

        # 过滤可用凭据
        available = [
            e for e in self._entries
            if not e.disabled
            and (not is_opus or self._supports_opus(e.credential))
        ]

        if not available:
            return None

        if self._load_balancing_mode == "balanced":
            # Least-Used 策略：选择成功次数最少的，平局按优先级
            best = min(available, key=lambda e: (e.success_count, e.credential.priority))
        else:
            # priority 模式（默认）：选择优先级最高的
            best = min(available, key=lambda e: e.credential.priority)

        return (best.id, best.credential)

    @staticmethod
    def _supports_opus(credential: Credential) -> bool:
        """检查凭据是否支持 Opus 模型"""
        title = credential.subscription_title
        if not title:
            return True  # 未获取订阅信息时暂时允许
        return "FREE" not in title.upper()

    def _switch_to_next_by_priority(self) -> None:
        """切换到下一个优先级最高的可用凭据（排除当前）"""
        candidates = [
            e for e in self._entries
            if not e.disabled and e.id != self._current_id
        ]
        if candidates:
            best = min(candidates, key=lambda e: e.credential.priority)
            self._current_id = best.id
            logger.info("已切换到凭据 #{}（优先级 {}）", best.id, best.credential.priority)

    def _select_highest_priority(self) -> None:
        """选择优先级最高的可用凭据作为当前凭据（不排除当前）"""
        available = [e for e in self._entries if not e.disabled]
        if available:
            best = min(available, key=lambda e: e.credential.priority)
            if best.id != self._current_id:
                logger.info(
                    "优先级变更后切换凭据: #{} -> #{}（优先级 {}）",
                    self._current_id, best.id, best.credential.priority,
                )
                self._current_id = best.id

    # ========================================================================
    # Token 获取与刷新
    # ========================================================================

    async def acquire_context(self, model: Optional[str] = None) -> CallContext:
        """获取 API 调用上下文

        返回绑定了 id、credential 和 token 的调用上下文。
        如果 Token 过期会自动刷新，刷新失败时尝试下一个凭据。

        Args:
            model: 可选的模型名称

        Returns:
            CallContext 实例

        Raises:
            ValueError: 所有凭据均不可用
        """
        total = self.total_count
        tried_count = 0

        while tried_count < total:
            # 选择凭据
            is_balanced = self._load_balancing_mode == "balanced"

            current_hit = None
            if not is_balanced:
                entry = self._find_entry(self._current_id)
                if entry and not entry.disabled:
                    current_hit = (entry.id, entry.credential)

            if current_hit:
                cred_id, credential = current_hit
            else:
                best = self._select_next_credential(model)

                # 自愈：如果所有凭据都被自动禁用，重置并重新启用
                if best is None:
                    auto_disabled = [
                        e for e in self._entries
                        if e.disabled and e.disabled_reason == DisabledReason.TOO_MANY_FAILURES
                    ]
                    if auto_disabled:
                        logger.warning(
                            "所有凭据均已被自动禁用，执行自愈：重置失败计数并重新启用"
                        )
                        for e in auto_disabled:
                            e.disabled = False
                            e.disabled_reason = None
                            e.failure_count = 0
                        best = self._select_next_credential(model)

                if best is None:
                    raise ValueError(
                        f"所有凭据均已禁用（{self.available_count}/{total}）"
                    )

                cred_id, credential = best
                self._current_id = cred_id

            # 尝试获取/刷新 Token
            try:
                ctx = await self._try_ensure_token(cred_id, credential)
                return ctx
            except Exception as e:
                logger.warning(
                    "凭据 #{} Token 刷新失败，尝试下一个凭据: {}", cred_id, e
                )
                self._switch_to_next_by_priority()
                tried_count += 1

        raise ValueError(
            f"所有凭据均无法获取有效 Token（可用: {self.available_count}/{total}）"
        )

    async def acquire_context_for(self, credential_id: int) -> CallContext:
        """获取指定凭据的 API 调用上下文

        用于 Admin API 查询特定凭据的使用额度等场景。
        会自动刷新 Token（如果过期）。

        Args:
            credential_id: 凭据 ID

        Returns:
            CallContext 实例

        Raises:
            ValueError: 凭据不存在或 Token 刷新失败
        """
        entry = self._find_entry(credential_id)
        if not entry:
            raise ValueError(f"凭据 #{credential_id} 不存在")
        return await self._try_ensure_token(entry.id, entry.credential)

    async def _try_ensure_token(self, entry_id: int, credential: Credential) -> CallContext:
        """尝试使用指定凭据获取有效 Token

        使用双重检查锁定模式，确保同一时间只有一个刷新操作
        """
        # 第一次检查（无锁）：快速判断是否需要刷新
        needs_refresh = (
            is_token_expired(credential.expires_at)
            or is_token_expiring_soon(credential.expires_at)
        )

        if needs_refresh:
            async with self._refresh_lock:
                # 第二次检查：获取锁后重新读取凭据
                entry = self._find_entry(entry_id)
                if not entry:
                    raise ValueError(f"凭据 #{entry_id} 不存在")

                current_cred = entry.credential
                if is_token_expired(current_cred.expires_at) or is_token_expiring_soon(current_cred.expires_at):
                    # 确实需要刷新
                    result = await refresh_token(current_cred, self._settings)

                    # 应用刷新结果
                    current_cred.access_token = result["access_token"]
                    if "refresh_token" in result:
                        current_cred.refresh_token = result["refresh_token"]
                    if "profile_arn" in result:
                        current_cred.profile_arn = result["profile_arn"]
                    if "expires_at" in result:
                        current_cred.expires_at = result["expires_at"]

                    if is_token_expired(current_cred.expires_at):
                        raise ValueError("刷新后的 Token 仍然无效或已过期")

                    # 持久化到数据库
                    await self._persist_credential(current_cred)

                    credential = current_cred
                else:
                    # 其他协程已完成刷新
                    logger.debug("Token 已被其他请求刷新，跳过刷新")
                    credential = current_cred
        else:
            pass  # Token 仍然有效

        if not credential.access_token:
            raise ValueError("没有可用的 accessToken")

        return CallContext(
            id=entry_id,
            credential=credential,
            token=credential.access_token,
        )

    async def _persist_credential(self, credential: Credential) -> None:
        """将凭据持久化到数据库"""
        if self._persist_callback:
            try:
                await self._persist_callback(credential)
            except Exception as e:
                logger.warning("Token 刷新后持久化失败（不影响本次请求）: {}", e)

    # ========================================================================
    # API 调用结果报告
    # ========================================================================

    def report_success(self, entry_id: int) -> None:
        """报告 API 调用成功

        重置该凭据的失败计数，增加成功计数
        """
        entry = self._find_entry(entry_id)
        if entry:
            entry.failure_count = 0
            entry.success_count += 1
            entry.last_used_at = now_rfc3339()
            logger.debug("凭据 #{} API 调用成功（累计 {} 次）", entry_id, entry.success_count)

    def report_failure(self, entry_id: int) -> bool:
        """报告 API 调用失败

        增加失败计数，达到阈值时禁用凭据并切换。

        Returns:
            是否还有可用凭据可以重试
        """
        entry = self._find_entry(entry_id)
        if not entry:
            return self.available_count > 0

        entry.failure_count += 1
        entry.last_used_at = now_rfc3339()

        logger.warning(
            "凭据 #{} API 调用失败（{}/{})",
            entry_id, entry.failure_count, MAX_FAILURES_PER_CREDENTIAL,
        )

        if entry.failure_count >= MAX_FAILURES_PER_CREDENTIAL:
            entry.disabled = True
            entry.disabled_reason = DisabledReason.TOO_MANY_FAILURES
            logger.error("凭据 #{} 已连续失败 {} 次，已被禁用", entry_id, entry.failure_count)

            # 切换到优先级最高的可用凭据
            available = [e for e in self._entries if not e.disabled]
            if available:
                best = min(available, key=lambda e: e.credential.priority)
                self._current_id = best.id
                logger.info("已切换到凭据 #{}（优先级 {}）", best.id, best.credential.priority)
            else:
                logger.error("所有凭据均已禁用！")

        return self.available_count > 0

    def report_quota_exhausted(self, entry_id: int) -> bool:
        """报告凭据额度已用尽

        立即禁用该凭据（不等待连续失败阈值），切换到下一个可用凭据。

        Returns:
            是否还有可用凭据
        """
        entry = self._find_entry(entry_id)
        if not entry or entry.disabled:
            return self.available_count > 0

        entry.disabled = True
        entry.disabled_reason = DisabledReason.QUOTA_EXCEEDED
        entry.failure_count = MAX_FAILURES_PER_CREDENTIAL
        entry.last_used_at = now_rfc3339()

        logger.error("凭据 #{} 额度已用尽，已被禁用", entry_id)

        # 切换到优先级最高的可用凭据
        available = [e for e in self._entries if not e.disabled]
        if available:
            best = min(available, key=lambda e: e.credential.priority)
            self._current_id = best.id
            logger.info("已切换到凭据 #{}（优先级 {}）", best.id, best.credential.priority)
            return True
        else:
            logger.error("所有凭据均已禁用！")
            return False

    def switch_to_next(self) -> bool:
        """切换到优先级最高的可用凭据（排除当前）

        Returns:
            是否成功切换（或当前凭据仍可用）
        """
        candidates = [
            e for e in self._entries
            if not e.disabled and e.id != self._current_id
        ]
        if candidates:
            best = min(candidates, key=lambda e: e.credential.priority)
            self._current_id = best.id
            logger.info("已切换到凭据 #{}（优先级 {}）", best.id, best.credential.priority)
            return True
        # 没有其他可用凭据，检查当前凭据是否可用
        return any(e.id == self._current_id and not e.disabled for e in self._entries)

    # ========================================================================
    # Admin API 方法
    # ========================================================================

    def snapshot(self) -> ManagerSnapshot:
        """获取管理器状态快照（用于 Admin API）"""
        available = sum(1 for e in self._entries if not e.disabled)
        entries = []
        for e in self._entries:
            entries.append(CredentialEntrySnapshot(
                id=e.id,
                priority=e.credential.priority,
                disabled=e.disabled,
                failure_count=e.failure_count,
                auth_method=e.credential.auth_method,
                has_profile_arn=bool(e.credential.profile_arn),
                expires_at=e.credential.expires_at,
                email=e.credential.email,
                subscription_title=e.credential.subscription_title,
                success_count=e.success_count,
                last_used_at=e.last_used_at,
                has_proxy=bool(e.credential.proxy_url),
                proxy_url=e.credential.proxy_url,
                token_valid=not is_token_expired(e.credential.expires_at),
            ))

        return ManagerSnapshot(
            entries=entries,
            current_id=self._current_id,
            total=len(self._entries),
            available=available,
        )

    def set_disabled(self, entry_id: int, disabled: bool) -> None:
        """设置凭据禁用状态

        Raises:
            ValueError: 凭据不存在
        """
        entry = self._find_entry(entry_id)
        if not entry:
            raise ValueError(f"凭据不存在: {entry_id}")

        entry.disabled = disabled
        if not disabled:
            entry.failure_count = 0
            entry.disabled_reason = None
        else:
            entry.disabled_reason = DisabledReason.MANUAL

    def set_priority(self, entry_id: int, priority: int) -> None:
        """设置凭据优先级

        修改后会立即按新优先级重新选择当前凭据

        Raises:
            ValueError: 凭据不存在
        """
        entry = self._find_entry(entry_id)
        if not entry:
            raise ValueError(f"凭据不存在: {entry_id}")

        entry.credential.priority = priority
        # 立即按新优先级重新选择当前凭据
        self._select_highest_priority()

    def reset_and_enable(self, entry_id: int) -> None:
        """重置凭据失败计数并重新启用

        Raises:
            ValueError: 凭据不存在
        """
        entry = self._find_entry(entry_id)
        if not entry:
            raise ValueError(f"凭据不存在: {entry_id}")

        entry.failure_count = 0
        entry.disabled = False
        entry.disabled_reason = None

    def add_entry(self, credential: Credential) -> None:
        """添加新凭据条目"""
        self._entries.append(CredentialEntry(
            id=credential.id,
            credential=credential,
        ))
        # 如果当前无活动凭据，选择新加入的
        if self._current_id == 0:
            self._current_id = credential.id

    def remove_entry(self, entry_id: int) -> None:
        """移除凭据条目

        Raises:
            ValueError: 凭据不存在或未禁用
        """
        entry = self._find_entry(entry_id)
        if not entry:
            raise ValueError(f"凭据不存在: {entry_id}")
        if not entry.disabled:
            raise ValueError(f"只能删除已禁用的凭据（请先禁用凭据 #{entry_id}）")

        was_current = self._current_id == entry_id
        self._entries = [e for e in self._entries if e.id != entry_id]

        if was_current:
            self._select_highest_priority()

        if not self._entries:
            self._current_id = 0
            logger.info("所有凭据已删除，current_id 已重置为 0")

    def get_load_balancing_mode(self) -> str:
        """获取当前负载均衡模式"""
        return self._load_balancing_mode

    def set_load_balancing_mode(self, mode: str) -> None:
        """设置负载均衡模式

        Raises:
            ValueError: 无效的模式值
        """
        if mode not in ("priority", "balanced"):
            raise ValueError(f"无效的负载均衡模式: {mode}")
        self._load_balancing_mode = mode
        logger.info("负载均衡模式已设置为: {}", mode)

    # ========================================================================
    # 后台刷新循环（可选）
    # ========================================================================

    async def background_refresh_loop(self, interval_seconds: int = 300) -> None:
        """后台刷新循环

        主动刷新 10 分钟内即将过期的 Token，避免请求时阻塞刷新。

        Args:
            interval_seconds: 检查间隔（秒），默认 5 分钟
        """
        logger.info("后台 Token 刷新循环已启动（间隔 {} 秒）", interval_seconds)
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self._refresh_expiring_tokens()
            except asyncio.CancelledError:
                logger.info("后台 Token 刷新循环已停止")
                break
            except Exception as e:
                logger.error("后台 Token 刷新出错: {}", e)

    async def _refresh_expiring_tokens(self) -> None:
        """刷新即将过期的 Token"""
        for entry in self._entries:
            if entry.disabled:
                continue
            if not is_token_expiring_soon(entry.credential.expires_at):
                continue

            logger.info("后台刷新: 凭据 #{} Token 即将过期", entry.id)
            try:
                async with self._refresh_lock:
                    # 双重检查
                    if not is_token_expiring_soon(entry.credential.expires_at):
                        continue

                    result = await refresh_token(entry.credential, self._settings)
                    entry.credential.access_token = result["access_token"]
                    if "refresh_token" in result:
                        entry.credential.refresh_token = result["refresh_token"]
                    if "profile_arn" in result:
                        entry.credential.profile_arn = result["profile_arn"]
                    if "expires_at" in result:
                        entry.credential.expires_at = result["expires_at"]

                    await self._persist_credential(entry.credential)
                    logger.info("后台刷新: 凭据 #{} Token 已刷新", entry.id)
            except Exception as e:
                logger.warning("后台刷新: 凭据 #{} 刷新失败: {}", entry.id, e)
