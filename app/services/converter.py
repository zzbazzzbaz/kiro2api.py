"""
Anthropic → Kiro 协议转换器

从 kiro.rs 移植，负责将 Anthropic API 请求格式转换为 Kiro API 请求格式。
包含：
- 模型名称映射
- 消息转换（用户/助手/系统/工具/图片）
- 对话状态组装
- Write/Edit 工具描述后缀注入
- 系统分块策略注入
- thinking 配置自动覆盖
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.anthropic import MessagesRequest

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

# 追加到 Write 工具 description 末尾的内容
WRITE_TOOL_DESCRIPTION_SUFFIX = (
    "- IMPORTANT: If the content to write exceeds 150 lines, you MUST only write the "
    "first 50 lines using this tool, then use `Edit` tool to append the remaining content "
    "in chunks of no more than 50 lines each. If needed, leave a unique placeholder to "
    "help append content. Do NOT attempt to write all content at once."
)

# 追加到 Edit 工具 description 末尾的内容
EDIT_TOOL_DESCRIPTION_SUFFIX = (
    "- IMPORTANT: If the `new_string` content exceeds 50 lines, you MUST split it into "
    "multiple Edit calls, each replacing no more than 50 lines at a time. If used to "
    "append content, leave a unique placeholder to help append content. On the final "
    "chunk, do NOT include the placeholder."
)

# 追加到系统提示词的分块写入策略
SYSTEM_CHUNKED_POLICY = (
    "When the Write or Edit tool has content size limits, always comply silently. "
    "Never suggest bypassing these limits via alternative tools. "
    "Never ask the user whether to switch approaches. "
    "Complete all chunked operations without commentary."
)


# ============================================================================
# 模型映射
# ============================================================================


def map_model(model: str) -> Optional[str]:
    """将 Anthropic 模型名映射到 Kiro 模型 ID

    规则：
    - 所有 sonnet → claude-sonnet-4.5
    - 所有 opus (含 4.5/4-5) → claude-opus-4.5，否则 → claude-opus-4.6
    - 所有 haiku → claude-haiku-4.5

    Args:
        model: Anthropic 模型名称

    Returns:
        Kiro 模型 ID，不支持的模型返回 None
    """
    model_lower = model.lower()

    if "sonnet" in model_lower:
        return "claude-sonnet-4.5"
    elif "opus" in model_lower:
        if "4-5" in model_lower or "4.5" in model_lower:
            return "claude-opus-4.5"
        else:
            return "claude-opus-4.6"
    elif "haiku" in model_lower:
        return "claude-haiku-4.5"
    else:
        return None


# ============================================================================
# 从模型名称后缀自动覆盖 thinking 配置
# ============================================================================


def override_thinking_from_model_suffix(model: str, req: MessagesRequest) -> MessagesRequest:
    """如果模型名称以 -thinking 结尾，自动启用 thinking

    Args:
        model: 原始模型名称
        req: 请求对象

    Returns:
        可能修改后的请求对象
    """
    if model.lower().endswith("-thinking"):
        if req.thinking is None:
            from app.schemas.anthropic import Thinking
            req.thinking = Thinking(type="enabled", budget_tokens=20000)
    return req


# ============================================================================
# thinking 标签生成
# ============================================================================


def _generate_thinking_prefix(req: MessagesRequest) -> Optional[str]:
    """生成 thinking 标签前缀

    Args:
        req: Anthropic 请求

    Returns:
        thinking 标签字符串，或 None
    """
    if req.thinking is None:
        return None

    if req.thinking.type == "enabled":
        return (
            f"<thinking_mode>enabled</thinking_mode>"
            f"<max_thinking_length>{req.thinking.budget_tokens}</max_thinking_length>"
        )
    elif req.thinking.type == "adaptive":
        effort = "high"
        if req.thinking is not None and req.output_config is not None:
            effort = req.output_config.effort
        return (
            f"<thinking_mode>adaptive</thinking_mode>"
            f"<thinking_effort>{effort}</thinking_effort>"
        )

    return None


def _has_thinking_tags(content: str) -> bool:
    """检查内容是否已包含 thinking 标签"""
    return "<thinking_mode>" in content or "<max_thinking_length>" in content


# ============================================================================
# session ID 提取
# ============================================================================


def _extract_session_id(user_id: str) -> Optional[str]:
    """从 metadata.user_id 中提取 session UUID

    user_id 格式: user_xxx_account__session_0b4445e1-f5be-49e1-87ce-62bbc28ad705
    """
    pos = user_id.find("session_")
    if pos == -1:
        return None

    session_part = user_id[pos + 8:]
    if len(session_part) >= 36:
        uuid_str = session_part[:36]
        if uuid_str.count("-") == 4:
            return uuid_str

    return None


# ============================================================================
# 消息内容处理
# ============================================================================


def _get_image_format(media_type: str) -> Optional[str]:
    """从 media_type 获取图片格式"""
    formats = {
        "image/jpeg": "jpeg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    return formats.get(media_type)


def _extract_tool_result_content(content: Any) -> str:
    """提取工具结果内容"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return json.dumps(content, ensure_ascii=False) if content else ""


