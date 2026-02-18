"""
调试日志中间件

异步记录请求/响应在各转换阶段的数据。
日志写入 data/debug-log/{stage}/{dd}/{hh}/{mm}/{ss}/{id}/{input,output} 目录。

三个阶段：
- openai_anthropic: OpenAI 格式 → Anthropic 格式
- anthropic_kiro: Anthropic 格式 → Kiro 格式
- kiro_anthropic: Kiro 返回 → Anthropic 格式

通过 .env 中的 DEBUG_LOG_MIDDLEWARE_* 配置开关。
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from app.core.config import get_settings


# ============================================================================
# 请求 ID 管理
# ============================================================================


def generate_request_id() -> str:
    """生成唯一请求 ID"""
    return uuid.uuid4().hex[:12]


# ============================================================================
# 异步文件写入
# ============================================================================


async def _write_file_async(path: Path, content: str) -> None:
    """异步写入文件（在线程池中执行 I/O）"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _write_file_sync, path, content)


def _write_file_sync(path: Path, content: str) -> None:
    """同步写入文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ============================================================================
# 日志目录构建
# ============================================================================


def _build_log_dir(stage: str, request_id: str, timestamp: Optional[datetime] = None) -> Path:
    """构建日志目录路径: data/debug-log/{stage}/{dd}/{hh}/{mm}/{ss}/{id}/

    Args:
        stage: 阶段名 (openai_anthropic / anthropic_kiro / kiro_anthropic)
        request_id: 请求唯一 ID
        timestamp: 时间戳，默认 now()
    """
    settings = get_settings()
    base_dir = Path(settings.DEBUG_LOG_DIR)
    ts = timestamp or datetime.now()

    return base_dir / stage / ts.strftime("%d") / ts.strftime("%H") / ts.strftime("%M") / ts.strftime("%S") / request_id


# ============================================================================
# 数据格式化
# ============================================================================


def _serialize(data: Any) -> str:
    """将数据序列化为格式化 JSON 字符串"""
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            return data
    if hasattr(data, "model_dump"):
        return json.dumps(data.model_dump(), ensure_ascii=False, indent=2, default=str)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _headers_to_dict(headers: Any) -> Dict[str, str]:
    """将请求头转换为可序列化字典"""
    if headers is None:
        return {}
    if isinstance(headers, dict):
        return headers
    # starlette Headers / MutableHeaders
    try:
        return dict(headers.items())
    except Exception:
        return {"_raw": str(headers)}


def _truncate_for_console(data: Any, max_len: int = 500) -> str:
    """截断数据用于控制台输出"""
    if isinstance(data, str):
        text = data
    elif isinstance(data, dict):
        text = json.dumps(data, ensure_ascii=False, default=str)
    elif hasattr(data, "model_dump"):
        text = json.dumps(data.model_dump(), ensure_ascii=False, default=str)
    else:
        text = str(data)

    if len(text) > max_len:
        return text[:max_len] + f"... ({len(text)} chars total)"
    return text


# ============================================================================
# 中间件 0: OpenAI → Anthropic (openai_anthropic)
# ============================================================================


async def log_middleware_0(
    request_id: str,
    openai_input: Any,
    anthropic_output: Any,
    headers: Any = None,
) -> None:
    """记录 OpenAI → Anthropic 转换

    Args:
        request_id: 请求 ID
        openai_input: 原始 OpenAI 格式请求
        anthropic_output: 转换后的 Anthropic 格式请求
        headers: 请求头
    """
    settings = get_settings()
    if not settings.DEBUG_LOG_MIDDLEWARE_0:
        return

    ts = datetime.now()
    log_dir = _build_log_dir("openai_anthropic", request_id, ts)

    logger.debug(
        "[M0][{rid}] OpenAI → Anthropic | input: {inp} | output: {out}",
        rid=request_id,
        inp=_truncate_for_console(openai_input, 300),
        out=_truncate_for_console(anthropic_output, 300),
    )

    input_data = {
        "headers": _headers_to_dict(headers),
        "body": openai_input.model_dump() if hasattr(openai_input, "model_dump") else openai_input,
    }
    output_data = {
        "body": anthropic_output.model_dump() if hasattr(anthropic_output, "model_dump") else anthropic_output,
    }

    asyncio.create_task(_write_file_async(log_dir / "input", _serialize(input_data)))
    asyncio.create_task(_write_file_async(log_dir / "output", _serialize(output_data)))


# ============================================================================
# 中间件 1: Anthropic → Kiro (anthropic_kiro)
# ============================================================================


async def log_middleware_1(
    request_id: str,
    anthropic_input: Any,
    kiro_output: Any,
    headers: Any = None,
) -> None:
    """记录 Anthropic → Kiro 转换

    Args:
        request_id: 请求 ID
        anthropic_input: Anthropic 格式请求
        kiro_output: 转换后的 Kiro 格式请求
        headers: 请求头
    """
    settings = get_settings()
    if not settings.DEBUG_LOG_MIDDLEWARE_1:
        return

    ts = datetime.now()
    log_dir = _build_log_dir("anthropic_kiro", request_id, ts)

    logger.debug(
        "[M1][{rid}] Anthropic → Kiro | input: {inp} | output: {out}",
        rid=request_id,
        inp=_truncate_for_console(anthropic_input, 300),
        out=_truncate_for_console(kiro_output, 300),
    )

    input_data = {
        "headers": _headers_to_dict(headers),
        "body": anthropic_input.model_dump() if hasattr(anthropic_input, "model_dump") else anthropic_input,
    }
    output_data = {
        "body": kiro_output if isinstance(kiro_output, dict) else kiro_output,
    }

    asyncio.create_task(_write_file_async(log_dir / "input", _serialize(input_data)))
    asyncio.create_task(_write_file_async(log_dir / "output", _serialize(output_data)))


# ============================================================================
# 中间件 2: Kiro 返回 → Anthropic (kiro_anthropic)
# ============================================================================


async def log_middleware_2(
    request_id: str,
    kiro_response_raw: Any,
    anthropic_output: Any,
) -> None:
    """记录 Kiro 返回 → Anthropic 转换

    Args:
        request_id: 请求 ID
        kiro_response_raw: Kiro 返回的原始数据
        anthropic_output: 转换后的 Anthropic 格式数据
    """
    settings = get_settings()
    if not settings.DEBUG_LOG_MIDDLEWARE_2:
        return

    ts = datetime.now()
    log_dir = _build_log_dir("kiro_anthropic", request_id, ts)

    logger.debug(
        "[M2][{rid}] Kiro → Anthropic | kiro_raw: {raw} | anthropic: {out}",
        rid=request_id,
        raw=_truncate_for_console(kiro_response_raw, 300),
        out=_truncate_for_console(anthropic_output, 300),
    )

    asyncio.create_task(_write_file_async(log_dir / "input", _serialize(kiro_response_raw)))
    asyncio.create_task(_write_file_async(log_dir / "output", _serialize(anthropic_output)))


# ============================================================================
# Kiro API 原始请求/响应记录
# ============================================================================


async def log_kiro_raw_request(
    request_id: str,
    request_body: str,
    url: str,
) -> None:
    """记录发送给 Kiro API 的原始请求"""
    settings = get_settings()
    if not settings.DEBUG_LOG_MIDDLEWARE_1 and not settings.DEBUG_LOG_MIDDLEWARE_2:
        return

    ts = datetime.now()
    log_dir = _build_log_dir("anthropic_kiro", request_id, ts)

    logger.debug(
        "[KIRO-REQ][{rid}] url={url} body_len={blen}",
        rid=request_id,
        url=url,
        blen=len(request_body),
    )

    asyncio.create_task(_write_file_async(
        log_dir / "kiro_request",
        _serialize({"url": url, "body": request_body}),
    ))


async def log_kiro_raw_response_chunk(
    request_id: str,
    chunk_index: int,
    event_type: str,
    event_data: Any,
) -> None:
    """记录 Kiro API 返回的原始事件块

    对流式响应逐事件记录。
    """
    settings = get_settings()
    if not settings.DEBUG_LOG_MIDDLEWARE_2:
        return

    ts = datetime.now()
    log_dir = _build_log_dir("kiro_anthropic", request_id, ts)

    asyncio.create_task(_write_file_async(
        log_dir / f"kiro_event_{chunk_index:04d}_{event_type}",
        _serialize(event_data),
    ))
