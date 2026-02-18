"""
POST /cc/v1/messages — 缓冲流式消息处理

缓冲所有事件直到流结束，用 contextUsageEvent 修正 input_tokens 后一次性发送
"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from app.api.dependencies import verify_api_key
from app.schemas.anthropic import MessagesRequest
from app.schemas.error import ErrorResponse
from app.services.converter import convert_request, map_model
from app.services.usage_logger import schedule_log_usage
from app.services.stream import (
    BufferedStreamContext, EventStreamDecoder, create_ping_sse,
    parse_kiro_event, PING_INTERVAL_SECS,
)
from app.api.v1.anthropic.messages import _estimate_input_tokens

router = APIRouter()


@router.post("/messages")
async def post_messages_cc(
    request: Request,
    payload: MessagesRequest,
    _api_key=Depends(verify_api_key),
):
    """缓冲流式消息处理

    等待上游流完成后一次性发送，期间发送 ping 保活
    """
    logger.info(
        "POST /cc/v1/messages model={} stream={}",
        payload.model, payload.stream,
    )

    provider = getattr(request.app.state, "kiro_provider", None)
    if not provider:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse.api_error("Kiro API provider 未配置").model_dump(),
        )

    try:
        kiro_request = convert_request(payload)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.invalid_request_error(str(e)).model_dump(),
        )

    request_body = json.dumps(kiro_request, ensure_ascii=False)
    thinking_enabled = payload.thinking is not None and payload.thinking.is_enabled()
    input_tokens = _estimate_input_tokens(payload)

    try:
        response = await provider.call_api_stream(request_body)
    except ValueError as e:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse.api_error(f"上游 API 调用失败: {e}").model_dump(),
        )

    mapped_model = map_model(payload.model) or payload.model
    ctx = BufferedStreamContext(mapped_model, input_tokens, thinking_enabled)

    # 读取所有上游数据
    decoder = EventStreamDecoder()
    try:
        async for chunk in response.aiter_bytes():
            decoder.feed(chunk)
            for frame in decoder.decode_all():
                event = parse_kiro_event(frame)
                ctx.process_and_buffer(event)
    except Exception as e:
        logger.error("读取缓冲流失败: {}", e)

    all_events = ctx.finish_and_get_all_events()

    # [使用日志]
    api_key_id = getattr(request.state, "api_key_id", None)
    client_ip = request.client.host if request.client else None
    token_manager = getattr(request.app.state, "token_manager", None)
    cred_id = token_manager.current_credential_id if token_manager else None
    final_input = ctx.context_input_tokens if ctx.context_input_tokens is not None else input_tokens
    schedule_log_usage(
        api_key_id=api_key_id, credential_id=cred_id,
        model=mapped_model, endpoint="/cc/v1/messages",
        client_ip=client_ip,
        input_tokens=final_input, output_tokens=ctx.output_tokens,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        for ev in all_events:
            yield ev.to_sse_string()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
