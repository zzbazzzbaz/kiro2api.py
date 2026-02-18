"""
Anthropic API 类型 Schema

包含 Messages、Tool、Thinking、ContentBlock、Models 等类型定义
与 Anthropic API 完全兼容
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ===== 最大思考预算 =====
MAX_BUDGET_TOKENS: int = 24576


# ===== Thinking 配置 =====

class Thinking(BaseModel):
    """扩展思考配置"""
    type: str = Field(description="思考类型: enabled / disabled / adaptive")
    budget_tokens: int = Field(default=20000, description="思考预算 Token 数")

    @field_validator("budget_tokens")
    @classmethod
    def clamp_budget(cls, v: int) -> int:
        """限制最大思考预算"""
        return min(v, MAX_BUDGET_TOKENS)

    def is_enabled(self) -> bool:
        """是否启用了思考（enabled 或 adaptive）"""
        return self.type in ("enabled", "adaptive")


# ===== Output 配置 =====

class OutputConfig(BaseModel):
    """输出配置"""
    effort: str = Field(default="high", description="输出努力程度")


# ===== Metadata =====

class Metadata(BaseModel):
    """请求元数据（如 Claude Code 的 session 信息）"""
    user_id: Optional[str] = Field(default=None, description="用户 ID")


# ===== 系统消息 =====

class SystemMessage(BaseModel):
    """系统消息"""
    type: str = Field(default="text")
    text: str


# ===== 消息 =====

class Message(BaseModel):
    """对话消息

    content 支持字符串或 ContentBlock 数组
    """
    role: str = Field(description="角色: user / assistant")
    content: Any = Field(description="消息内容（字符串或内容块数组）")


# ===== 图片源 =====

class ImageSource(BaseModel):
    """图片数据源"""
    type: str = Field(description="源类型: base64")
    media_type: str = Field(description="MIME 类型: image/jpeg, image/png 等")
    data: str = Field(description="Base64 编码的图片数据")


# ===== 内容块 =====

class ContentBlock(BaseModel):
    """内容块

    type 决定了其他字段的含义：
    - text: 文本内容
    - thinking: 思考内容
    - tool_use: 工具调用
    - tool_result: 工具执行结果
    - image: 图片内容
    """
    type: str
    text: Optional[str] = None
    thinking: Optional[str] = None
    tool_use_id: Optional[str] = None
    content: Optional[Any] = None
    name: Optional[str] = None
    input: Optional[Any] = None
    id: Optional[str] = None
    is_error: Optional[bool] = None
    source: Optional[ImageSource] = None


# ===== 工具定义 =====

class Tool(BaseModel):
    """工具定义

    支持两种格式：
    1. 普通工具：name + description + input_schema
    2. WebSearch 工具：type="web_search_20250305" + name + max_uses
    """
    type: Optional[str] = Field(default=None, description="工具类型（仅 WebSearch）")
    name: str = Field(default="", description="工具名称")
    description: str = Field(default="", description="工具描述")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="输入参数 JSON Schema")
    max_uses: Optional[int] = Field(default=None, description="最大使用次数（仅 WebSearch）")

    def is_web_search(self) -> bool:
        """是否为 WebSearch 工具"""
        return self.type is not None and self.type.startswith("web_search")


# ===== Messages 请求 =====

class MessagesRequest(BaseModel):
    """POST /v1/messages 请求体"""
    model: str = Field(description="模型名称")
    max_tokens: int = Field(description="最大输出 Token 数")
    messages: List[Message] = Field(description="对话消息列表")
    stream: bool = Field(default=False, description="是否使用流式输出")
    system: Optional[Union[str, List[SystemMessage]]] = Field(default=None, description="系统消息")
    tools: Optional[List[Tool]] = Field(default=None, description="可用工具列表")
    tool_choice: Optional[Any] = Field(default=None, description="工具选择策略")
    thinking: Optional[Thinking] = Field(default=None, description="扩展思考配置")
    output_config: Optional[OutputConfig] = Field(default=None, description="输出配置")
    metadata: Optional[Metadata] = Field(default=None, description="请求元数据")

    @field_validator("system", mode="before")
    @classmethod
    def normalize_system(cls, v: Any) -> Optional[List[SystemMessage]]:
        """将系统消息统一为列表格式

        支持字符串或对象数组输入
        """
        if v is None:
            return None
        if isinstance(v, str):
            return [SystemMessage(text=v)]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    result.append(SystemMessage(text=item))
                elif isinstance(item, dict):
                    result.append(SystemMessage(**item))
                elif isinstance(item, SystemMessage):
                    result.append(item)
            return result if result else None
        return v


# ===== Token 计数 =====

class CountTokensRequest(BaseModel):
    """POST /v1/messages/count_tokens 请求体"""
    model: str
    messages: List[Message]
    system: Optional[Union[str, List[SystemMessage]]] = None
    tools: Optional[List[Tool]] = None

    @field_validator("system", mode="before")
    @classmethod
    def normalize_system(cls, v: Any) -> Optional[List[SystemMessage]]:
        """统一系统消息格式"""
        if v is None:
            return None
        if isinstance(v, str):
            return [SystemMessage(text=v)]
        return v


class CountTokensResponse(BaseModel):
    """Token 计数响应"""
    input_tokens: int


# ===== Models 端点 =====

class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "anthropic"
    display_name: str = ""
    type: str = "model"
    max_tokens: int = 8192


class ModelsResponse(BaseModel):
    """模型列表响应"""
    object: str = "list"
    data: List[ModelInfo] = []


# ===== SSE 事件类型（用于流式响应构建）=====

class Usage(BaseModel):
    """Token 使用量"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


class MessageStartEvent(BaseModel):
    """message_start SSE 事件的 message 对象"""
    id: str
    type: str = "message"
    role: str = "assistant"
    content: List[Any] = Field(default_factory=list)
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Usage = Field(default_factory=Usage)


class ContentBlockDelta(BaseModel):
    """内容块增量"""
    type: str
    text: Optional[str] = None
    thinking: Optional[str] = None
    partial_json: Optional[str] = None


class MessageDelta(BaseModel):
    """message_delta 事件数据"""
    stop_reason: str = "end_turn"
    stop_sequence: Optional[str] = None


class MessageDeltaUsage(BaseModel):
    """message_delta 中的 usage"""
    output_tokens: int = 0