def _process_message_content(content: Any) -> Tuple[str, List[dict], List[dict]]:
    """处理消息内容，提取文本、图片和工具结果

    Args:
        content: 消息内容（字符串或内容块数组）

    Returns:
        (text, images, tool_results)
    """
    text_parts: List[str] = []
    images: List[dict] = []
    tool_results: List[dict] = []

    if isinstance(content, str):
        text_parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue

            block_type = item.get("type", "")

            if block_type == "text":
                text = item.get("text", "")
                if text:
                    text_parts.append(text)

            elif block_type == "image":
                source = item.get("source")
                if source:
                    fmt = _get_image_format(source.get("media_type", ""))
                    if fmt:
                        images.append({
                            "format": fmt,
                            "source": {"bytes": source.get("data", "")},
                        })

            elif block_type == "tool_result":
                tool_use_id = item.get("tool_use_id")
                if tool_use_id:
                    result_content = _extract_tool_result_content(item.get("content"))
                    is_error = item.get("is_error", False)

                    content_map = {"text": result_content}
                    tr = {
                        "toolUseId": tool_use_id,
                        "content": [content_map],
                        "status": "error" if is_error else "success",
                    }
                    if is_error:
                        tr["isError"] = True
                    tool_results.append(tr)

    return ("\n".join(text_parts), images, tool_results)


# ============================================================================
# 工具定义转换
# ============================================================================


def _convert_tools(tools: Optional[List[Any]]) -> List[dict]:
    """转换 Anthropic 工具定义为 Kiro 格式

    对 Write/Edit 工具追加分块策略描述后缀
    """
    if not tools:
        return []

    result = []
    for t in tools:
        if isinstance(t, dict):
            name = t.get("name", "")
            description = t.get("description", "")
            input_schema = t.get("input_schema", {})
        else:
            name = getattr(t, "name", "")
            description = getattr(t, "description", "")
            input_schema = getattr(t, "input_schema", {})

        # 对 Write/Edit 工具追加描述后缀
        if name == "Write":
            description = f"{description}\n{WRITE_TOOL_DESCRIPTION_SUFFIX}"
        elif name == "Edit":
            description = f"{description}\n{EDIT_TOOL_DESCRIPTION_SUFFIX}"

        # 限制描述长度为 10000 字符
        if len(description) > 10000:
            description = description[:10000]

        result.append({
            "toolSpecification": {
                "name": name,
                "description": description,
                "inputSchema": {"json": input_schema if isinstance(input_schema, dict) else {}},
            }
        })

    return result


def _create_placeholder_tool(name: str) -> dict:
    """为历史中使用但不在 tools 列表中的工具创建占位符定义"""
    return {
        "toolSpecification": {
            "name": name,
            "description": "Tool used in conversation history",
            "inputSchema": {
                "json": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": True,
                }
            },
        }
    }


# ============================================================================
# 助手消息转换
# ============================================================================


def _convert_assistant_message(msg: dict) -> dict:
    """转换 Anthropic assistant 消息为 Kiro 格式"""
    content = msg.get("content", "")
    thinking_content = ""
    text_content = ""
    tool_uses: List[dict] = []

    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            block_type = item.get("type", "")

            if block_type == "thinking":
                thinking = item.get("thinking", "")
                if thinking:
                    thinking_content += thinking

            elif block_type == "text":
                text = item.get("text", "")
                if text:
                    text_content += text

            elif block_type == "tool_use":
                tool_id = item.get("id")
                name = item.get("name")
                if tool_id and name:
                    tool_uses.append({
                        "toolUseId": tool_id,
                        "name": name,
                        "input": item.get("input", {}),
                    })

    # 组合 thinking 和 text 内容
    if thinking_content:
        if text_content:
            final_content = f"<thinking>{thinking_content}</thinking>\n\n{text_content}"
        else:
            final_content = f"<thinking>{thinking_content}</thinking>"
    elif not text_content and tool_uses:
        final_content = " "  # Kiro API 要求 content 不能为空
    else:
        final_content = text_content

    result: dict = {
        "assistantResponseMessage": {
            "content": final_content,
        }
    }
    if tool_uses:
        result["assistantResponseMessage"]["toolUses"] = tool_uses

    return result


# ============================================================================
# 用户消息合并
# ============================================================================


