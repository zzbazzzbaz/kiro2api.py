"""
POST /v1/messages/count_tokens — Token 估算端点
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import verify_api_key
from app.schemas.anthropic import CountTokensRequest
from app.services.stream import estimate_tokens

router = APIRouter()


@router.post("/messages/count_tokens")
async def count_tokens(
    request: Request,
    payload: CountTokensRequest,
    _api_key=Depends(verify_api_key),
):
    """估算输入 Token 数

    如果配置了外部 count_tokens API，优先调用外部服务；
    否则使用本地估算。
    """
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
                    total += estimate_tokens(
                        block.get("text", "") or block.get("thinking", "")
                    )

    # 工具
    if payload.tools:
        total += len(payload.tools) * 50

    return {"input_tokens": max(total, 1)}
