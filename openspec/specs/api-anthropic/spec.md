# Anthropic API 规范

## 目的
提供与 Anthropic Claude API 兼容的端点，接受 Anthropic 格式的请求并返回 Anthropic 格式的响应，通过 Kiro 上游 API 进行代理。

## 需求

### 需求：消息创建端点
系统应当（SHALL）提供 POST `/v1/messages` 端点，以 Anthropic 格式创建聊天补全。

#### 场景：流式请求
- 假设（GIVEN）一个 `stream: true` 的有效请求
- 当（WHEN）调用 POST `/v1/messages` 时
- 则（THEN）以 SSE（Server-Sent Events）格式返回，`Content-Type: text/event-stream`
- 且（AND）事件包括 `message_start`、`content_block_start`、`content_block_delta`、`content_block_stop`、`message_delta`、`message_stop`
- 且（AND）每 25 秒发送一次 ping 事件以保持连接

#### 场景：非流式请求
- 假设（GIVEN）一个 `stream: false` 的有效请求
- 当（WHEN）调用 POST `/v1/messages` 时
- 则（THEN）返回完整的 JSON 响应，包含 `id`、`type`、`role`、`content`、`model`、`stop_reason`、`usage`

#### 场景：不支持的模型
- 假设（GIVEN）请求的模型名称无法映射
- 当（WHEN）调用 POST `/v1/messages` 时
- 则（THEN）返回 400 响应，错误类型为 `invalid_request_error`

#### 场景：消息为空
- 假设（GIVEN）请求的 `messages` 数组为空
- 当（WHEN）调用 POST `/v1/messages` 时
- 则（THEN）返回 400 响应，错误类型为 `invalid_request_error`

### 需求：Claude Code 缓冲端点
系统应当（SHALL）提供 POST `/cc/v1/messages` 端点，采用缓冲流式传输以获得精确的 `input_tokens`。

#### 场景：缓冲流式请求
- 假设（GIVEN）一个发往 `/cc/v1/messages` 的有效流式请求
- 当（WHEN）上游响应完成后
- 则（THEN）`message_start` 中包含来自 `contextUsageEvent` 的精确 `input_tokens`
- 且（AND）所有 SSE 事件在上游完成后一次性发送
- 且（AND）等待期间每 25 秒发送一次 ping 事件

#### 场景：非流式请求（与 /v1 相同）
- 假设（GIVEN）一个发往 `/cc/v1/messages` 的有效非流式请求
- 当（WHEN）处理请求时
- 则（THEN）行为与 `/v1/messages` 非流式模式完全一致

### 需求：模型列表端点
系统应当（SHALL）提供 GET `/v1/models` 端点，返回可用模型列表。

#### 场景：列出模型
- 假设（GIVEN）一个已认证的有效请求
- 当（WHEN）调用 GET `/v1/models` 时
- 则（THEN）返回 JSON 响应，`object: "list"`，`data` 包含 Sonnet、Opus、Haiku 各版本

### 需求：Token 计数端点
系统应当（SHALL）提供 POST `/v1/messages/count_tokens` 端点，用于估算 Token 数量。

#### 场景：计算 Token
- 假设（GIVEN）包含 `model` 和 `messages` 的有效请求
- 当（WHEN）调用 POST `/v1/messages/count_tokens` 时
- 则（THEN）返回包含 `input_tokens` 的 JSON 响应（估算值，最小为 1）

### 需求：Thinking 模式支持
系统应当（SHALL）通过请求参数 `thinking` 支持扩展思考模式。

#### 场景：启用 thinking
- 假设（GIVEN）请求携带 `thinking: {type: "enabled", budget_tokens: 20000}`
- 当（WHEN）处理请求时
- 则（THEN）响应包含 thinking 内容块
- 且（AND）`budget_tokens` 上限为 24576

#### 场景：通过模型名称后缀启用 thinking
- 假设（GIVEN）请求的模型名称以 `-thinking` 结尾
- 当（WHEN）处理请求时
- 则（THEN）自动启用 thinking（type: "enabled"，budget_tokens: 20000）
- 且（AND）对于 Opus 4.6 模型，type 设置为 "adaptive"

### 需求：工具调用支持
系统应当（SHALL）支持 Anthropic 工具调用（函数调用）。

#### 场景：工具调用请求
- 假设（GIVEN）请求包含带有工具定义的 `tools` 数组
- 当（WHEN）助手决定使用工具时
- 则（THEN）响应包含 `tool_use` 内容块
- 且（AND）`stop_reason` 设为 `"tool_use"`

#### 场景：工具结果
- 假设（GIVEN）请求包含 `tool_result` 内容块
- 当（WHEN）处理请求时
- 则（THEN）工具结果转换为 Kiro 格式并包含在对话中

### 需求：WebSearch 工具
系统应当（SHALL）通过 Kiro MCP API 处理 WebSearch 工具请求。

#### 场景：WebSearch 请求
- 假设（GIVEN）请求中仅包含 `web_search_*` 类型的工具
- 当（WHEN）处理请求时
- 则（THEN）路由到 Kiro MCP 端点（`/mcp`）
- 且（AND）MCP 响应转换为 Anthropic 格式返回

### 需求：系统消息支持
系统应当（SHALL）支持 `system` 字段的字符串和数组两种格式。

#### 场景：字符串格式系统消息
- 假设（GIVEN）`system: "你是一个有用的助手"`
- 当（WHEN）处理请求时
- 则（THEN）内部转换为系统消息数组

#### 场景：数组格式系统消息
- 假设（GIVEN）`system: [{text: "你是一个有用的助手"}]`
- 当（WHEN）处理请求时
- 则（THEN）每个 text 条目均作为系统提示内容

### 需求：模型名称映射
系统应当（SHALL）将 Anthropic 模型名称映射到 Kiro 内部模型 ID。

#### 场景：Sonnet 模型
- 假设（GIVEN）模型名称包含 "sonnet"
- 当（WHEN）进行映射时
- 则（THEN）解析为 `claude-sonnet-4.5`

#### 场景：Opus 4.5 模型
- 假设（GIVEN）模型名称包含 "opus" 且包含 "4.5" 或 "4-5"
- 当（WHEN）进行映射时
- 则（THEN）解析为 `claude-opus-4.5`

#### 场景：其他 Opus 模型
- 假设（GIVEN）模型名称包含 "opus" 但不含 "4.5"
- 当（WHEN）进行映射时
- 则（THEN）解析为 `claude-opus-4.6`

#### 场景：Haiku 模型
- 假设（GIVEN）模型名称包含 "haiku"
- 当（WHEN）进行映射时
- 则（THEN）解析为 `claude-haiku-4.5`
