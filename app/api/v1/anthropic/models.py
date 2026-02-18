"""
GET /v1/models — 模型列表端点
"""

import time

from fastapi import APIRouter

router = APIRouter()

# 支持的模型列表
SUPPORTED_MODELS = [
    {"id": "claude-sonnet-4-5", "display_name": "Claude Sonnet 4.5", "max_tokens": 8192},
    {"id": "claude-opus-4-5", "display_name": "Claude Opus 4.5", "max_tokens": 8192},
    {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "max_tokens": 8192},
    {"id": "claude-opus-4-6", "display_name": "Claude Opus 4.6", "max_tokens": 8192},
    {"id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "max_tokens": 8192},
]


@router.get("/models")
async def list_models():
    """返回支持的模型列表"""
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": now,
                "owned_by": "anthropic",
                "display_name": m["display_name"],
                "type": "model",
                "max_tokens": m["max_tokens"],
            }
            for m in SUPPORTED_MODELS
        ],
    }
