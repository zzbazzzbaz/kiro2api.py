#!/usr/bin/env python3
"""
启动脚本 - 从 .env 读取配置并启动 uvicorn
"""

import uvicorn
from app.core.config import get_settings
from app.core.logging import setup_logging

# 在 uvicorn 启动前初始化 loguru，确保 reloader 进程的日志也走 loguru
settings = get_settings()
setup_logging(settings.LOG_LEVEL)

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,  # 开发模式自动重载
        reload_excludes=["data/*", "*.db", "*.db-journal"],
        log_config=None,  # 禁用 uvicorn 默认日志配置，使用 loguru
    )