def _merge_user_messages(messages: List[dict], model_id: str) -> dict:
    """合并多个 user 消息为一个 Kiro 用户消息"""
    content_parts: List[str] = []
    all_images: List[dict] = []
    all_tool_results: List[dict] = []

    for msg in messages:
        text, images, tool_results = _process_message_content(msg.get("content", ""))
        if text:
            content_parts.append(text)
        all_images.extend(images)
        all_tool_results.extend(tool_results)

    content = "\n".join(content_parts)

    user_msg: dict = {
        "content": content,
        "modelId": model_id,
        "origin": "AI_EDITOR",
        "userInputMessageContext": {},
    }

    if all_images:
        user_msg["images"] = all_images

    if all_tool_results:
        user_msg["userInputMessageContext"]["toolResults"] = all_tool_results

    return {"userInputMessage": user_msg}


# ============================================================================
# tool_use / tool_result 配对验证
# ============================================================================


def _collect_history_tool_names(history: List[dict]) -> List[str]:
    """收集历史消息中使用的所有工具名称"""
    tool_names: List[str] = []
    for msg in history:
        assistant_msg = msg.get("assistantResponseMessage")
        if assistant_msg:
            for tu in assistant_msg.get("toolUses", []):
                name = tu.get("name", "")
                if name and name not in tool_names:
                    tool_names.append(name)
    return tool_names


def _validate_tool_pairing(
    history: List[dict], tool_results: List[dict]
) -> Tuple[List[dict], Set[str]]:
    """验证并过滤 tool_use/tool_result 配对

    Returns:
        (过滤后的 tool_results, 孤立的 tool_use_id 集合)
    """
    # 收集所有历史中的 tool_use_id
    all_tool_use_ids: Set[str] = set()
    # 收集历史中已有 tool_result 的 tool_use_id
    history_tool_result_ids: Set[str] = set()

    for msg in history:
        # assistant 消息中的 tool_uses
        assistant_msg = msg.get("assistantResponseMessage")
        if assistant_msg:
            for tu in assistant_msg.get("toolUses", []):
                all_tool_use_ids.add(tu.get("toolUseId", ""))

        # user 消息中的 tool_results
        user_msg = msg.get("userInputMessage")
        if user_msg:
            ctx = user_msg.get("userInputMessageContext", {})
            for tr in ctx.get("toolResults", []):
                history_tool_result_ids.add(tr.get("toolUseId", ""))

    # 计算未配对的 tool_use_ids
    unpaired_tool_use_ids = all_tool_use_ids - history_tool_result_ids

    # 过滤当前消息的 tool_results
    filtered_results: List[dict] = []
    for result in tool_results:
        tid = result.get("toolUseId", "")
        if tid in unpaired_tool_use_ids:
            filtered_results.append(result)
            unpaired_tool_use_ids.discard(tid)
        elif tid in all_tool_use_ids:
            logger.warning("跳过重复的 tool_result：tool_use_id=%s", tid)
        else:
            logger.warning("跳过孤立的 tool_result：找不到对应的 tool_use，tool_use_id=%s", tid)

    for orphaned_id in unpaired_tool_use_ids:
        logger.warning("检测到孤立的 tool_use：将从历史中移除，tool_use_id=%s", orphaned_id)

    return filtered_results, unpaired_tool_use_ids


def _remove_orphaned_tool_uses(history: List[dict], orphaned_ids: Set[str]) -> None:
    """从历史消息中移除孤立的 tool_use"""
    if not orphaned_ids:
        return

    for msg in history:
        assistant_msg = msg.get("assistantResponseMessage")
        if assistant_msg and "toolUses" in assistant_msg:
            original = assistant_msg["toolUses"]
            filtered = [tu for tu in original if tu.get("toolUseId", "") not in orphaned_ids]
            if not filtered:
                del assistant_msg["toolUses"]
            else:
                assistant_msg["toolUses"] = filtered


# ============================================================================
# 构建历史消息
# ============================================================================


