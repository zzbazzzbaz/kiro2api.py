"""
POST /v1/chat/completions — OpenAI 兼容端点

将 OpenAI 格式请求转换为 Anthropic 格式，调用上游后转换响应
"""

import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from app.api.dependencies import verify_api_key
from app.schemas.openai import ChatCompletionRequest
from app.schemas.anthropic import MessagesRequest
from app.schemas.error import ErrorResponse
from app.services.converter import convert_request, map_model
from app.services.debug_logger import (
    generate_request_id, log_middleware_0, log_middleware_1, log_middleware_2,
    log_kiro_raw_request, log_kiro_raw_response_chunk,
)
from app.services.usage_logger import schedule_log_usage
from app.services.stream import (
    EventStreamDecoder, StreamContext, parse_kiro_event, estimate_tokens,
)

router = APIRouter()


def _openai_to_anthropic(req: ChatCompletionRequest) -> MessagesRequest:
    """将 OpenAI 格式请求转换为 Anthropic 格式"""
    # 提取 system 消息
    system_parts = []
    messages = []

    for msg in req.messages:
        role = msg.role
        content = msg.content

        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            continue

        if role == "tool":
            # 转换为 tool_result
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": content or "",
                }],
            })
            continue

        if role == "assistant" and msg.tool_calls:
            # 助手消息含工具调用
            blocks = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in msg.tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": json.loads(func.get("arguments", "{}")) if isinstance(func.get("arguments"), str) else func.get("arguments", {}),
                    })
                else:
                    blocks.append({
                        "type": "tool_use",
                        "id": getattr(tc, "id", ""),
                        "name": getattr(getattr(tc, "function", None), "name", ""),
                        "input": json.loads(getattr(getattr(tc, "function", None), "arguments", "{}")) if isinstance(getattr(getattr(tc, "function", None), "arguments", None), str) else {},
                    })
            messages.append({"role": "assistant", "content": blocks})
            continue

        messages.append({"role": role, "content": content or ""})

    # 转换工具定义
    tools = None
    if req.tools:
        tools = []
        for t in req.tools:
            func = t.function if hasattr(t, "function") else t.get("function", {})
            tools.append({
                "name": getattr(func, "name", "") if hasattr(func, "name") else func.get("name", ""),
                "description": getattr(func, "description", "") if hasattr(func, "description") else func.get("description", ""),
                "input_schema": getattr(func, "parameters", {}) if hasattr(func, "parameters") else func.get("parameters", {}),
            })

    return MessagesRequest(
        model=req.model,
        max_tokens=req.max_tokens or 4096,
        messages=messages,
        stream=req.stream,
        system="\n".join(system_parts) if system_parts else None,
        tools=tools,
    )


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
    _api_key=Depends(verify_api_key),
):
    """OpenAI 兼容的 Chat Completions 端点"""
    logger.info(
        "POST /v1/chat/completions model={} stream={} messages={}",
        payload.model, payload.stream, len(payload.messages),
    )

    provider = getattr(request.app.state, "kiro_provider", None)
    if not provider:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "Kiro API provider 未配置", "type": "server_error"}},
        )

    # 生成请求 ID
    request_id = generate_request_id()

    # 转换为 Anthropic 格式
    anthropic_req = _openai_to_anthropic(payload)

    # [中间件 0] OpenAI → Anthropic
    await log_middleware_0(request_id, payload, anthropic_req, headers=request.headers)

    try:
        kiro_request = convert_request(anthropic_req)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": {"message": str(e), "type": "invalid_request_error"}})

    request_body = json.dumps(kiro_request, ensure_ascii=False)

    # [中间件 1] Anthropic → Kiro
    await log_middleware_1(request_id, anthropic_req, kiro_request, headers=request.headers)

    thinking_enabled = anthropic_req.thinking is not None and anthropic_req.thinking.is_enabled()
    input_tokens = max(1, sum(
        estimate_tokens(str(m.content or "")) for m in payload.messages
    ))
    mapped_model = map_model(payload.model) or payload.model

    api_key_id = getattr(request.state, "api_key_id", None)
    client_ip = request.client.host if request.client else None
    token_manager = getattr(request.app.state, "token_manager", None)

    if payload.stream:
        return await _handle_openai_stream(provider, request_body, payload.model, mapped_model, input_tokens, thinking_enabled, request_id, api_key_id, client_ip, token_manager)
    else:
        return await _handle_openai_non_stream(provider, request_body, payload.model, mapped_model, input_tokens, thinking_enabled, request_id, api_key_id, client_ip, token_manager)


