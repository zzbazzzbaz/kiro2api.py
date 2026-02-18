"""
WebSearch 工具处理模块

从 kiro.rs 移植，实现 Anthropic WebSearch 请求到 Kiro MCP 的转换和响应生成。
包含：
- WebSearch 工具检测
- MCP 请求构建（JSON-RPC 2.0）
- MCP 响应解析
- Anthropic 格式响应生成（tool_use + 搜索结果）
"""

import json
import logging
import random
import string
import time
import uuid
from typing import Any, Dict, List, Optional

from app.schemas.anthropic import MessagesRequest
from app.services.stream import SseEvent

logger = logging.getLogger(__name__)


# ============================================================================
# WebSearch 工具检测
# ============================================================================


def has_web_search_tool(req: MessagesRequest) -> bool:
    """检查请求是否为纯 WebSearch 请求

    条件：tools 有且只有一个，且 name 为 web_search
    """
    if not req.tools or len(req.tools) != 1:
        return False
    tool = req.tools[0]
    name = tool.name if hasattr(tool, "name") else (tool.get("name") if isinstance(tool, dict) else "")
    return name == "web_search"


def extract_search_query(req: MessagesRequest) -> Optional[str]:
    """从消息中提取搜索查询

    读取 messages 的第一条消息的第一个内容块，
    并去除 "Perform a web search for the query: " 前缀
    """
    if not req.messages:
        return None

    first_msg = req.messages[0]
    content = first_msg.content if hasattr(first_msg, "content") else (
        first_msg.get("content") if isinstance(first_msg, dict) else None
    )

    if content is None:
        return None

    # 提取文本
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list) and content:
        first_block = content[0]
        if isinstance(first_block, dict) and first_block.get("type") == "text":
            text = first_block.get("text", "")

    if not text:
        return None

    # 去除前缀
    prefix = "Perform a web search for the query: "
    if text.startswith(prefix):
        text = text[len(prefix):]

    return text if text else None


# ============================================================================
# MCP 请求构建
# ============================================================================


def _random_string(length: int, charset: str) -> str:
    """生成指定长度的随机字符串"""
    return "".join(random.choices(charset, k=length))


def create_mcp_request(query: str) -> tuple:
    """创建 MCP 请求

    Args:
        query: 搜索查询

    Returns:
        (tool_use_id, mcp_request_dict)
    """
    # ID 格式: web_search_tooluse_{22位随机}_{毫秒时间戳}_{8位随机}
    charset_22 = string.ascii_letters + string.digits
    charset_8 = string.ascii_lowercase + string.digits

    random_22 = _random_string(22, charset_22)
    timestamp = int(time.time() * 1000)
    random_8 = _random_string(8, charset_8)

    request_id = f"web_search_tooluse_{random_22}_{timestamp}_{random_8}"
    tool_use_id = f"srvtoolu_{uuid.uuid4().hex[:32]}"

    mcp_request = {
        "id": request_id,
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": {
                "query": query,
            },
        },
    }

    return (tool_use_id, mcp_request)


# ============================================================================
# MCP 响应解析
# ============================================================================


def parse_search_results(mcp_response: dict) -> Optional[dict]:
    """解析 MCP 响应中的搜索结果

    Args:
        mcp_response: MCP JSON 响应

    Returns:
        WebSearchResults dict 或 None
    """
    if not isinstance(mcp_response, dict):
        return None

    result = mcp_response.get("result")
    if not result:
        return None

    content = result.get("content")
    if not content or not isinstance(content, list) or not content:
        return None

    first_content = content[0]
    if first_content.get("type") != "text":
        return None

    try:
        return json.loads(first_content.get("text", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None


# ============================================================================
# Anthropic 格式响应生成
# ============================================================================


def _generate_search_summary(query: str, search_results: Optional[dict]) -> str:
    """生成搜索结果摘要"""
    summary = f'Here are the search results for "{query}":\n\n'

    if search_results and "results" in search_results:
        for i, result in enumerate(search_results["results"], 1):
            title = result.get("title", "")
            url = result.get("url", "")
            snippet = result.get("snippet", "")

            summary += f"{i}. **{title}**\n"
            if snippet:
                # 截断过长的摘要
                truncated = snippet[:200] + "..." if len(snippet) > 200 else snippet
                summary += f"   {truncated}\n"
            summary += f"   Source: {url}\n\n"
    else:
        summary += "No results found.\n"

    summary += "\nPlease note that these are web search results and may not be fully accurate or up-to-date."
    return summary


def generate_websearch_events(
    model: str,
    query: str,
    tool_use_id: str,
    search_results: Optional[dict],
    input_tokens: int,
) -> List[SseEvent]:
    """生成 WebSearch SSE 事件序列

    Args:
        model: 模型名称
        query: 搜索查询
        tool_use_id: 工具使用 ID
        search_results: 解析后的搜索结果
        input_tokens: 输入 Token 数

    Returns:
        SSE 事件列表
    """
    events: List[SseEvent] = []
    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    # 1. message_start
    events.append(SseEvent(
        event="message_start",
        data={
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        },
    ))

    # 2. content_block_start (server_tool_use)
    events.append(SseEvent(
        event="content_block_start",
        data={
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "id": tool_use_id,
                "type": "server_tool_use",
                "name": "web_search",
                "input": {},
            },
        },
    ))

    # 3. content_block_delta (input_json_delta)
    events.append(SseEvent(
        event="content_block_delta",
        data={
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "input_json_delta",
                "partial_json": json.dumps({"query": query}, ensure_ascii=False),
            },
        },
    ))

    # 4. content_block_stop (server_tool_use)
    events.append(SseEvent(
        event="content_block_stop",
        data={"type": "content_block_stop", "index": 0},
    ))

    # 5. content_block_start (web_search_tool_result)
    search_content = []
    if search_results and "results" in search_results:
        for r in search_results["results"]:
            search_content.append({
                "type": "web_search_result",
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "encrypted_content": r.get("snippet", ""),
                "page_age": None,
            })

    events.append(SseEvent(
        event="content_block_start",
        data={
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "web_search_tool_result",
                "tool_use_id": tool_use_id,
                "content": search_content,
            },
        },
    ))

    # 6. content_block_stop (web_search_tool_result)
    events.append(SseEvent(
        event="content_block_stop",
        data={"type": "content_block_stop", "index": 1},
    ))

    # 7. content_block_start (text)
    events.append(SseEvent(
        event="content_block_start",
        data={
            "type": "content_block_start",
            "index": 2,
            "content_block": {"type": "text", "text": ""},
        },
    ))

    # 8. content_block_delta (text_delta) — 搜索结果摘要
    summary = _generate_search_summary(query, search_results)
    chunk_size = 100
    for i in range(0, len(summary), chunk_size):
        chunk = summary[i:i + chunk_size]
        events.append(SseEvent(
            event="content_block_delta",
            data={
                "type": "content_block_delta",
                "index": 2,
                "delta": {"type": "text_delta", "text": chunk},
            },
        ))

    # 9. content_block_stop (text)
    events.append(SseEvent(
        event="content_block_stop",
        data={"type": "content_block_stop", "index": 2},
    ))

    # 10. message_delta
    output_tokens = max(1, (len(summary) + 3) // 4)
    events.append(SseEvent(
        event="message_delta",
        data={
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        },
    ))

    # 11. message_stop
    events.append(SseEvent(
        event="message_stop",
        data={"type": "message_stop"},
    ))

    return events
