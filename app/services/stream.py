"""
SSE 流式处理模块

从 kiro.rs 移植，负责：
- AWS Event Stream 帧解码
- Kiro 事件解析（AssistantResponse、ToolUse、ContextUsage、Exception 等）
- StreamContext — 实时 SSE 转换
- BufferedStreamContext — 缓冲模式（/cc/v1）
- thinking 标签检测（真实标签 vs. 引用标签）
- SSE 保活机制
"""

import json
import struct
import uuid
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# 上下文窗口大小（用于从百分比计算 input_tokens）
CONTEXT_WINDOW_SIZE: int = 200000

# Ping 间隔（秒）
PING_INTERVAL_SECS: int = 25


# ============================================================================
# AWS Event Stream 帧解码器
# ============================================================================

# Prelude 固定大小（12 字节）
PRELUDE_SIZE: int = 12
# 最小消息大小（Prelude + Message CRC）
MIN_MESSAGE_SIZE: int = 16
# 最大消息大小限制（16 MB）
MAX_MESSAGE_SIZE: int = 16 * 1024 * 1024


def _crc32(data: bytes) -> int:
    """计算 CRC32（与 AWS Event Stream 兼容）"""
    return zlib.crc32(data) & 0xFFFFFFFF


def _parse_headers(data: bytes) -> Dict[str, str]:
    """解析 AWS Event Stream 消息头部

    头部格式：
    - 1 字节：名称长度
    - N 字节：名称
    - 1 字节：类型（7 = string）
    - 2 字节：值长度
    - N 字节：值
    """
    headers: Dict[str, str] = {}
    offset = 0

    while offset < len(data):
        if offset >= len(data):
            break

        # 读取名称长度
        name_len = data[offset]
        offset += 1

        # 读取名称
        name = data[offset:offset + name_len].decode("utf-8")
        offset += name_len

        # 读取类型
        header_type = data[offset]
        offset += 1

        if header_type == 7:  # String 类型
            # 读取值长度（2 字节大端）
            value_len = struct.unpack(">H", data[offset:offset + 2])[0]
            offset += 2
            # 读取值
            value = data[offset:offset + value_len].decode("utf-8")
            offset += value_len
            headers[name] = value
        else:
            # 未知类型，跳过
            break

    return headers


@dataclass
class Frame:
    """解析后的 AWS Event Stream 消息帧"""
    headers: Dict[str, str]
    payload: bytes

    @property
    def message_type(self) -> Optional[str]:
        return self.headers.get(":message-type")

    @property
    def event_type(self) -> Optional[str]:
        return self.headers.get(":event-type")

    def payload_as_json(self) -> Any:
        """将 payload 解析为 JSON"""
        return json.loads(self.payload)

    def payload_as_str(self) -> str:
        """将 payload 解析为字符串"""
        return self.payload.decode("utf-8", errors="replace")


def parse_frame(buffer: bytes, offset: int = 0) -> Optional[Tuple[Frame, int]]:
    """尝试从缓冲区解析一个完整帧

    Args:
        buffer: 输入缓冲区
        offset: 起始偏移

    Returns:
        (Frame, consumed_bytes) 或 None（数据不足）

    Raises:
        ValueError: 解析错误
    """
    remaining = len(buffer) - offset
    if remaining < PRELUDE_SIZE:
        return None

    # 读取 prelude
    total_length = struct.unpack(">I", buffer[offset:offset + 4])[0]
    header_length = struct.unpack(">I", buffer[offset + 4:offset + 8])[0]
    prelude_crc = struct.unpack(">I", buffer[offset + 8:offset + 12])[0]

    # 验证消息长度
    if total_length < MIN_MESSAGE_SIZE:
        raise ValueError(f"消息太小: {total_length} < {MIN_MESSAGE_SIZE}")
    if total_length > MAX_MESSAGE_SIZE:
        raise ValueError(f"消息太大: {total_length} > {MAX_MESSAGE_SIZE}")

    # 检查数据是否完整
    if remaining < total_length:
        return None

    msg_data = buffer[offset:offset + total_length]

    # 验证 Prelude CRC
    actual_prelude_crc = _crc32(msg_data[:8])
    if actual_prelude_crc != prelude_crc:
        raise ValueError(f"Prelude CRC 不匹配: {actual_prelude_crc} != {prelude_crc}")

    # 验证 Message CRC
    message_crc = struct.unpack(">I", msg_data[-4:])[0]
    actual_message_crc = _crc32(msg_data[:-4])
    if actual_message_crc != message_crc:
        raise ValueError(f"Message CRC 不匹配: {actual_message_crc} != {message_crc}")

    # 解析头部
    headers_start = PRELUDE_SIZE
    headers_end = headers_start + header_length
    headers = _parse_headers(msg_data[headers_start:headers_end])

    # 提取 payload
    payload = msg_data[headers_end:-4]

    return (Frame(headers=headers, payload=payload), total_length)


