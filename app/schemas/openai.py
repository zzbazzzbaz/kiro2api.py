"""
OpenAI API 兼容类型 Schema

用于 /v1/chat/completions 端点的请求与响应格式转换
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ===== 请求类型 =====

class ChatMessage(BaseModel):
    """OpenAI 格式的聊天消息"""
    role: str = Field(description="角色: system / user / assistant / tool")
    content: Optional[Any] = Field(default=None, description="消息内容（字符串或内容块数组）")
    name: Optional[str] = Field(default=None, description="发送者名称")
    tool_calls: Optional[List[Any]] = Field(default=None, description="工具调用列表")
    tool_call_id: Optional[str] = Field(default=None, description="工具调用 ID（role=tool 时）")


class FunctionDefinition(BaseModel):
    """函数定义"""
    name: str
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """OpenAI 工具定义"""
    type: str = "function"
    function: FunctionDefinition


class ChatCompletionRequest(BaseModel):
    """POST /v1/chat/completions 请求体"""
    model: str = Field(description="模型名称")
    messages: List[ChatMessage] = Field(description="聊天消息列表")
    max_tokens: Optional[int] = Field(default=4096, description="最大输出 Token 数")
    temperature: Optional[float] = Field(default=None, description="温度参数")
    top_p: Optional[float] = Field(default=None, description="Top-P 采样")
    stream: bool = Field(default=False, description="是否使用流式输出")
    tools: Optional[List[ToolDefinition]] = Field(default=None, description="可用工具列表")
    tool_choice: Optional[Any] = Field(default=None, description="工具选择策略")
    stop: Optional[Any] = Field(default=None, description="停止序列")
    n: int = Field(default=1, description="生成数量")


# ===== 响应类型（非流式） =====

class ChatCompletionUsage(BaseModel):
    """Token 使用量"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ToolCallFunction(BaseModel):
    """工具调用函数"""
    name: str
    arguments: str = Field(description="JSON 字符串格式的参数")


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    type: str = "function"
    function: ToolCallFunction


class ChatCompletionMessage(BaseModel):
    """完成消息"""
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionChoice(BaseModel):
    """完成选项"""
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    """POST /v1/chat/completions 非流式响应"""
    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)


# ===== 流式响应类型 =====

class ChatCompletionChunkDelta(BaseModel):
    """流式块增量"""
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None


class ChatCompletionChunkChoice(BaseModel):
    """流式选项"""
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """POST /v1/chat/completions 流式响应块"""
    id: str
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str
    choices: List[ChatCompletionChunkChoice]
    usage: Optional[ChatCompletionUsage] = None
