"""
POST /v1/messages — 流式 + 非流式消息处理
"""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from app.api.dependencies import verify_api_key
from app.schemas.anthropic import MessagesRequest
from app.schemas.error import ErrorResponse
from app.services.converter import convert_request, map_model
from app.services.debug_logger import (
    generate_request_id, log_middleware_1, log_middleware_2,
    log_kiro_raw_request, log_kiro_raw_response_chunk,
)
from app.services.usage_logger import schedule_log_usage
from app.services.stream import (
    EventStreamDecoder, StreamContext, SseEvent,
    create_ping_sse, parse_kiro_event, estimate_tokens,
    PING_INTERVAL_SECS,
)
from app.services.websearch import has_web_search_tool, extract_search_query, create_mcp_request, parse_search_results, generate_websearch_events

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
        "POST /v1/messages model={} max_tokens={} stream={} messages={}",
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

    # 生成请求 ID
    request_id = generate_request_id()

    # 转换请求
    try:
        kiro_request = convert_request(payload)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.invalid_request_error(str(e)).model_dump(),
        )

    request_body = json.dumps(kiro_request, ensure_ascii=False)

    # [中间件 1] Anthropic → Kiro
    await log_middleware_1(request_id, payload, kiro_request, headers=request.headers)

    # 确定 thinking 配置
    thinking_enabled = payload.thinking is not None and payload.thinking.is_enabled()

    # 估算 input_tokens
    input_tokens = _estimate_input_tokens(payload)

    api_key_id = getattr(request.state, "api_key_id", None)
    client_ip = request.client.host if request.client else None
    token_manager = getattr(request.app.state, "token_manager", None)

    if payload.stream:
        return await _handle_stream(provider, request_body, payload.model, input_tokens, thinking_enabled, request_id, api_key_id, client_ip, token_manager)
    else:
        return await _handle_non_stream(provider, request_body, payload.model, input_tokens, thinking_enabled, request_id, api_key_id, client_ip, token_manager)


