# 消费记录规范

## 目的
记录每个外部 API Key 的每次请求消费数据，支持使用分析和额度强制执行。

## 需求

### 需求：请求日志记录
系统应当（SHALL）在响应完成后异步记录每次 API 调用的消费数据。

#### 场景：流式请求完成后记录
- 假设（GIVEN）通过 API Key `sk-ext-aaa` 完成了一个流式请求
- 当（WHEN）SSE 流结束时
- 则（THEN）创建一条 usage_log 记录，包含 `api_key_id`、`timestamp`、`client_ip`、`model`、`input_tokens`、`output_tokens`、`total_tokens`
- 且（AND）`api_keys.tokens_used` 增加 `total_tokens` 的数量
- 且（AND）日志写入不阻塞客户端响应

#### 场景：非流式请求完成后记录
- 假设（GIVEN）完成了一个非流式请求
- 当（WHEN）发送 JSON 响应后
- 则（THEN）根据响应 `usage` 字段中的精确 Token 数创建 usage_log 记录

#### 场景：请求失败（未消耗 Token）
- 假设（GIVEN）请求在到达上游 API 之前就失败了
- 当（WHEN）返回错误响应时
- 则（THEN）不创建 usage_log 记录
- 且（AND）`tokens_used` 不递增

### 需求：消费记录查询
系统应当（SHALL）提供 Admin API 端点用于查询消费日志。

#### 场景：按 API Key 查询
- 假设（GIVEN）一个 API Key ID
- 当（WHEN）调用 GET `/api/admin/api-keys/{id}/usage` 时
- 则（THEN）返回该 Key 的消费日志，按时间戳倒序排列

#### 场景：按时间范围查询
- 假设（GIVEN）一个 API Key ID 及查询参数 `start` 和 `end`（RFC3339 格式）
- 当（WHEN）调用 GET `/api/admin/api-keys/{id}/usage?start=...&end=...` 时
- 则（THEN）仅返回该时间范围内的日志

### 需求：额度累计
系统应当（SHALL）维护每个 API Key 的累计 Token 用量。

#### 场景：Token 累加
- 假设（GIVEN）API Key 的 `tokens_used = 50000`
- 当（WHEN）一次请求消耗了 1500 个 Token 时
- 则（THEN）`tokens_used` 更新为 51500

#### 场景：并发累加
- 假设（GIVEN）两个并发请求同时完成
- 当（WHEN）两者均尝试递增 `tokens_used` 时
- 则（THEN）两次递增均正确应用（数据库原子更新）
