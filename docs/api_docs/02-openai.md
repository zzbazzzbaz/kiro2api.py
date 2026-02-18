# OpenAI 兼容 API

## POST /v1/chat/completions

OpenAI Chat Completions 兼容端点。内部自动将 OpenAI 格式转换为 Anthropic 格式，调用 Kiro API 后再转换回 OpenAI 格式响应。

### 请求

**Headers：**

| Header | 必需 | 说明 |
|---|---|---|
| `Content-Type` | ✅ | `application/json` |
| `x-api-key` | 视配置 | 外部 API Key（`REQUIRE_API_KEY=true` 时必需） |
| `Authorization` | 视配置 | `Bearer sk-xxx` 格式（与 x-api-key 二选一） |

**请求体 JSON：**

```json
{
  "model": "claude-sonnet-4-5-20250514",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "max_tokens": 4096,
  "stream": false,
  "temperature": null,
  "top_p": null,
  "tools": null,
  "tool_choice": null,
  "stop": null,
  "n": 1
}
```

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|---|---|---|---|---|
| `model` | string | ✅ | — | 模型名称，需包含 `sonnet`/`opus`/`haiku` 关键词 |
| `messages` | array | ✅ | — | 聊天消息列表，见下方 [消息格式](#消息格式) |
| `max_tokens` | integer | 否 | `4096` | 最大输出 Token 数 |
| `stream` | boolean | 否 | `false` | 是否使用 SSE 流式输出 |
| `temperature` | float | 否 | `null` | 温度参数（传入但不影响 Kiro 行为） |
| `top_p` | float | 否 | `null` | Top-P 采样（传入但不影响 Kiro 行为） |
| `tools` | array | 否 | `null` | 工具定义列表，见下方 [工具定义格式](#工具定义格式) |
| `tool_choice` | object | 否 | `null` | 工具选择策略 |
| `stop` | string\|array | 否 | `null` | 停止序列（传入但不影响 Kiro 行为） |
| `n` | integer | 否 | `1` | 生成数量（固定为 1，传入其他值无效） |

> **注意：** `temperature`、`top_p`、`stop`、`n` 字段会被接受但不会传递给 Kiro API，因为 Kiro 不支持这些参数。

#### 消息格式

```json
{
  "role": "user",
  "content": "消息内容"
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `role` | string | ✅ | 角色：`system` / `user` / `assistant` / `tool` |
| `content` | string\|null | 否 | 消息文本内容 |
| `name` | string | 否 | 发送者名称 |
| `tool_calls` | array | 否 | 工具调用列表（role=assistant 时） |
| `tool_call_id` | string | 否 | 关联的工具调用 ID（role=tool 时） |

**角色转换规则：**

| OpenAI role | 转换为 Anthropic | 说明 |
|---|---|---|
| `system` | `system` 参数 | 提取为独立的系统消息，多条合并 |
| `user` | `user` | 直接映射 |
| `assistant` | `assistant` | 含 `tool_calls` 时转换为 `tool_use` 内容块 |
| `tool` | `user` + `tool_result` | 转换为带 `tool_result` 内容块的 user 消息 |

#### 工具定义格式

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "获取天气信息",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {"type": "string", "description": "城市名"}
      },
      "required": ["location"]
    }
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `type` | string | 否 | 固定为 `"function"` |
| `function.name` | string | ✅ | 函数名称 |
| `function.description` | string | 否 | 函数描述 |
| `function.parameters` | object | 否 | 参数 JSON Schema |

### 响应

#### 非流式响应（stream=false）

```json
{
  "id": "chatcmpl-e5211b47eabc44af9ed8bfa0",
  "object": "chat.completion",
  "created": 1771388779,
  "model": "claude-sonnet-4-5-20250514",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 2064,
    "completion_tokens": 8,
    "total_tokens": 2072
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 完成 ID，格式为 `chatcmpl-{hex24}` |
| `object` | string | 固定为 `"chat.completion"` |
| `created` | integer | Unix 时间戳 |
| `model` | string | 请求时传入的原始模型名称 |
| `choices[0].message.role` | string | 固定为 `"assistant"` |
| `choices[0].message.content` | string\|null | 回复文本内容 |
| `choices[0].message.tool_calls` | array\|null | 工具调用列表（如有） |
| `choices[0].finish_reason` | string | `"stop"`（正常结束）/ `"tool_calls"`（工具调用） |
| `usage.prompt_tokens` | integer | 输入 Token 数 |
| `usage.completion_tokens` | integer | 输出 Token 数 |
| `usage.total_tokens` | integer | 总 Token 数（prompt + completion） |

#### 流式响应（stream=true）

返回 `text/event-stream` 格式的 SSE 流：

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1771388797,"model":"claude-sonnet-4-5-20250514","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1771388797,"model":"claude-sonnet-4-5-20250514","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1771388797,"model":"claude-sonnet-4-5-20250514","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1771388797,"model":"claude-sonnet-4-5-20250514","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**流式块字段说明：**

| 字段 | 说明 |
|---|---|
| `choices[0].delta.role` | 仅首个 chunk 包含，固定为 `"assistant"` |
| `choices[0].delta.content` | 文本增量 |
| `choices[0].finish_reason` | 最后一个 chunk 为 `"stop"` 或 `"tool_calls"`，其余为 `null` |
| `data: [DONE]` | 流结束标记 |

### 请求示例

```bash
# 非流式
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 100,
    "messages": [
      {"role": "user", "content": "What is 2+2?"}
    ]
  }'

# 流式
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 100,
    "stream": true,
    "messages": [
      {"role": "system", "content": "回答要简短"},
      {"role": "user", "content": "什么是 Python？"}
    ]
  }'

# 带工具调用
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "查一下北京天气"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "获取天气",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string"}
            },
            "required": ["city"]
          }
        }
      }
    ]
  }'
```
