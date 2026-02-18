"""
OpenAI API 路由注册

/v1/chat/completions
"""

from fastapi import APIRouter

from app.api.v1.openai.chat_completions import router as chat_router

router = APIRouter()

# POST /v1/chat/completions
router.include_router(chat_router, prefix="/v1")
