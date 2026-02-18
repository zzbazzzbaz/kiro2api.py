"""
Alembic 环境配置

支持异步 SQLAlchemy 引擎（aiosqlite）
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入所有模型，确保 autogenerate 能发现它们
from app.models.base import Base
from app.models.credential import Credential  # noqa: F401
from app.models.group import Group  # noqa: F401
from app.models.api_key import ApiKey  # noqa: F401
from app.models.usage_log import UsageLog  # noqa: F401

# Alembic 配置对象
config = context.config

# 配置 Python 日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置 autogenerate 的目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式迁移

    仅生成 SQL 脚本，不需要数据库连接
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """执行迁移（在连接上下文中）"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步在线模式迁移

    使用异步引擎连接数据库并执行迁移
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式迁移入口"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
