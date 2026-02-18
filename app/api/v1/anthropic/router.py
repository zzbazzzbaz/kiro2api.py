"""
Anthropic API 路由注册

/v1/messages、/v1/models、/v1/messages/count_tokens、/cc/v1/messages
"""

from fastapi import APIRouter

from app.api.v1.anthropic.messages import router as messages_router
from app.api.v1.anthropic.messages_cc import router as messages_cc_router
from app.api.v1.anthropic.models import router as models_router
from app.api.v1.anthropic.count_tokens import router as count_tokens_router

router = APIRouter()

# GET /v1/models
router.include_router(models_router, prefix="/v1")
# POST /v1/messages
router.include_router(messages_router, prefix="/v1")
# POST /v1/messages/count_tokens
router.include_router(count_tokens_router, prefix="/v1")
# POST /cc/v1/messages
router.include_router(messages_cc_router, prefix="/cc/v1")
