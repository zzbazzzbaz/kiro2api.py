# OpenAI API 规范

## 目的
提供与 OpenAI Chat Completions API 兼容的端点，接受 OpenAI 格式请求，内部转换为 Anthropic 格式，并以 OpenAI 格式返回响应。

## 需求

### 需求：Chat Completions 端点
系统应当（SHALL）提供与 OpenAI Chat Completions API 兼容的 POST `/v1/chat/completions` 端点。

#### 场景：流式请求
- 假设（GIVEN）一个 `stream: true` 的有效请求
- 当（WHEN）调用 POST `/v1/chat/completions` 时
- 则（THEN）以 SSE 格式返回，每个数据块类型为 `chat.completion.chunk`
- 且（AND）最后一个块为 `data: [DONE]`

#### 场景：非流式请求
- 假设（GIVEN）一个 `stream: false` 的有效请求
- 当（WHEN）调用 POST `/v1/chat/completions` 时
- 则（THEN）返回完整 JSON 响应，包含 `id`、`object: "chat.completion"`、`choices`、`usage`

### 需求：OpenAI 消息格式转 Anthropic 格式
系统应当（SHALL）将 OpenAI 消息格式转换为 Anthropic 消息格式。

#### 场景：提取 system 角色消息
- 假设（GIVEN）消息列表中包含 `role: "system"` 的条目
- 当（WHEN）转换为 Anthropic 格式时
- 则（THEN）system 消息被提取到 `system` 字段
- 且（AND）多条 system 消息拼接合并

#### 场景：user 和 assistant 角色
- 假设（GIVEN）消息包含 `role: "user"` 或 `role: "assistant"`
- 当（WHEN）转换为 Anthropic 格式时
- 则（THEN）角色直接映射

#### 场景：tool 角色转换
- 假设（GIVEN）一条带有 `role: "tool"` 和 `tool_call_id` 的消息
- 当（WHEN）转换为 Anthropic 格式时
- 则（THEN）转换为 `tool_result` 内容块

### 需求：Anthropic 响应转 OpenAI 格式
系统应当（SHALL）将 Anthropic SSE 事件转换为 OpenAI SSE 格式。

#### 场景：文本内容增量
- 假设（GIVEN）一个 `type: "text_delta"` 的 Anthropic `content_block_delta`
- 当（WHEN）转换为 OpenAI 格式时
- 则（THEN）生成 `{"choices": [{"delta": {"content": "..."}}]}`

#### 场景：思考内容增量
- 假设（GIVEN）一个 `type: "thinking_delta"` 的 Anthropic `content_block_delta`
- 当（WHEN）转换为 OpenAI 格式时
- 则（THEN）生成 `{"choices": [{"delta": {"reasoning_content": "..."}}]}`

#### 场景：工具调用
- 假设（GIVEN）一个 Anthropic tool_use 内容块
- 当（WHEN）转换为 OpenAI 格式时
- 则（THEN）生成 `{"choices": [{"delta": {"tool_calls": [...]}}]}`

#### 场景：用量统计
- 假设（GIVEN）包含 `input_tokens` 和 `output_tokens` 的 Anthropic 用量数据
- 当（WHEN）转换为 OpenAI 格式时
- 则（THEN）生成 `{"usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...}}`

### 需求：不支持参数的处理
系统宜（SHOULD）优雅处理 Kiro 不支持的 OpenAI 参数。

#### 场景：temperature 参数
- 假设（GIVEN）请求携带 `temperature` 参数
- 当（WHEN）处理请求时
- 则（THEN）`temperature` 被静默忽略（Kiro 不支持此参数）

#### 场景：top_p 参数
- 假设（GIVEN）请求携带 `top_p` 参数
- 当（WHEN）处理请求时
- 则（THEN）`top_p` 被静默忽略
