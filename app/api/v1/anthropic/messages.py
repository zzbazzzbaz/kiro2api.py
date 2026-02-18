"""
POST /v1/messages — 流式 + 非流式消息处理
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.dependencies import verify_api_key
from app.schemas.anthropic import MessagesRequest
from app.schemas.error import ErrorResponse
from app.services.converter import convert_request, map_model
from app.services.stream import (
    EventStreamDecoder, StreamContext, SseEvent,
    create_ping_sse, parse_kiro_event, estimate_tokens,
    PING_INTERVAL_SECS,
)
from app.services.websearch import has_web_search_tool, extract_search_query, create_mcp_request, parse_search_results, generate_websearch_events

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/messages")
async def post_messages(
    request: Request,
    payload: MessagesRequest,
    _api_key=Depends(verify_api_key),
):
    """创建消息（对话）

    支持流式和非流式输出
    """
    logger.info(
        "POST /v1/messages model=%s max_tokens=%d stream=%s messages=%d",
        payload.model, payload.max_tokens, payload.stream, len(payload.messages),
    )

    # 获取 KiroProvider（从 app.state 注入）
    provider = getattr(request.app.state, "kiro_provider", None)
    if not provider:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse.api_error("Kiro API provider 未配置").model_dump(),
        )

    # 检测 WebSearch 请求
    if has_web_search_tool(payload):
        logger.info("检测到 WebSearch 工具，路由到 WebSearch 处理")
        return await _handle_websearch(request, provider, payload)

    # 转换请求
    try:
        kiro_request = convert_request(payload)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.invalid_request_error(str(e)).model_dump(),
        )

    request_body = json.dumps(kiro_request, ensure_ascii=False)

    # 确定 thinking 配置
    thinking_enabled = payload.thinking is not None and payload.thinking.is_enabled()

    # 估算 input_tokens
    input_tokens = _estimate_input_tokens(payload)

    if payload.stream:
        return await _handle_stream(provider, request_body, payload.model, input_tokens, thinking_enabled)
    else:
        return await _handle_non_stream(provider, request_body, payload.model, input_tokens, thinking_enabled)


async def _handle_websearch(request: Request, provider, payload: MessagesRequest):
    """处理 WebSearch 请求"""
    query = extract_search_query(payload)
    if not query:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.invalid_request_error("无法从消息中提取搜索查询").model_dump(),
        )

    tool_use_id, mcp_request = create_mcp_request(query)
    mcp_body = json.dumps(mcp_request, ensure_ascii=False)

    # 调用 MCP API
    search_results = None
    try:
        response = await provider.call_mcp(mcp_body)
        mcp_data = response.json()
        search_results = parse_search_results(mcp_data)
    except Exception as e:
        logger.warning("MCP API 调用失败: %s", e)

    input_tokens = _estimate_input_tokens(payload)
    events = generate_websearch_events(payload.model, query, tool_use_id, search_results, input_tokens)

    async def event_generator():
        for ev in events:
            yield ev.to_sse_string()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _handle_stream(provider, request_body: str, model: str, input_tokens: int, thinking_enabled: bool):
    """处理流式请求"""
    try:
        response = await provider.call_api_stream(request_body)
    except ValueError as e:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse.api_error(f"上游 API 调用失败: {e}").model_dump(),
        )

    mapped_model = map_model(model) or model
    ctx = StreamContext(mapped_model, input_tokens, thinking_enabled)

    async def sse_generator() -> AsyncGenerator[str, None]:
        # 发送初始事件
        for ev in ctx.generate_initial_events():
            yield ev.to_sse_string()

        decoder = EventStreamDecoder()
        try:
            async for chunk in response.aiter_bytes():
                decoder.feed(chunk)
                for frame in decoder.decode_all():
                    event = parse_kiro_event(frame)
                    for sse_ev in ctx.process_kiro_event(event):
                        yield sse_ev.to_sse_string()
        except Exception as e:
            logger.error("处理流式响应失败: %s", e)
        finally:
            # 发送最终事件
            for ev in ctx.generate_final_events():
                yield ev.to_sse_string()

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _handle_non_stream(provider, request_body: str, model: str, input_tokens: int, thinking_enabled: bool):
    """处理非流式请求 — 内部仍使用流式调用，收集完成后返回完整响应"""
    try:
        response = await provider.call_api_stream(request_body)
    except ValueError as e:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse.api_error(f"上游 API 调用失败: {e}").model_dump(),
        )

    mapped_model = map_model(model) or model
    ctx = StreamContext(mapped_model, input_tokens, thinking_enabled)
    ctx.generate_initial_events()  # 初始化状态

    decoder = EventStreamDecoder()
    try:
        async for chunk in response.aiter_bytes():
            decoder.feed(chunk)
            for frame in decoder.decode_all():
                event = parse_kiro_event(frame)
                ctx.process_kiro_event(event)
    except Exception as e:
        logger.error("处理非流式响应失败: %s", e)

    ctx.generate_final_events()  # 完成状态

    # 构建非流式响应
    final_input = ctx.context_input_tokens if ctx.context_input_tokens is not None else input_tokens
    content_blocks = []

    for idx, block in sorted(ctx._active_blocks.items()):
        if block["type"] == "text":
            content_blocks.append({"type": "text", "text": ""})
        elif block["type"] == "thinking":
            content_blocks.append({"type": "thinking", "thinking": ""})

    return JSONResponse(content={
        "id": ctx.message_id,
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": mapped_model,
        "stop_reason": ctx._get_stop_reason(),
        "stop_sequence": None,
        "usage": {
            "input_tokens": final_input,
            "output_tokens": ctx.output_tokens,
        },
    })


def _estimate_input_tokens(payload: MessagesRequest) -> int:
    """简单估算输入 Token 数"""
    total = 0
    # 系统消息
    if payload.system:
        for s in payload.system:
            text = getattr(s, "text", str(s)) if not isinstance(s, str) else s
            total += estimate_tokens(text)
    # 消息
    for msg in payload.messages:
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += estimate_tokens(block.get("text", "") or block.get("thinking", ""))
    # 工具
    if payload.tools:
        total += len(payload.tools) * 50
    return max(total, 1)