class EventStreamDecoder:
    """AWS Event Stream 流式解码器

    使用状态机处理流式数据，支持容错恢复
    """

    def __init__(self, max_errors: int = 5):
        self._buffer = bytearray()
        self._error_count = 0
        self._max_errors = max_errors
        self._frames_decoded = 0
        self._stopped = False

    def feed(self, data: bytes) -> None:
        """向解码器提供数据"""
        if len(self._buffer) + len(data) > MAX_MESSAGE_SIZE:
            raise ValueError("缓冲区溢出")
        self._buffer.extend(data)

    def decode_all(self) -> List[Frame]:
        """解码所有可用帧"""
        frames: List[Frame] = []
        if self._stopped:
            return frames

        offset = 0
        while offset < len(self._buffer):
            try:
                result = parse_frame(bytes(self._buffer), offset)
                if result is None:
                    break
                frame, consumed = result
                offset += consumed
                frames.append(frame)
                self._frames_decoded += 1
                self._error_count = 0
            except ValueError as e:
                self._error_count += 1
                logger.warning("帧解码错误 ({}/{}): {}", self._error_count, self._max_errors, e)
                if self._error_count >= self._max_errors:
                    self._stopped = True
                    break
                # 跳过 1 字节尝试恢复
                offset += 1

        # 移除已处理的数据
        if offset > 0:
            del self._buffer[:offset]

        return frames

    def reset(self) -> None:
        """重置解码器"""
        self._buffer.clear()
        self._error_count = 0
        self._frames_decoded = 0
        self._stopped = False


# ============================================================================
# Kiro 事件类型
# ============================================================================


@dataclass
class AssistantResponseEvent:
    """助手响应事件"""
    content: str = ""


@dataclass
class ToolUseEvent:
    """工具使用事件"""
    name: str = ""
    tool_use_id: str = ""
    input: str = ""
    stop: bool = False


@dataclass
class ContextUsageEvent:
    """上下文使用率事件"""
    context_usage_percentage: float = 0.0


@dataclass
class KiroEvent:
    """统一 Kiro 事件"""
    type: str  # assistant_response / tool_use / context_usage / metering / error / exception / unknown
    assistant_response: Optional[AssistantResponseEvent] = None
    tool_use: Optional[ToolUseEvent] = None
    context_usage: Optional[ContextUsageEvent] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None


