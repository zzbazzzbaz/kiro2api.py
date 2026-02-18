"""
Admin API 路由注册

/api/admin/credentials、/api/admin/api-keys、/api/admin/groups、/api/admin/config
"""

from fastapi import APIRouter

from app.api.v1.admin.credentials import router as credentials_router
from app.api.v1.admin.api_keys import router as api_keys_router
from app.api.v1.admin.groups import router as groups_router
from app.api.v1.admin.config import router as config_router

router = APIRouter(prefix="/api/admin")

router.include_router(credentials_router, prefix="/credentials", tags=["Admin - 凭据"])
router.include_router(api_keys_router, prefix="/api-keys", tags=["Admin - API Key"])
router.include_router(groups_router, prefix="/groups", tags=["Admin - 分组"])
router.include_router(config_router, prefix="/config", tags=["Admin - 配置"])
