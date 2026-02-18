# 流式响应规范

## 目的
将 Kiro AWS Event Stream 转换为 Anthropic SSE 事件，包括 thinking 标签检测、内容块管理和保活处理。

## 需求

### 需求：事件流解码
系统应当（SHALL）解码 Kiro AWS Event Stream 的二进制帧，提取结构化事件。

#### 场景：有效帧
- 假设（GIVEN）一个包含完整 AWS Event Stream 帧（头部 + 载荷 + CRC）的二进制数据块
- 当（WHEN）解码器处理该数据块时
- 则（THEN）正确提取事件类型和载荷

#### 场景：不完整帧
- 假设（GIVEN）一个包含不完整帧的二进制数据块
- 当（WHEN）解码器处理该数据块时
- 则（THEN）数据被缓冲，直到收到完整帧

### 需求：SSE 事件生成
系统应当（SHALL）将 Kiro 事件转换为 Anthropic SSE 格式。

#### 场景：文本内容
- 假设（GIVEN）一个包含文本内容的 Kiro `assistantResponseEvent`
- 当（WHEN）转换为 SSE 时
- 则（THEN）生成 `type: "text_delta"` 的 `content_block_delta` 事件

#### 场景：思考内容
- 假设（GIVEN）已启用 thinking 模式，且内容位于 `<thinking>` 标签之间
- 当（WHEN）转换为 SSE 时
- 则（THEN）在独立内容块中生成 `type: "thinking_delta"` 的 `content_block_delta` 事件

#### 场景：工具调用内容
- 假设（GIVEN）一个带有工具名称和 JSON 输入的 Kiro `toolUseEvent`
- 当（WHEN）转换为 SSE 时
- 则（THEN）先生成 `type: "tool_use"` 的 `content_block_start`，再生成 `input_json_delta` 事件

#### 场景：上下文用量事件
- 假设（GIVEN）一个包含 `context_usage_percentage` 的 Kiro `contextUsageEvent`
- 当（WHEN）进行转换时
- 则（THEN）`input_tokens` 按 `percentage * 200000 / 100` 计算
- 且（AND）如果 `percentage >= 100%`，`stop_reason` 设为 `"model_context_window_exceeded"`

### 需求：Thinking 标签检测
系统应当（SHALL）正确区分真实的 `</thinking>` 结束标签与引用中的同名标签。

#### 场景：真实结束标签
- 假设（GIVEN）文本中包含 `</thinking>\n\n`（后跟双换行）
- 当（WHEN）检测结束标签时
- 则（THEN）该标签被识别为真实的结束标签

#### 场景：引用中的标签
- 假设（GIVEN）文本中包含 `` `</thinking>` `` 或 `"</thinking>"`
- 当（WHEN）检测结束标签时
- 则（THEN）该标签被忽略（属于引用，非真实标签）

#### 场景：标签位于缓冲区末尾
- 假设（GIVEN）`</thinking>` 出现在当前缓冲区末尾
- 当（WHEN）检测结束标签时
- 则（THEN）等待更多数据以确认后续是否为双换行

### 需求：保活机制
系统应当（SHALL）每 25 秒发送一次 ping 事件，防止连接超时。

#### 场景：长时间运行的流
- 假设（GIVEN）一个持续超过 25 秒的流式响应
- 当（WHEN）25 秒内没有数据时
- 则（THEN）发送 `event: ping\ndata: {"type": "ping"}\n\n`

### 需求：结束事件
系统应当（SHALL）在流结束时生成正确的关闭事件。

#### 场景：正常流结束
- 假设（GIVEN）上游流正常结束
- 当（WHEN）生成最终事件时
- 则（THEN）依次发送 `content_block_stop`、`message_delta`（含 `stop_reason` 和 `usage`）、`message_stop`

#### 场景：流中途出错
- 假设（GIVEN）上游流中途发生错误
- 当（WHEN）检测到错误时
- 则（THEN）仍然发送最终事件以正确关闭 SSE 连接
