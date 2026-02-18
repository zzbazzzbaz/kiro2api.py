# Anthropic 兼容 API

## POST /v1/messages

创建消息（对话），支持流式和非流式输出。

### 请求

**Headers：**

| Header | 必需 | 说明 |
|---|---|---|
| `Content-Type` | ✅ | `application/json` |
| `x-api-key` | 视配置 | 外部 API Key（`REQUIRE_API_KEY=true` 时必需） |

**请求体 JSON：**

```json
{
  "model": "claude-sonnet-4-5-20250514",
  "max_tokens": 4096,
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "system": "You are a helpful assistant.",
  "tools": [],
  "thinking": {"type": "enabled", "budget_tokens": 20000},
  "metadata": {"user_id": "session-uuid"}
}
```

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|---|---|---|---|---|
| `model` | string | ✅ | — | 模型名称，需包含 `sonnet`/`opus`/`haiku` 关键词。加 `-thinking` 后缀自动启用扩展思考 |
| `max_tokens` | integer | ✅ | — | 最大输出 Token 数 |
| `messages` | array | ✅ | — | 对话消息列表，见下方 [消息格式](#消息格式) |
| `stream` | boolean | 否 | `false` | 是否使用 SSE 流式输出 |
| `system` | string \| array | 否 | `null` | 系统消息。支持纯字符串或 `[{"type":"text","text":"..."}]` 数组格式 |
| `tools` | array | 否 | `null` | 可用工具列表，见下方 [工具定义格式](#工具定义格式) |
| `tool_choice` | object | 否 | `null` | 工具选择策略 |
| `thinking` | object | 否 | `null` | 扩展思考配置，见下方 [Thinking 配置](#thinking-配置) |
| `output_config` | object | 否 | `null` | 输出配置 `{"effort": "high"}` |
| `metadata` | object | 否 | `null` | 请求元数据。`user_id` 用于关联会话 ID |

#### 消息格式

每条消息包含 `role` 和 `content` 两个字段：

```json
{
  "role": "user",
  "content": "纯文本内容"
}
```

`content` 支持两种格式：

**1. 纯字符串：**

```json
{"role": "user", "content": "Hello!"}
```

**2. 内容块数组：**

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "看这张图片"},
    {
      "type": "image",
      "source": {
        "type": "base64",
        "media_type": "image/png",
        "data": "iVBORw0KGgo..."
      }
    }
  ]
}
```

**内容块类型：**

| type | 字段 | 说明 |
|---|---|---|
| `text` | `text` | 文本内容 |
| `image` | `source` | 图片。`source.type` 固定为 `"base64"`，`source.media_type` 为 MIME 类型，`source.data` 为 Base64 数据 |
| `tool_use` | `id`, `name`, `input` | 工具调用（role=assistant 时） |
| `tool_result` | `tool_use_id`, `content`, `is_error` | 工具执行结果（role=user 时） |
| `thinking` | `thinking` | 思考内容（role=assistant 时） |

#### 工具定义格式

```json
{
  "name": "get_weather",
  "description": "获取天气信息",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {"type": "string", "description": "城市名"}
    },
    "required": ["location"]
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 工具名称 |
| `description` | string | 否 | 工具描述 |
| `input_schema` | object | 否 | 输入参数的 JSON Schema |

**WebSearch 工具（特殊格式）：**

```json
{
  "type": "web_search_20250305",
  "name": "web_search",
  "max_uses": 3
}
```

当检测到 WebSearch 工具时，请求会被路由到 MCP WebSearch 处理流程。

#### Thinking 配置