async def _handle_openai_stream(provider, request_body, original_model, mapped_model, input_tokens, thinking_enabled, request_id: str = "", api_key_id=None, client_ip=None, token_manager=None):
    """OpenAI 流式响应"""
    # [Kiro 原始请求记录]
    await log_kiro_raw_request(request_id, request_body, "generateAssistantResponse")

    try:
        response = await provider.call_api_stream(request_body)
    except ValueError as e:
        return JSONResponse(status_code=502, content={"error": {"message": str(e)}})

    ctx = StreamContext(mapped_model, input_tokens, thinking_enabled)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    async def sse_generator() -> AsyncGenerator[str, None]:
        # 初始化
        ctx.generate_initial_events()

        # 发送初始 role chunk
        yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created, 'model': original_model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"

        decoder = EventStreamDecoder()
        chunk_index = 0
        kiro_events_raw = []
        anthropic_events_raw = []
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
                    for sse_ev in ctx.process_kiro_event(event):
                        anthropic_events_raw.append({"event": sse_ev.event, "data": sse_ev.data})
                        # 将 Anthropic SSE 转换为 OpenAI chunk
                        openai_chunk = _anthropic_sse_to_openai_chunk(
                            sse_ev, completion_id, created, original_model
                        )
                        if openai_chunk:
                            yield f"data: {json.dumps(openai_chunk)}\n\n"
        except Exception as e:
            logger.error("流式处理失败: {}", e)

        # 最终事件
        for sse_ev in ctx.generate_final_events():
            anthropic_events_raw.append({"event": sse_ev.event, "data": sse_ev.data})
            openai_chunk = _anthropic_sse_to_openai_chunk(sse_ev, completion_id, created, original_model)
            if openai_chunk:
                yield f"data: {json.dumps(openai_chunk)}\n\n"

        # [中间件 2] Kiro 返回 → Anthropic
        await log_middleware_2(request_id, kiro_events_raw, anthropic_events_raw)

        # [使用日志]
        final_input = ctx.context_input_tokens if ctx.context_input_tokens is not None else input_tokens
        cred_id = token_manager.current_credential_id if token_manager else None
        schedule_log_usage(
            api_key_id=api_key_id, credential_id=cred_id,
            model=mapped_model, endpoint="/v1/chat/completions",
            client_ip=client_ip,
            input_tokens=final_input, output_tokens=ctx.output_tokens,
        )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _handle_openai_non_stream(provider, request_body, original_model, mapped_model, input_tokens, thinking_enabled, request_id: str = "", api_key_id=None, client_ip=None, token_manager=None):
    """OpenAI 非流式响应"""
    # [Kiro 原始请求记录]
    await log_kiro_raw_request(request_id, request_body, "generateAssistantResponse")

    try:
        response = await provider.call_api_stream(request_body)
    except ValueError as e:
        return JSONResponse(status_code=502, content={"error": {"message": str(e)}})

    ctx = StreamContext(mapped_model, input_tokens, thinking_enabled)
    ctx.generate_initial_events()

    # 收集文本
    text_parts = []

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
                for sse_ev in ctx.process_kiro_event(event):
                    if sse_ev.event == "content_block_delta":
                        delta = sse_ev.data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text_parts.append(delta.get("text", ""))
    except Exception as e:
        logger.error("非流式处理失败: {}", e)

    ctx.generate_final_events()
    final_input = ctx.context_input_tokens if ctx.context_input_tokens is not None else input_tokens

    response_data = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": original_model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "".join(text_parts) or None,
            },
            "finish_reason": "stop" if not ctx._has_tool_use else "tool_calls",
        }],
        "usage": {
            "prompt_tokens": final_input,
            "completion_tokens": ctx.output_tokens,
            "total_tokens": final_input + ctx.output_tokens,
        },
    }

    # [中间件 2] Kiro 返回 → Anthropic
    await log_middleware_2(request_id, kiro_events_raw, response_data)

    # [使用日志]
    cred_id = token_manager.current_credential_id if token_manager else None
    schedule_log_usage(
        api_key_id=api_key_id, credential_id=cred_id,
        model=mapped_model, endpoint="/v1/chat/completions",
        client_ip=client_ip,
        input_tokens=final_input, output_tokens=ctx.output_tokens,
    )

    return JSONResponse(content=response_data)


def _anthropic_sse_to_openai_chunk(sse_ev, completion_id, created, model) -> Optional[dict]:
    """将 Anthropic SSE 事件转换为 OpenAI chunk"""
    if sse_ev.event == "content_block_delta":
        delta = sse_ev.data.get("delta", {})
        delta_type = delta.get("type", "")

        if delta_type == "text_delta":
            return {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": delta.get("text", "")},
                    "finish_reason": None,
                }],
            }

    elif sse_ev.event == "message_delta":
        stop_reason = sse_ev.data.get("delta", {}).get("stop_reason", "end_turn")
        finish = "stop" if stop_reason == "end_turn" else ("tool_calls" if stop_reason == "tool_use" else "stop")
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": finish,
            }],
        }

    return None