async def _handle_websearch(request: Request, provider, payload: MessagesRequest):
    """处理 WebSearch 请求"""
    query = extract_search_query(payload)
    logger.debug("WebSearch 提取到查询: {}", query)
    if not query:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.invalid_request_error("无法从消息中提取搜索查询").model_dump(),
        )

    tool_use_id, mcp_request = create_mcp_request(query)
    mcp_body = json.dumps(mcp_request, ensure_ascii=False)
    logger.debug("WebSearch MCP 请求: tool_use_id={} body={}", tool_use_id, mcp_body)

    # 调用 MCP API
    search_results = None
    try:
        response = await provider.call_mcp(mcp_body)
        logger.debug("WebSearch MCP 响应状态: {}", response.status_code)
        mcp_data = response.json()
        logger.debug("WebSearch MCP 响应体: {}", json.dumps(mcp_data, ensure_ascii=False)[:2000])
        search_results = parse_search_results(mcp_data)
        result_count = len(search_results.get("results", [])) if search_results else 0
        logger.debug("WebSearch 解析结果: {} 条", result_count)
    except Exception as e:
        logger.warning("MCP API 调用失败: {}", e)

    input_tokens = _estimate_input_tokens(payload)
    events = generate_websearch_events(payload.model, query, tool_use_id, search_results, input_tokens)
    logger.debug("WebSearch 生成 {} 个 SSE 事件", len(events))

    async def event_generator():
        for ev in events:
            yield ev.to_sse_string()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _handle_stream(provider, request_body: str, model: str, input_tokens: int, thinking_enabled: bool, request_id: str = "", api_key_id=None, client_ip=None, token_manager=None):
    """处理流式请求"""
    # [Kiro 原始请求记录]
    await log_kiro_raw_request(request_id, request_body, "generateAssistantResponse")

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
        chunk_index = 0
        kiro_events_raw = []
        anthropic_events_raw = []
        try:
            async for chunk in response.aiter_bytes():
                decoder.feed(chunk)
                for frame in decoder.decode_all():
                    event = parse_kiro_event(frame)
                    # [Kiro 原始事件记录]
                    kiro_events_raw.append({"type": event.type, "index": chunk_index})
                    await log_kiro_raw_response_chunk(request_id, chunk_index, event.type, {
                        "type": event.type,
                        "content": event.assistant_response.content if event.assistant_response else None,
                        "tool_use": {"name": event.tool_use.name, "input": event.tool_use.input, "stop": event.tool_use.stop} if event.tool_use else None,
                        "context_usage": event.context_usage.context_usage_percentage if event.context_usage else None,
                        "error": event.error_message,
                        "exception": event.exception_message,
                    })
                    chunk_index += 1
                    for sse_ev in ctx.process_kiro_event(event):
                        anthropic_events_raw.append({"event": sse_ev.event, "data": sse_ev.data})
                        yield sse_ev.to_sse_string()
        except Exception as e:
            logger.error("处理流式响应失败: {}", e)
        finally:
            # 发送最终事件
            for ev in ctx.generate_final_events():
                anthropic_events_raw.append({"event": ev.event, "data": ev.data})
                yield ev.to_sse_string()

            # [中间件 2] Kiro 返回 → Anthropic
            await log_middleware_2(request_id, kiro_events_raw, anthropic_events_raw)

            # [使用日志]
            final_input = ctx.context_input_tokens if ctx.context_input_tokens is not None else input_tokens
            cred_id = token_manager.current_credential_id if token_manager else None
            schedule_log_usage(
                api_key_id=api_key_id, credential_id=cred_id,
                model=mapped_model, endpoint="/v1/messages",
                client_ip=client_ip,
                input_tokens=final_input, output_tokens=ctx.output_tokens,
            )

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _handle_non_stream(provider, request_body: str, model: str, input_tokens: int, thinking_enabled: bool, request_id: str = "", api_key_id=None, client_ip=None, token_manager=None):
    """处理非流式请求 — 内部仍使用流式调用，收集完成后返回完整响应"""
    # [Kiro 原始请求记录]
    await log_kiro_raw_request(request_id, request_body, "generateAssistantResponse")

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
    chunk_index = 0
    kiro_events_raw = []
    try:
        async for chunk in response.aiter_bytes():
            decoder.feed(chunk)
            for frame in decoder.decode_all():
                event = parse_kiro_event(frame)
                kiro_events_raw.append({"type": event.type, "index": chunk_index})
                await log_kiro_raw_response_chunk(request_id, chunk_index, event.type, {
                    "type": event.type,
                    "content": event.assistant_response.content if event.assistant_response else None,
                    "tool_use": {"name": event.tool_use.name, "input": event.tool_use.input, "stop": event.tool_use.stop} if event.tool_use else None,
                    "context_usage": event.context_usage.context_usage_percentage if event.context_usage else None,
                    "error": event.error_message,
                    "exception": event.exception_message,
                })
                chunk_index += 1
                ctx.process_kiro_event(event)
    except Exception as e:
        logger.error("处理非流式响应失败: {}", e)

    ctx.generate_final_events()  # 完成状态

    # 构建非流式响应
    final_input = ctx.context_input_tokens if ctx.context_input_tokens is not None else input_tokens
    content_blocks = []

    for idx, block in sorted(ctx._active_blocks.items()):
        if block["type"] == "text":
            content_blocks.append({"type": "text", "text": ""})
        elif block["type"] == "thinking":
            content_blocks.append({"type": "thinking", "thinking": ""})

    response_data = {
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
    }

    # [中间件 2] Kiro 返回 → Anthropic
    await log_middleware_2(request_id, kiro_events_raw, response_data)

    # [使用日志]
    cred_id = token_manager.current_credential_id if token_manager else None
    schedule_log_usage(
        api_key_id=api_key_id, credential_id=cred_id,
        model=mapped_model, endpoint="/v1/messages",
        client_ip=client_ip,
        input_tokens=final_input, output_tokens=ctx.output_tokens,
    )

    return JSONResponse(content=response_data)


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