```json
{
  "type": "enabled",
  "budget_tokens": 20000
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | `"enabled"` 强制启用 / `"disabled"` 禁用 / `"adaptive"` 自适应 |
| `budget_tokens` | integer | 思考预算 Token 数（最大 24576，超出会被截断） |

### 响应

#### 非流式响应（stream=false）

```json
{
  "id": "msg_40a115960be44874abd6a14b",
  "type": "message",
  "role": "assistant",
  "content": [
    {"type": "text", "text": "Hello! How can I help you?"}
  ],
  "model": "claude-sonnet-4.5",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 2055,
    "output_tokens": 12
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 消息唯一 ID |
| `type` | string | 固定为 `"message"` |
| `role` | string | 固定为 `"assistant"` |
| `content` | array | 内容块数组（text / thinking / tool_use） |
| `model` | string | Kiro 内部模型 ID（如 `claude-sonnet-4.5`） |
| `stop_reason` | string | 停止原因：`"end_turn"` / `"tool_use"` / `"max_tokens"` |
| `stop_sequence` | string\|null | 触发停止的序列（通常为 null） |
| `usage.input_tokens` | integer | 输入 Token 数 |
| `usage.output_tokens` | integer | 输出 Token 数 |

#### 流式响应（stream=true）

返回 `text/event-stream` 格式的 SSE 流。事件顺序：

```
event: message_start
data: {"type":"message_start","message":{...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"input_tokens":2055,"output_tokens":2}}

event: message_stop
data: {"type":"message_stop"}
```

**SSE 事件类型：**

| 事件 | 说明 |
|---|---|
| `message_start` | 消息开始，包含 `message` 对象（含 `id`、`model`、初始 `usage`） |
| `content_block_start` | 内容块开始，`index` 为块序号，`content_block` 含 `type`（text/thinking） |
| `content_block_delta` | 内容增量。`delta.type` 为 `text_delta`（文本）或 `thinking_delta`（思考） |
| `content_block_stop` | 内容块结束 |
| `message_delta` | 消息结束信息，含 `stop_reason` 和最终 `usage` |
| `message_stop` | 消息流结束 |
| `ping` | 保活心跳（每 15 秒） |

---

## POST /cc/v1/messages

缓冲流式端点。与 `/v1/messages` 参数完全相同，区别在于：

- 内部仍使用流式调用上游
- **缓冲所有事件**直到流结束
- 修正 `input_tokens` 为上游返回的真实值（从 `contextUsageEvent` 获取）
- 然后一次性发送所有 SSE 事件

**适用场景：** 需要精确 `input_tokens` 的客户端。

请求格式与 `/v1/messages` 完全一致，不再重复。

---

## GET /v1/models

获取支持的模型列表。

### 请求

无请求体。

### 响应

```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-sonnet-4-5-20250514",
      "object": "model",
      "created": 0,
      "owned_by": "anthropic",
      "display_name": "Claude Sonnet 4.5",
      "type": "model",
      "max_tokens": 8192
    },
    {
      "id": "claude-sonnet-4-20250514",
      "object": "model",
      "created": 0,
      "owned_by": "anthropic",
      "display_name": "Claude Sonnet 4",
      "type": "model",
      "max_tokens": 8192
    },
    {
      "id": "claude-haiku-4-5-20250514",
      "object": "model",
      "created": 0,
      "owned_by": "anthropic",
      "display_name": "Claude Haiku 4.5",
      "type": "model",
      "max_tokens": 8192
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 模型 ID（用于 `model` 字段传入） |
| `display_name` | string | 模型显示名称 |
| `max_tokens` | integer | 该模型支持的最大输出 Token 数 |

---

## POST /v1/messages/count_tokens

估算输入 Token 数量。

### 请求

```json
{
  "model": "claude-sonnet-4-5-20250514",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "system": "You are helpful.",
  "tools": []
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `model` | string | ✅ | 模型名称 |
| `messages` | array | ✅ | 消息列表（格式同 /v1/messages） |
| `system` | string \| array | 否 | 系统消息 |
| `tools` | array | 否 | 工具定义列表 |

### 响应

```json
{
  "input_tokens": 15
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `input_tokens` | integer | 估算的输入 Token 数。优先调用外部 API（如已配置 `COUNT_TOKENS_API_URL`），否则使用本地估算（字符数/3） |

### 请求示例

```bash
# 流式对话
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 1024,
    "stream": true,
    "messages": [
      {"role": "user", "content": "用一句话解释量子计算"}
    ]
  }'

# 带系统消息和工具
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 2048,
    "stream": true,
    "system": "你是一个天气助手",
    "messages": [
      {"role": "user", "content": "北京今天天气怎么样？"}
    ],
    "tools": [
      {
        "name": "get_weather",
        "description": "获取指定城市的天气",
        "input_schema": {
          "type": "object",
          "properties": {
            "city": {"type": "string"}
          },
          "required": ["city"]
        }
      }
    ]
  }'

# 启用扩展思考
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 4096,
    "stream": true,
    "thinking": {"type": "enabled", "budget_tokens": 20000},
    "messages": [
      {"role": "user", "content": "证明根号2是无理数"}
    ]
  }'

# 使用 -thinking 后缀（等效于上面的 thinking 配置）
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514-thinking",
    "max_tokens": 4096,
    "stream": true,
    "messages": [
      {"role": "user", "content": "证明根号2是无理数"}
    ]
  }'

# 多轮对话
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 1024,
    "stream": false,
    "messages": [
      {"role": "user", "content": "我叫小明"},
      {"role": "assistant", "content": "你好小明！有什么我能帮你的？"},
      {"role": "user", "content": "你还记得我叫什么吗？"}
    ]
  }'
```