def parse_kiro_event(frame: Frame) -> KiroEvent:
    """从帧解析 Kiro 事件"""
    message_type = frame.message_type or "event"

    if message_type == "error":
        return KiroEvent(
            type="error",
            error_code=frame.headers.get(":error-code", "UnknownError"),
            error_message=frame.payload_as_str(),
        )

    if message_type == "exception":
        return KiroEvent(
            type="exception",
            exception_type=frame.headers.get(":exception-type", "UnknownException"),
            exception_message=frame.payload_as_str(),
        )

    event_type = frame.event_type or "unknown"

    if event_type == "assistantResponseEvent":
        try:
            data = frame.payload_as_json()
            return KiroEvent(
                type="assistant_response",
                assistant_response=AssistantResponseEvent(content=data.get("content", "")),
            )
        except Exception:
            return KiroEvent(type="unknown")

    if event_type == "toolUseEvent":
        try:
            data = frame.payload_as_json()
            return KiroEvent(
                type="tool_use",
                tool_use=ToolUseEvent(
                    name=data.get("name", ""),
                    tool_use_id=data.get("toolUseId", ""),
                    input=data.get("input", ""),
                    stop=data.get("stop", False),
                ),
            )
        except Exception:
            return KiroEvent(type="unknown")

    if event_type == "contextUsageEvent":
        try:
            data = frame.payload_as_json()
            return KiroEvent(
                type="context_usage",
                context_usage=ContextUsageEvent(
                    context_usage_percentage=data.get("contextUsagePercentage", 0.0),
                ),
            )
        except Exception:
            return KiroEvent(type="unknown")

    if event_type == "meteringEvent":
        return KiroEvent(type="metering")

    return KiroEvent(type="unknown")


# ============================================================================
# SSE 事件
# ============================================================================


@dataclass
class SseEvent:
    """SSE 事件"""
    event: str
    data: Any

    def to_sse_string(self) -> str:
        """格式化为 SSE 字符串"""
        data_str = json.dumps(self.data, ensure_ascii=False) if not isinstance(self.data, str) else self.data
        return f"event: {self.event}\ndata: {data_str}\n\n"


def create_ping_sse() -> str:
    """创建 ping 保活 SSE 字符串"""
    return 'event: ping\ndata: {"type": "ping"}\n\n'


# ============================================================================
# Thinking 标签检测
# ============================================================================


def _is_quote_char(text: str, pos: int) -> bool:
    """检查指定位置是否为引用字符（反引号、双引号、单引号）"""
    if pos < 0 or pos >= len(text):
        return False
    return text[pos] in ('`', '"', "'")


def find_real_thinking_start_tag(buffer: str) -> Optional[int]:
    """查找真正的 <thinking> 开始标签（不被引用字符包裹）"""
    tag = "<thinking>"
    search_start = 0

    while True:
        pos = buffer.find(tag, search_start)
        if pos == -1:
            return None

        has_quote_before = pos > 0 and _is_quote_char(buffer, pos - 1)
        after_pos = pos + len(tag)
        has_quote_after = _is_quote_char(buffer, after_pos)

        if not has_quote_before and not has_quote_after:
            return pos

        search_start = pos + 1


def find_real_thinking_end_tag(buffer: str) -> Optional[int]:
    """查找真正的 </thinking> 结束标签（后跟 \\n\\n，不被引用字符包裹）"""
    tag = "</thinking>"
    suffix = "\n\n"
    search_start = 0

    while True:
        pos = buffer.find(tag, search_start)
        if pos == -1:
            return None

        # 检查后面是否有 \n\n
        after_tag = pos + len(tag)
        if after_tag + len(suffix) > len(buffer):
            return None  # 数据不足
        if buffer[after_tag:after_tag + len(suffix)] != suffix:
            search_start = pos + 1
            continue

        has_quote_before = pos > 0 and _is_quote_char(buffer, pos - 1)
        has_quote_after = _is_quote_char(buffer, after_tag)

        if not has_quote_before and not has_quote_after:
            return pos

        search_start = pos + 1


# ============================================================================
# Token 估算
# ============================================================================


def estimate_tokens(text: str) -> int:
    """估算文本的 Token 数"""
    if not text:
        return 0
    # 简单估算：英文约 4 字符/token，中文约 1.5 字符/token
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, ascii_chars // 4 + int(non_ascii_chars / 1.5))


# ============================================================================
# StreamContext — 实时 SSE 转换
# ============================================================================