def _build_history(req: MessagesRequest, model_id: str) -> List[dict]:
    """构建 Kiro 格式的历史消息列表"""
    history: List[dict] = []

    # 生成 thinking 前缀
    thinking_prefix = _generate_thinking_prefix(req)

    # 1. 处理系统消息
    if req.system:
        system_parts = []
        for s in req.system:
            if isinstance(s, str):
                system_parts.append(s)
            else:
                system_parts.append(getattr(s, "text", str(s)))
        system_content = "\n".join(system_parts)

        if system_content:
            # 追加分块写入策略
            system_content = f"{system_content}\n{SYSTEM_CHUNKED_POLICY}"

            # 注入 thinking 标签
            if thinking_prefix and not _has_thinking_tags(system_content):
                system_content = f"{thinking_prefix}\n{system_content}"

            # 系统消息作为 user + assistant 配对
            history.append({
                "userInputMessage": {
                    "content": system_content,
                    "modelId": model_id,
                    "origin": "AI_EDITOR",
                    "userInputMessageContext": {},
                }
            })
            history.append({
                "assistantResponseMessage": {
                    "content": "I will follow these instructions.",
                }
            })
    elif thinking_prefix:
        # 没有系统消息但有 thinking 配置
        history.append({
            "userInputMessage": {
                "content": thinking_prefix,
                "modelId": model_id,
                "origin": "AI_EDITOR",
                "userInputMessageContext": {},
            }
        })
        history.append({
            "assistantResponseMessage": {
                "content": "I will follow these instructions.",
            }
        })

    # 2. 处理常规消息历史
    messages = req.messages
    if not messages:
        return history

    # 序列化消息为 dict
    raw_messages = []
    for m in messages:
        if isinstance(m, dict):
            raw_messages.append(m)
        else:
            raw_messages.append(m.model_dump() if hasattr(m, "model_dump") else {"role": m.role, "content": m.content})

    # 最后一条消息作为 currentMessage，不加入历史
    # 如果最后一条是 assistant，则包含在历史中
    last_is_assistant = raw_messages[-1].get("role") == "assistant" if raw_messages else False
    history_end = len(raw_messages) if last_is_assistant else len(raw_messages) - 1

    # 收集并配对消息
    user_buffer: List[dict] = []

    for i in range(history_end):
        msg = raw_messages[i]
        role = msg.get("role", "")

        if role == "user":
            user_buffer.append(msg)
        elif role == "assistant":
            if user_buffer:
                merged = _merge_user_messages(user_buffer, model_id)
                history.append(merged)
                user_buffer.clear()

                assistant = _convert_assistant_message(msg)
                history.append(assistant)

    # 处理结尾的孤立 user 消息
    if user_buffer:
        merged = _merge_user_messages(user_buffer, model_id)
        history.append(merged)
        history.append({
            "assistantResponseMessage": {"content": "OK"}
        })

    return history


# ============================================================================
# 主转换函数
# ============================================================================


def convert_request(req: MessagesRequest) -> dict:
    """将 Anthropic 请求转换为 Kiro 请求

    Args:
        req: Anthropic MessagesRequest

    Returns:
        Kiro API 请求体 dict（包含 conversationState）

    Raises:
        ValueError: 模型不支持或消息列表为空
    """
    # 0. 从模型名称后缀自动覆盖 thinking 配置
    req = override_thinking_from_model_suffix(req.model, req)

    # 1. 映射模型
    model_id = map_model(req.model)
    if not model_id:
        raise ValueError(f"模型不支持: {req.model}")

    # 2. 检查消息列表
    if not req.messages:
        raise ValueError("消息列表为空")

    # 3. 生成会话 ID
    conversation_id = None
    if req.metadata and req.metadata.user_id:
        conversation_id = _extract_session_id(req.metadata.user_id)
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    agent_continuation_id = str(uuid.uuid4())

    # 4. 处理最后一条消息作为 current_message
    last_msg = req.messages[-1]
    if isinstance(last_msg, dict):
        last_content = last_msg.get("content", "")
    else:
        last_content = last_msg.content

    text_content, images, tool_results = _process_message_content(last_content)

    # 5. 转换工具定义
    tools_raw = None
    if req.tools:
        tools_raw = [t.model_dump() if hasattr(t, "model_dump") else t for t in req.tools]
    tools = _convert_tools(tools_raw)

    # 6. 构建历史消息
    history = _build_history(req, model_id)

    # 7. 验证 tool_use/tool_result 配对
    validated_tool_results, orphaned_ids = _validate_tool_pairing(history, tool_results)

    # 8. 移除孤立的 tool_use
    _remove_orphaned_tool_uses(history, orphaned_ids)

    # 9. 收集历史中使用的工具名称，为缺失的工具生成占位符
    history_tool_names = _collect_history_tool_names(history)
    existing_tool_names = {
        t.get("toolSpecification", {}).get("name", "").lower()
        for t in tools
    }
    for tool_name in history_tool_names:
        if tool_name.lower() not in existing_tool_names:
            tools.append(_create_placeholder_tool(tool_name))

    # 10. 构建 UserInputMessageContext
    context: dict = {}
    if tools:
        context["tools"] = tools
    if validated_tool_results:
        context["toolResults"] = validated_tool_results

    # 11. 构建当前消息
    user_input_message: dict = {
        "userInputMessageContext": context,
        "content": text_content,
        "modelId": model_id,
        "origin": "AI_EDITOR",
    }
    if images:
        user_input_message["images"] = images

    # 12. 构建 ConversationState
    conversation_state: dict = {
        "agentContinuationId": agent_continuation_id,
        "agentTaskType": "vibe",
        "chatTriggerType": "MANUAL",
        "currentMessage": {
            "userInputMessage": user_input_message,
        },
        "conversationId": conversation_id,
    }
    if history:
        conversation_state["history"] = history

    return {"conversationState": conversation_state}
