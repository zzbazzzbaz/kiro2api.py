"""
应用配置模块

使用 pydantic-settings 从环境变量和 .env 文件加载配置
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ===== 服务配置 =====
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ===== 区域配置 =====
    REGION: str = "us-east-1"
    AUTH_REGION: Optional[str] = None
    API_REGION: Optional[str] = None

    # ===== Kiro 版本伪装 =====
    KIRO_VERSION: str = "0.9.2"
    SYSTEM_VERSION: str = "darwin#24.6.0"
    NODE_VERSION: str = "22.21.1"

    # ===== 数据库 =====
    DATABASE_URL: str = "sqlite+aiosqlite:///data/kiro2api.db"

    # ===== 安全 =====
    ADMIN_API_KEY: Optional[str] = None
    REQUIRE_API_KEY: bool = False

    # ===== 负载均衡 =====
    LOAD_BALANCING_MODE: str = "priority"

    # ===== 全局代理 =====
    PROXY_URL: Optional[str] = None
    PROXY_USERNAME: Optional[str] = None
    PROXY_PASSWORD: Optional[str] = None

    # ===== 外部 count_tokens API =====
    COUNT_TOKENS_API_URL: Optional[str] = None
    COUNT_TOKENS_API_KEY: Optional[str] = None
    COUNT_TOKENS_AUTH_TYPE: str = "x-api-key"

    # ===== 调试日志中间件 =====
    DEBUG_LOG_DIR: str = "data/debug-log"
    DEBUG_LOG_MIDDLEWARE_0: bool = False  # OpenAI → Anthropic
    DEBUG_LOG_MIDDLEWARE_1: bool = False  # Anthropic → Kiro
    DEBUG_LOG_MIDDLEWARE_2: bool = False  # Kiro 返回 → Anthropic

    @property
    def effective_auth_region(self) -> str:
        """获取有效的 Auth Region（用于 Token 刷新）
        优先级：AUTH_REGION > REGION
        """
        return self.AUTH_REGION or self.REGION

    @property
    def effective_api_region(self) -> str:
        """获取有效的 API Region（用于 API 请求）
        优先级：API_REGION > REGION
        """
        return self.API_REGION or self.REGION


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