class StreamContext:
    """SSE 流处理上下文

    处理 Kiro 事件并转换为 Anthropic SSE 事件序列。
    管理内容块生命周期（start/delta/stop），支持 thinking 标签检测。
    """

    def __init__(self, model: str, input_tokens: int, thinking_enabled: bool = False):
        self.model = model
        self.message_id = f"msg_{uuid.uuid4().hex[:24]}"
        self.input_tokens = input_tokens
        self.context_input_tokens: Optional[int] = None
        self.output_tokens = 0

        # thinking 状态
        self.thinking_enabled = thinking_enabled
        self.thinking_buffer = ""
        self.in_thinking_block = False
        self.thinking_extracted = False
        self.thinking_block_index: Optional[int] = None
        self.text_block_index: Optional[int] = None
        self.strip_thinking_leading_newline = False

        # SSE 状态
        self._message_started = False
        self._message_delta_sent = False
        self._message_ended = False
        self._next_block_index = 0
        self._active_blocks: Dict[int, dict] = {}  # {index: {type, started, stopped}}
        self._has_tool_use = False
        self._stop_reason: Optional[str] = None

        # 工具块索引映射
        self._tool_block_indices: Dict[str, int] = {}

    def _next_index(self) -> int:
        idx = self._next_block_index
        self._next_block_index += 1
        return idx

    def _get_stop_reason(self) -> str:
        if self._stop_reason:
            return self._stop_reason
        if self._has_tool_use:
            return "tool_use"
        return "end_turn"

    def _has_non_thinking_blocks(self) -> bool:
        return any(b["type"] != "thinking" for b in self._active_blocks.values())

    # ========================================================================
    # 初始事件生成
    # ========================================================================

    def generate_initial_events(self) -> List[SseEvent]:
        """生成初始事件序列（message_start + 文本块 start）"""
        events: List[SseEvent] = []

        # message_start
        if not self._message_started:
            self._message_started = True
            events.append(SseEvent(
                event="message_start",
                data={
                    "type": "message_start",
                    "message": {
                        "id": self.message_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": self.model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": self.input_tokens,
                            "output_tokens": 1,
                        },
                    },
                },
            ))

        # thinking 模式下不在初始化时创建文本块
        if self.thinking_enabled:
            return events

        # 创建初始文本块
        text_idx = self._next_index()
        self.text_block_index = text_idx
        self._active_blocks[text_idx] = {"type": "text", "started": True, "stopped": False}
        events.append(SseEvent(
            event="content_block_start",
            data={
                "type": "content_block_start",
                "index": text_idx,
                "content_block": {"type": "text", "text": ""},
            },
        ))

        return events

    # ========================================================================
    # Kiro 事件处理
    # ========================================================================

    def process_kiro_event(self, event: KiroEvent) -> List[SseEvent]:
        """处理 Kiro 事件并转换为 Anthropic SSE 事件"""
        if event.type == "assistant_response" and event.assistant_response:
            return self._process_assistant_response(event.assistant_response.content)

        if event.type == "tool_use" and event.tool_use:
            return self._process_tool_use(event.tool_use)

        if event.type == "context_usage" and event.context_usage:
            percentage = event.context_usage.context_usage_percentage
            actual = int(percentage * CONTEXT_WINDOW_SIZE / 100.0)
            self.context_input_tokens = actual
            if percentage >= 100.0:
                self._stop_reason = "model_context_window_exceeded"
            return []

        if event.type == "exception":
            if event.exception_type == "ContentLengthExceededException":
                self._stop_reason = "max_tokens"
            logger.warning("收到异常事件: {} - {}", event.exception_type, event.exception_message)
            return []

        if event.type == "error":
            logger.error("收到错误事件: {} - {}", event.error_code, event.error_message)
            return []

        return []

    def _process_assistant_response(self, content: str) -> List[SseEvent]:
        """处理助手响应内容"""
        if not content:
            return []

        self.output_tokens += estimate_tokens(content)

        if self.thinking_enabled:
            return self._process_content_with_thinking(content)

        return self._create_text_delta_events(content)

    # ========================================================================
    # Thinking 处理
    # ========================================================================

    def _process_content_with_thinking(self, content: str) -> List[SseEvent]:
        """处理包含 thinking 块的内容"""
        events: List[SseEvent] = []
        self.thinking_buffer += content

        while True:
            if not self.in_thinking_block and not self.thinking_extracted:
                # 查找 <thinking> 开始标签
                start_pos = find_real_thinking_start_tag(self.thinking_buffer)
                if start_pos is not None:
                    # 发送 <thinking> 之前的非空内容
                    before = self.thinking_buffer[:start_pos]
                    if before and before.strip():
                        events.extend(self._create_text_delta_events(before))

                    self.in_thinking_block = True
                    self.strip_thinking_leading_newline = True
                    self.thinking_buffer = self.thinking_buffer[start_pos + len("<thinking>"):]

                    # 创建 thinking 块
                    thinking_idx = self._next_index()
                    self.thinking_block_index = thinking_idx
                    self._active_blocks[thinking_idx] = {"type": "thinking", "started": True, "stopped": False}
                    events.append(SseEvent(
                        event="content_block_start",
                        data={
                            "type": "content_block_start",
                            "index": thinking_idx,
                            "content_block": {"type": "thinking", "thinking": ""},
                        },
                    ))
                else:
                    # 没有找到 <thinking>，保留可能的部分标签
                    safe_len = max(0, len(self.thinking_buffer) - len("<thinking>"))
                    if safe_len > 0:
                        safe_content = self.thinking_buffer[:safe_len]
                        if safe_content and safe_content.strip():
                            events.extend(self._create_text_delta_events(safe_content))
                            self.thinking_buffer = self.thinking_buffer[safe_len:]
                    break

            elif self.in_thinking_block:
                # 剥离 <thinking> 后的前导换行符
                if self.strip_thinking_leading_newline:
                    if self.thinking_buffer.startswith("\n"):
                        self.thinking_buffer = self.thinking_buffer[1:]
                        self.strip_thinking_leading_newline = False
                    elif self.thinking_buffer:
                        self.strip_thinking_leading_newline = False

                # 查找 </thinking>\n\n
                end_pos = find_real_thinking_end_tag(self.thinking_buffer)
                if end_pos is not None:
                    thinking_content = self.thinking_buffer[:end_pos]
                    if thinking_content and self.thinking_block_index is not None:
                        events.append(self._create_thinking_delta(self.thinking_block_index, thinking_content))

                    self.in_thinking_block = False
                    self.thinking_extracted = True

                    # 关闭 thinking 块
                    if self.thinking_block_index is not None:
                        events.append(self._create_thinking_delta(self.thinking_block_index, ""))
                        events.append(SseEvent(
                            event="content_block_stop",
                            data={"type": "content_block_stop", "index": self.thinking_block_index},
                        ))
                        self._active_blocks[self.thinking_block_index]["stopped"] = True

                    self.thinking_buffer = self.thinking_buffer[end_pos + len("</thinking>\n\n"):]
                else:
                    # 保留可能的部分结束标签
                    safe_len = max(0, len(self.thinking_buffer) - len("</thinking>\n\n"))
                    if safe_len > 0:
                        safe_content = self.thinking_buffer[:safe_len]
                        if safe_content and self.thinking_block_index is not None:
                            events.append(self._create_thinking_delta(self.thinking_block_index, safe_content))
                        self.thinking_buffer = self.thinking_buffer[safe_len:]
                    break
            else:
                # thinking 已提取完毕，剩余内容作为文本
                if self.thinking_buffer:
                    events.extend(self._create_text_delta_events(self.thinking_buffer))
                    self.thinking_buffer = ""
                break

        return events

    def _create_thinking_delta(self, index: int, content: str) -> SseEvent:
        """创建 thinking_delta 事件"""
        return SseEvent(
            event="content_block_delta",
            data={
                "type": "content_block_delta",
                "index": index,
                "delta": {"type": "thinking_delta", "thinking": content},
            },
        )

    # ========================================================================
    # 文本块处理
    # ========================================================================

    def _create_text_delta_events(self, content: str) -> List[SseEvent]:
        """创建 text_delta 事件，如需要会先创建文本块"""
        events: List[SseEvent] = []

        # 如果没有活跃的文本块，创建一个
        if self.text_block_index is None or self._active_blocks.get(self.text_block_index, {}).get("stopped", True):
            text_idx = self._next_index()
            self.text_block_index = text_idx
            self._active_blocks[text_idx] = {"type": "text", "started": True, "stopped": False}
            events.append(SseEvent(
                event="content_block_start",
                data={
                    "type": "content_block_start",
                    "index": text_idx,
                    "content_block": {"type": "text", "text": ""},
                },
            ))

        events.append(SseEvent(
            event="content_block_delta",
            data={
                "type": "content_block_delta",
                "index": self.text_block_index,
                "delta": {"type": "text_delta", "text": content},
            },
        ))

        return events

    # ========================================================================
    # 工具使用处理
    # ========================================================================

    def _process_tool_use(self, tool_use: ToolUseEvent) -> List[SseEvent]:
        """处理工具使用事件"""
        events: List[SseEvent] = []
        self._has_tool_use = True

        # thinking 模式下，如果有缓冲的内容需要先 flush
        if self.thinking_enabled and self.thinking_buffer:
            # flush thinking buffer 中残留的结束标签
            remaining = self.thinking_buffer
            self.thinking_buffer = ""

            if self.in_thinking_block:
                # 移除可能的 </thinking> 尾部
                end_tag = "</thinking>"
                if remaining.endswith(end_tag) or end_tag in remaining:
                    tag_pos = remaining.find(end_tag)
                    if tag_pos >= 0:
                        thinking_content = remaining[:tag_pos]
                        if thinking_content and self.thinking_block_index is not None:
                            events.append(self._create_thinking_delta(self.thinking_block_index, thinking_content))
                        remaining = ""

                self.in_thinking_block = False
                self.thinking_extracted = True

                # 关闭 thinking 块
                if self.thinking_block_index is not None:
                    bk = self._active_blocks.get(self.thinking_block_index, {})
                    if not bk.get("stopped", True):
                        events.append(self._create_thinking_delta(self.thinking_block_index, ""))
                        events.append(SseEvent(
                            event="content_block_stop",
                            data={"type": "content_block_stop", "index": self.thinking_block_index},
                        ))
                        self._active_blocks[self.thinking_block_index]["stopped"] = True
            elif remaining.strip():
                events.extend(self._create_text_delta_events(remaining))

        # 关闭当前文本块（如果有）
        if self.text_block_index is not None:
            bk = self._active_blocks.get(self.text_block_index, {})
            if bk.get("started") and not bk.get("stopped"):
                events.append(SseEvent(
                    event="content_block_stop",
                    data={"type": "content_block_stop", "index": self.text_block_index},
                ))
                self._active_blocks[self.text_block_index]["stopped"] = True

        tool_id = tool_use.tool_use_id

        if tool_id not in self._tool_block_indices:
            # 新工具块
            tool_idx = self._next_index()
            self._tool_block_indices[tool_id] = tool_idx
            self._active_blocks[tool_idx] = {"type": "tool_use", "started": True, "stopped": False}

            events.append(SseEvent(
                event="content_block_start",
                data={
                    "type": "content_block_start",
                    "index": tool_idx,
                    "content_block": {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": tool_use.name,
                        "input": {},
                    },
                },
            ))

        tool_idx = self._tool_block_indices[tool_id]

        # 发送 input_json_delta
        if tool_use.input:
            events.append(SseEvent(
                event="content_block_delta",
                data={
                    "type": "content_block_delta",
                    "index": tool_idx,
                    "delta": {"type": "input_json_delta", "partial_json": tool_use.input},
                },
            ))

        # 工具调用完成
        if tool_use.stop:
            events.append(SseEvent(
                event="content_block_stop",
                data={"type": "content_block_stop", "index": tool_idx},
            ))
            self._active_blocks[tool_idx]["stopped"] = True

        return events

    # ========================================================================
    # 结束事件
    # ========================================================================

    def generate_final_events(self) -> List[SseEvent]:
        """生成最终事件序列"""
        events: List[SseEvent] = []

        # flush thinking buffer
        if self.thinking_enabled and self.thinking_buffer:
            remaining = self.thinking_buffer
            self.thinking_buffer = ""

            if self.in_thinking_block:
                # 移除 </thinking> 标签
                end_tag = "</thinking>"
                tag_pos = remaining.find(end_tag)
                if tag_pos >= 0:
                    thinking_content = remaining[:tag_pos]
                    if thinking_content and self.thinking_block_index is not None:
                        events.append(self._create_thinking_delta(self.thinking_block_index, thinking_content))
                elif remaining and self.thinking_block_index is not None:
                    events.append(self._create_thinking_delta(self.thinking_block_index, remaining))

                self.in_thinking_block = False

                # 关闭 thinking 块
                if self.thinking_block_index is not None:
                    bk = self._active_blocks.get(self.thinking_block_index, {})
                    if not bk.get("stopped", True):
                        events.append(self._create_thinking_delta(self.thinking_block_index, ""))
                        events.append(SseEvent(
                            event="content_block_stop",
                            data={"type": "content_block_stop", "index": self.thinking_block_index},
                        ))
                        self._active_blocks[self.thinking_block_index]["stopped"] = True
            elif remaining.strip():
                events.extend(self._create_text_delta_events(remaining))

        # 如果只有 thinking 没有 text/tool，补发 text 块 + stop_reason=max_tokens
        if self.thinking_enabled and not self._has_non_thinking_blocks():
            if not self._stop_reason:
                self._stop_reason = "max_tokens"
            # 补发一个空白 text 块
            events.extend(self._create_text_delta_events(" "))

        # 关闭所有未关闭的块
        for idx, block in self._active_blocks.items():
            if block["started"] and not block["stopped"]:
                events.append(SseEvent(
                    event="content_block_stop",
                    data={"type": "content_block_stop", "index": idx},
                ))
                block["stopped"] = True

        # 计算最终的 input_tokens
        final_input_tokens = self.context_input_tokens if self.context_input_tokens is not None else self.input_tokens

        # message_delta
        if not self._message_delta_sent:
            self._message_delta_sent = True
            events.append(SseEvent(
                event="message_delta",
                data={
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": self._get_stop_reason(),
                        "stop_sequence": None,
                    },
                    "usage": {
                        "input_tokens": final_input_tokens,
                        "output_tokens": self.output_tokens,
                    },
                },
            ))

        # message_stop
        if not self._message_ended:
            self._message_ended = True
            events.append(SseEvent(
                event="message_stop",
                data={"type": "message_stop"},
            ))

        return events


