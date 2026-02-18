"""
异步消费日志写入器

响应完成后通过 asyncio.create_task 异步写入日志，不阻塞响应返回。
同时实现 tokens_used 原子递增。
"""

import asyncio
from typing import Optional

from loguru import logger
from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.api_key import ApiKey
from app.models.usage_log import UsageLog


async def log_usage(
    api_key_id: Optional[int],
    credential_id: Optional[int],
    model: str,
    endpoint: str,
    client_ip: Optional[str],
    input_tokens: int,
    output_tokens: int,
    status_code: int = 200,
    error_message: Optional[str] = None,
    duration_ms: int = 0,
) -> None:
    """异步写入消费日志并递增 tokens_used

    此函数应通过 asyncio.create_task() 调用，不阻塞响应返回。
    """
    try:
        async with AsyncSessionLocal() as db:
            total_tokens = input_tokens + output_tokens

            # 写入日志
            log_entry = UsageLog(
                api_key_id=api_key_id,
                credential_id=credential_id,
                model=model,
                endpoint=endpoint,
                client_ip=client_ip,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                status_code=status_code,
                error_message=error_message,
                duration_ms=duration_ms,
            )
            db.add(log_entry)

            # 原子递增 tokens_used 和 request_count
            if api_key_id is not None:
                values = {ApiKey.request_count: ApiKey.request_count + 1}
                if total_tokens > 0:
                    values[ApiKey.tokens_used] = ApiKey.tokens_used + total_tokens
                await db.execute(
                    update(ApiKey)
                    .where(ApiKey.id == api_key_id)
                    .values(**values)
                )

            await db.commit()

    except Exception as e:
        logger.error("写入消费日志失败: {}", e)


def schedule_log_usage(
    api_key_id: Optional[int],
    credential_id: Optional[int],
    model: str,
    endpoint: str,
    client_ip: Optional[str],
    input_tokens: int,
    output_tokens: int,
    status_code: int = 200,
    error_message: Optional[str] = None,
    duration_ms: int = 0,
) -> None:
    """调度异步消费日志写入

    通过 asyncio.create_task() 在后台执行，不阻塞当前响应。
    """
    asyncio.create_task(
        log_usage(
            api_key_id=api_key_id,
            credential_id=credential_id,
            model=model,
            endpoint=endpoint,
            client_ip=client_ip,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status_code=status_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )
    )
