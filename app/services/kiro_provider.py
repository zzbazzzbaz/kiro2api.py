"""
Kiro API Provider

从 kiro.rs 移植，核心组件，负责与 Kiro API 通信。
支持流式和非流式请求，多凭据故障转移和重试机制。
"""

import asyncio
import json
import random
import uuid
from typing import Optional

import httpx
from loguru import logger

from app.core.config import Settings
from app.models.credential import Credential
from app.services.token_manager import CallContext, MultiTokenManager
from app.utils.http_client import build_client, get_effective_proxy
from app.utils.machine_id import get_effective_machine_id

# 每个凭据的最大重试次数
MAX_RETRIES_PER_CREDENTIAL: int = 3

# 总重试次数硬上限（避免无限重试）
MAX_TOTAL_RETRIES: int = 9

# 指数退避参数
BASE_DELAY_MS: int = 200
MAX_DELAY_MS: int = 2000


def _retry_delay(attempt: int) -> float:
    """计算指数退避延迟（秒）

    包含少量随机抖动，避免上游抖动时放大故障

    Args:
        attempt: 当前重试次数（从 0 开始）

    Returns:
        延迟秒数
    """
    exp = BASE_DELAY_MS * (2 ** min(attempt, 6))
    backoff = min(exp, MAX_DELAY_MS)
    jitter_max = max(backoff // 4, 1)
    jitter = random.randint(0, jitter_max)
    return (backoff + jitter) / 1000.0


def _is_monthly_request_limit(body: str) -> bool:
    """检查响应体是否包含额度用尽标识

    兼容多种格式：
    - 直接包含 "MONTHLY_REQUEST_COUNT"
    - {"reason": "MONTHLY_REQUEST_COUNT"}
    - {"error": {"reason": "MONTHLY_REQUEST_COUNT"}}
    """
    if "MONTHLY_REQUEST_COUNT" in body:
        return True

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return False

    # 检查顶层 reason
    if isinstance(data, dict):
        if data.get("reason") == "MONTHLY_REQUEST_COUNT":
            return True
        # 检查 error.reason
        error = data.get("error")
        if isinstance(error, dict) and error.get("reason") == "MONTHLY_REQUEST_COUNT":
            return True

    return False


class KiroProvider:
    """Kiro API Provider

    核心组件，负责与 Kiro API 通信。
    支持多凭据故障转移和重试机制。

    重试策略：
    - 400 Bad Request: 直接返回错误，不计入凭据失败
    - 401/403: 视为凭据/权限问题，计入失败次数并允许故障转移
    - 402 MONTHLY_REQUEST_COUNT: 视为额度用尽，禁用凭据并切换
    - 429/5xx/网络等瞬态错误: 重试但不禁用或切换凭据
    """

    def __init__(self, token_manager: MultiTokenManager):
        self._token_manager = token_manager
        self._settings = token_manager.settings

    @property
    def token_manager(self) -> MultiTokenManager:
        return self._token_manager

    # ========================================================================
    # URL 构建
    # ========================================================================

    def base_url(self) -> str:
        """获取 API 基础 URL（使用全局 api_region）"""
        return f"https://q.{self._settings.effective_api_region}.amazonaws.com/generateAssistantResponse"

    def mcp_url(self) -> str:
        """获取 MCP API URL（使用全局 api_region）"""
        return f"https://q.{self._settings.effective_api_region}.amazonaws.com/mcp"

    def base_domain(self) -> str:
        """获取 API 基础域名（使用全局 api_region）"""
        return f"q.{self._settings.effective_api_region}.amazonaws.com"

    def _base_url_for(self, credential: Credential) -> str:
        """获取凭据级 API 基础 URL"""
        region = credential.api_region or self._settings.effective_api_region
        return f"https://q.{region}.amazonaws.com/generateAssistantResponse"

    def _mcp_url_for(self, credential: Credential) -> str:
        """获取凭据级 MCP API URL"""
        region = credential.api_region or self._settings.effective_api_region
        return f"https://q.{region}.amazonaws.com/mcp"

    def _base_domain_for(self, credential: Credential) -> str:
        """获取凭据级 API 基础域名"""
        region = credential.api_region or self._settings.effective_api_region
        return f"q.{region}.amazonaws.com"

    # ========================================================================
    # 请求头构建
    # ========================================================================

    def _get_machine_id(self, credential: Credential) -> str:
        """获取凭据的 Machine ID"""
        return get_effective_machine_id(
            credential.machine_id,
            credential.refresh_token,
        )

    def _build_headers(self, ctx: CallContext) -> dict:
        """构建 generateAssistantResponse 请求头

        Args:
            ctx: API 调用上下文
        """
        machine_id = self._get_machine_id(ctx.credential)
        kiro_version = self._settings.KIRO_VERSION
        os_name = self._settings.SYSTEM_VERSION
        node_version = self._settings.NODE_VERSION

        x_amz_user_agent = f"aws-sdk-js/1.0.27 KiroIDE-{kiro_version}-{machine_id}"
        user_agent = (
            f"aws-sdk-js/1.0.27 ua/2.1 os/{os_name} lang/js md/nodejs#{node_version} "
            f"api/codewhispererstreaming#1.0.27 m/E KiroIDE-{kiro_version}-{machine_id}"
        )

        return {
            "Content-Type": "application/json",
            "x-amzn-codewhisperer-optout": "true",
            "x-amzn-kiro-agent-mode": "vibe",
            "x-amz-user-agent": x_amz_user_agent,
            "User-Agent": user_agent,
            "host": self._base_domain_for(ctx.credential),
            "amz-sdk-invocation-id": str(uuid.uuid4()),
            "amz-sdk-request": "attempt=1; max=3",
            "Authorization": f"Bearer {ctx.token}",
            "Connection": "close",
        }

    def _build_mcp_headers(self, ctx: CallContext) -> dict:
        """构建 MCP 请求头

        Args:
            ctx: API 调用上下文
        """
        machine_id = self._get_machine_id(ctx.credential)
        kiro_version = self._settings.KIRO_VERSION
        os_name = self._settings.SYSTEM_VERSION
        node_version = self._settings.NODE_VERSION

        x_amz_user_agent = f"aws-sdk-js/1.0.27 KiroIDE-{kiro_version}-{machine_id}"
        user_agent = (
            f"aws-sdk-js/1.0.27 ua/2.1 os/{os_name} lang/js md/nodejs#{node_version} "
            f"api/codewhispererstreaming#1.0.27 m/E KiroIDE-{kiro_version}-{machine_id}"
        )

        return {
            "Content-Type": "application/json",
            "x-amz-user-agent": x_amz_user_agent,
            "User-Agent": user_agent,
            "host": self._base_domain_for(ctx.credential),
            "amz-sdk-invocation-id": str(uuid.uuid4()),
            "amz-sdk-request": "attempt=1; max=3",
            "Authorization": f"Bearer {ctx.token}",
            "Connection": "close",
        }

    # ========================================================================
    # HTTP 客户端
    # ========================================================================

    def _client_for(self, credential: Credential) -> httpx.AsyncClient:
        """根据凭据的代理配置获取（或创建并缓存）httpx AsyncClient"""
        proxy_url, proxy_username, proxy_password = get_effective_proxy(
            credential.proxy_url, credential.proxy_username, credential.proxy_password,
            self._settings.PROXY_URL, self._settings.PROXY_USERNAME, self._settings.PROXY_PASSWORD,
        )
        return build_client(proxy_url, proxy_username, proxy_password, timeout=720.0)

    # ========================================================================
    # 模型提取
    # ========================================================================

    @staticmethod
    def _extract_model_from_request(request_body: str) -> Optional[str]:
        """从请求体中提取模型名称

        尝试解析 JSON，提取 conversationState.currentMessage.userInputMessage.modelId
        """
        try:
            data = json.loads(request_body)
            return (
                data.get("conversationState", {})
                .get("currentMessage", {})
                .get("userInputMessage", {})
                .get("modelId")
            )
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None

    # ========================================================================
    # 公开 API
    # ========================================================================

    async def call_api(self, request_body: str) -> httpx.Response:
        """发送非流式 API 请求

        支持多凭据故障转移。

        Args:
            request_body: JSON 格式的请求体字符串

        Returns:
            httpx.Response

        Raises:
            ValueError: 所有重试均失败
        """
        return await self._call_api_with_retry(request_body, is_stream=False)

    async def call_api_stream(self, request_body: str) -> httpx.Response:
        """发送流式 API 请求

        支持多凭据故障转移。返回的 Response 需由调用方处理流式数据。

        Args:
            request_body: JSON 格式的请求体字符串

        Returns:
            httpx.Response（流式）

        Raises:
            ValueError: 所有重试均失败
        """
        return await self._call_api_with_retry(request_body, is_stream=True)

    async def call_mcp(self, request_body: str) -> httpx.Response:
        """发送 MCP API 请求（用于 WebSearch 等工具调用）

        Args:
            request_body: JSON 格式的 MCP 请求体字符串

        Returns:
            httpx.Response

        Raises:
            ValueError: 所有重试均失败
        """
        return await self._call_mcp_with_retry(request_body)

    async def get_usage_limits(self, credential_id: int) -> dict:
        """获取指定凭据的使用额度信息

        调用 Kiro getUsageLimits API 查询账户使用量和配额。
        与 kiro.rs get_usage_limits 逻辑完全一致。

        Args:
            credential_id: 凭据 ID

        Returns:
            上游返回的原始 JSON dict

        Raises:
            ValueError: 凭据不存在或 API 调用失败
        """
        ctx = await self._token_manager.acquire_context_for(credential_id)

        machine_id = self._get_machine_id(ctx.credential)
        kiro_version = self._settings.KIRO_VERSION
        os_name = self._settings.SYSTEM_VERSION
        node_version = self._settings.NODE_VERSION
        host = self._base_domain_for(ctx.credential)

        # 构建 URL
        url = f"https://{host}/getUsageLimits?origin=AI_EDITOR&resourceType=AGENTIC_REQUEST"
        if ctx.credential.profile_arn:
            from urllib.parse import quote
            url += f"&profileArn={quote(ctx.credential.profile_arn, safe='')}"

        # 构建请求头（与 kiro.rs 一致，使用 codewhispererruntime 而非 streaming）
        x_amz_user_agent = f"aws-sdk-js/1.0.0 KiroIDE-{kiro_version}-{machine_id}"
        user_agent = (
            f"aws-sdk-js/1.0.0 ua/2.1 os/{os_name} lang/js md/nodejs#{node_version} "
            f"api/codewhispererruntime#1.0.0 m/N,E KiroIDE-{kiro_version}-{machine_id}"
        )

        headers = {
            "x-amz-user-agent": x_amz_user_agent,
            "User-Agent": user_agent,
            "host": host,
            "amz-sdk-invocation-id": str(uuid.uuid4()),
            "amz-sdk-request": "attempt=1; max=1",
            "Authorization": f"Bearer {ctx.token}",
            "Connection": "close",
        }

        client = self._client_for(ctx.credential)
        try:
            response = await client.get(url, headers=headers)
        except Exception as e:
            raise ValueError(f"getUsageLimits 请求失败: {e}")

        if response.status_code != 200:
            body = response.text
            error_map = {
                401: "认证失败，Token 无效或已过期",
                403: "权限不足，无法获取使用额度",
                429: "请求过于频繁，已被限流",
            }
            msg = error_map.get(response.status_code, "获取使用额度失败")
            raise ValueError(f"{msg}: {response.status_code} {body[:200]}")

        return response.json()

    # ========================================================================
    # 内部重试逻辑
    # ========================================================================

    async def _call_api_with_retry(
        self, request_body: str, is_stream: bool
    ) -> httpx.Response:
        """带重试逻辑的 API 调用

        重试策略：
        - 每个凭据最多重试 MAX_RETRIES_PER_CREDENTIAL 次
        - 总重试次数 = min(凭据数量 × 每凭据重试次数, MAX_TOTAL_RETRIES)
        """
        total_credentials = self._token_manager.total_count
        max_retries = min(total_credentials * MAX_RETRIES_PER_CREDENTIAL, MAX_TOTAL_RETRIES)
        max_retries = max(max_retries, 1)  # 至少尝试一次
        last_error: Optional[Exception] = None
        api_type = "流式" if is_stream else "非流式"

        # 尝试从请求体中提取模型信息
        model = self._extract_model_from_request(request_body)

        for attempt in range(max_retries):
            # 获取调用上下文
            try:
                ctx = await self._token_manager.acquire_context(model)
            except Exception as e:
                last_error = e
                continue

            url = self._base_url_for(ctx.credential)
            headers = self._build_headers(ctx)
            client = self._client_for(ctx.credential)

            # 发送请求
            try:
                if is_stream:
                    # 流式请求：使用 stream 上下文
                    request = client.build_request("POST", url, headers=headers, content=request_body)
                    response = await client.send(request, stream=True)
                else:
                    response = await client.post(url, headers=headers, content=request_body)
            except Exception as e:
                logger.warning(
                    "API 请求发送失败（尝试 %d/%d）: %s",
                    attempt + 1, max_retries, e,
                )
                last_error = e
                if attempt + 1 < max_retries:
                    await asyncio.sleep(_retry_delay(attempt))
                continue

            status = response.status_code

            # 成功响应
            if 200 <= status < 300:
                self._token_manager.report_success(ctx.id)
                return response

            # 失败响应：读取 body
            if is_stream:
                body = (await response.aread()).decode("utf-8", errors="replace")
            else:
                body = response.text

            # 402 额度用尽
            if status == 402 and _is_monthly_request_limit(body):
                logger.warning(
                    "API 请求失败（额度已用尽，禁用凭据并切换，尝试 %d/%d）: %d %s",
                    attempt + 1, max_retries, status, body,
                )
                has_available = self._token_manager.report_quota_exhausted(ctx.id)
                if not has_available:
                    raise ValueError(f"{api_type} API 请求失败（所有凭据已用尽）: {status} {body}")
                last_error = ValueError(f"{api_type} API 请求失败: {status} {body}")
                continue

            # 400 Bad Request
            if status == 400:
                raise ValueError(f"{api_type} API 请求失败: {status} {body}")

            # 401/403 凭据问题
            if status in (401, 403):
                logger.warning(
                    "API 请求失败（可能为凭据错误，尝试 %d/%d）: %d %s",
                    attempt + 1, max_retries, status, body,
                )
                has_available = self._token_manager.report_failure(ctx.id)
                if not has_available:
                    raise ValueError(f"{api_type} API 请求失败（所有凭据已用尽）: {status} {body}")
                last_error = ValueError(f"{api_type} API 请求失败: {status} {body}")
                continue

            # 429/408/5xx 瞬态错误
            if status in (408, 429) or status >= 500:
                logger.warning(
                    "API 请求失败（上游瞬态错误，尝试 %d/%d）: %d %s",
                    attempt + 1, max_retries, status, body,
                )
                last_error = ValueError(f"{api_type} API 请求失败: {status} {body}")
                if attempt + 1 < max_retries:
                    await asyncio.sleep(_retry_delay(attempt))
                continue

            # 其他 4xx
            if 400 <= status < 500:
                raise ValueError(f"{api_type} API 请求失败: {status} {body}")

            # 兜底
            logger.warning(
                "API 请求失败（未知错误，尝试 %d/%d）: %d %s",
                attempt + 1, max_retries, status, body,
            )
            last_error = ValueError(f"{api_type} API 请求失败: {status} {body}")
            if attempt + 1 < max_retries:
                await asyncio.sleep(_retry_delay(attempt))

        raise last_error or ValueError(
            f"{api_type} API 请求失败：已达到最大重试次数（{max_retries}次）"
        )

    async def _call_mcp_with_retry(self, request_body: str) -> httpx.Response:
        """带重试逻辑的 MCP API 调用"""
        total_credentials = self._token_manager.total_count
        max_retries = min(total_credentials * MAX_RETRIES_PER_CREDENTIAL, MAX_TOTAL_RETRIES)
        max_retries = max(max_retries, 1)
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            # MCP 调用不涉及模型选择
            try:
                ctx = await self._token_manager.acquire_context(None)
            except Exception as e:
                last_error = e
                continue

            url = self._mcp_url_for(ctx.credential)
            headers = self._build_mcp_headers(ctx)
            client = self._client_for(ctx.credential)

            # 发送请求
            try:
                response = await client.post(url, headers=headers, content=request_body)
            except Exception as e:
                logger.warning("MCP 请求发送失败（尝试 {}/{}): {}", attempt + 1, max_retries, e)
                last_error = e
                if attempt + 1 < max_retries:
                    await asyncio.sleep(_retry_delay(attempt))
                continue

            status = response.status_code

            # 成功
            if 200 <= status < 300:
                self._token_manager.report_success(ctx.id)
                return response

            body = response.text

            # 402 额度用尽
            if status == 402 and _is_monthly_request_limit(body):
                has_available = self._token_manager.report_quota_exhausted(ctx.id)
                if not has_available:
                    raise ValueError(f"MCP 请求失败（所有凭据已用尽）: {status} {body}")
                last_error = ValueError(f"MCP 请求失败: {status} {body}")
                continue

            # 400
            if status == 400:
                raise ValueError(f"MCP 请求失败: {status} {body}")

            # 401/403
            if status in (401, 403):
                has_available = self._token_manager.report_failure(ctx.id)
                if not has_available:
                    raise ValueError(f"MCP 请求失败（所有凭据已用尽）: {status} {body}")
                last_error = ValueError(f"MCP 请求失败: {status} {body}")
                continue

            # 瞬态错误
            if status in (408, 429) or status >= 500:
                logger.warning(
                    "MCP 请求失败（上游瞬态错误，尝试 %d/%d）: %d %s",
                    attempt + 1, max_retries, status, body,
                )
                last_error = ValueError(f"MCP 请求失败: {status} {body}")
                if attempt + 1 < max_retries:
                    await asyncio.sleep(_retry_delay(attempt))
                continue

            # 其他 4xx
            if 400 <= status < 500:
                raise ValueError(f"MCP 请求失败: {status} {body}")

            # 兜底
            last_error = ValueError(f"MCP 请求失败: {status} {body}")
            if attempt + 1 < max_retries:
                await asyncio.sleep(_retry_delay(attempt))

        raise last_error or ValueError(
            f"MCP 请求失败：已达到最大重试次数（{max_retries}次）"
        )