# ============================================================================
# BufferedStreamContext — 缓冲模式（/cc/v1）
# ============================================================================


class BufferedStreamContext:
    """缓冲流处理上下文

    缓冲所有事件直到流结束，然后从 contextUsageEvent 修正 input_tokens，
    再一次性发送所有事件。用于 /cc/v1/messages 端点。
    """

    def __init__(self, model: str, estimated_input_tokens: int, thinking_enabled: bool = False):
        self._stream_ctx = StreamContext(model, estimated_input_tokens, thinking_enabled)
        self._buffered_events: List[SseEvent] = []
        # 先生成初始事件并缓冲
        initial = self._stream_ctx.generate_initial_events()
        self._buffered_events.extend(initial)

    def process_and_buffer(self, event: KiroEvent) -> None:
        """处理 Kiro 事件并缓冲结果"""
        sse_events = self._stream_ctx.process_kiro_event(event)
        self._buffered_events.extend(sse_events)

    def finish_and_get_all_events(self) -> List[SseEvent]:
        """完成处理并返回所有事件（已修正 input_tokens）"""
        # 生成最终事件
        final = self._stream_ctx.generate_final_events()
        self._buffered_events.extend(final)

        # 用 context_input_tokens 修正 message_start 中的 input_tokens
        actual_input = self._stream_ctx.context_input_tokens
        if actual_input is not None:
            for ev in self._buffered_events:
                if ev.event == "message_start" and isinstance(ev.data, dict):
                    msg = ev.data.get("message")
                    if isinstance(msg, dict) and "usage" in msg:
                        msg["usage"]["input_tokens"] = actual_input

        return self._buffered_events
