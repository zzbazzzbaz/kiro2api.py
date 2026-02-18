"""
Loguru 结构化日志配置

替换 stdlib logging，提供：
- 结构化控制台输出（带颜色、时间、模块信息）
- 拦截 stdlib logging → loguru
- uvicorn 日志统一
- 静默 aiosqlite/sqlalchemy 等低层 DEBUG 噪音
"""

import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """拦截 stdlib logging，转发到 loguru

    使用 record.name 作为日志来源名称，避免显示 logging:callHandlers 内部帧。
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 使用 logger.bind 将真实模块名注入，避免帧解析到 logging 内部
        logger.bind(name=record.name).opt(exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """初始化 loguru 结构化日志

    - 移除默认 handler
    - 添加带颜色的控制台结构化输出
    - 拦截 stdlib logging（INFO 及以上）
    - 静默 aiosqlite/sqlalchemy 等 DEBUG 噪音
    """
    # 移除 loguru 默认 handler
    logger.remove()

    # 添加结构化控制台输出
    logger.add(
        sys.stderr,
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[name]}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["extra"].setdefault("name", record["name"]) or True,
    )

    # 拦截 stdlib logging（INFO 级别，过滤掉底层 DEBUG 噪音）
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    # 拦截 uvicorn 日志
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        target_logger = logging.getLogger(name)
        target_logger.handlers = [InterceptHandler()]
        target_logger.propagate = False

    # 静默低层库的 DEBUG 日志
    for noisy in ("aiosqlite", "sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
