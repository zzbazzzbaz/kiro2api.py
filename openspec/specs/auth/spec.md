# 认证规范

## 目的
管理 API 访问的认证与授权，支持外部 API Key（面向终端用户）和 Admin API Key（面向管理员）。

## 需求

### 需求：外部 API Key 认证
系统应当（SHALL）使用 API Key 对外部 API 请求进行认证。

#### 场景：通过 x-api-key 头部传入有效 Key
- 假设（GIVEN）数据库中存在一个已启用的 API Key
- 当（WHEN）请求携带 `x-api-key: <有效key>` 头部到达时
- 则（THEN）请求通过认证
- 且（AND）该 API Key 的 `group_id` 被注入请求上下文
- 且（AND）`last_used_at` 和 `request_count` 被更新

#### 场景：通过 Bearer Token 传入有效 Key
- 假设（GIVEN）数据库中存在一个已启用的 API Key
- 当（WHEN）请求携带 `Authorization: Bearer <有效key>` 头部到达时
- 则（THEN）认证行为与 x-api-key 方式完全一致

#### 场景：无效 API Key
- 假设（GIVEN）API Key 在数据库中不存在
- 当（WHEN）请求到达时
- 则（THEN）返回 401 响应：`{"error": {"type": "authentication_error", "message": "Invalid API key"}}`

#### 场景：已禁用的 API Key
- 假设（GIVEN）API Key 的 `enabled = false`
- 当（WHEN）携带该 Key 的请求到达时
- 则（THEN）返回 401 认证错误

#### 场景：缺少 API Key
- 假设（GIVEN）请求未携带任何 API Key 头部
- 当（WHEN）请求到达受保护端点时
- 则（THEN）返回 401 认证错误

### 需求：API Key 安全存储
系统必须（MUST）使用 SHA-256 哈希安全存储 API Key。

#### 场景：Key 存储
- 假设（GIVEN）一个新生成的 API Key
- 当（WHEN）持久化到数据库时
- 则（THEN）仅存储 SHA-256 哈希值
- 且（AND）存储展示用前缀（如 `sk-xxxx****`）

#### 场景：Key 比较
- 假设（GIVEN）传入一个 API Key
- 当（WHEN）与存储的哈希进行比较时
- 则（THEN）使用常量时间比较（`hmac.compare_digest`）防止时序攻击

### 需求：Admin API Key 认证
系统应当（SHALL）使用配置在环境变量中的独立 Admin API Key 对管理接口进行认证。

#### 场景：有效的 Admin Key
- 假设（GIVEN）`.env` 中配置了有效的 Admin API Key
- 当（WHEN）携带正确 Key 的请求到达 `/api/admin/*` 时
- 则（THEN）请求通过认证

#### 场景：无效的 Admin Key
- 假设（GIVEN）Admin API Key 不正确
- 当（WHEN）请求到达 `/api/admin/*` 时
- 则（THEN）返回 401 响应：`{"error": {"type": "authentication_error", "message": "Invalid or missing admin API key"}}`

#### 场景：Admin Key 配置为空
- 假设（GIVEN）`.env` 中 `ADMIN_API_KEY` 为空或未设置
- 当（WHEN）应用启动时
- 则（THEN）Admin API 路由不注册
- 且（AND）输出警告日志

### 需求：Token 额度强制执行
系统必须（MUST）在处理请求前对每个 API Key 执行 Token 额度检查。

#### 场景：额度内
- 假设（GIVEN）API Key 的 `token_quota = 100000`，`tokens_used = 50000`
- 当（WHEN）请求到达时
- 则（THEN）正常处理请求

#### 场景：超出额度
- 假设（GIVEN）API Key 的 `token_quota = 100000`，`tokens_used = 100000`
- 当（WHEN）请求到达时
- 则（THEN）返回 429 响应：`{"error": {"type": "rate_limit_error", "message": "Token quota exceeded"}}`

#### 场景：无限额度
- 假设（GIVEN）API Key 的 `token_quota = None`
- 当（WHEN）请求到达时
- 则（THEN）不执行额度检查
