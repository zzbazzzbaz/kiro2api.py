# 任务清单：初始构建 — kiro2api

## 1. 项目基础搭建
- [x] 1.1 创建项目目录结构（`app/`、`alembic/`、`data/`）
- [x] 1.2 创建 `pyproject.toml`，包含所有依赖
- [x] 1.3 创建 `.env.example`，包含所有配置变量
- [x] 1.4 实现 `app/core/config.py` — pydantic-settings `Settings` 类
- [x] 1.5 实现 `app/core/database.py` — 异步 SQLAlchemy 引擎 + Session 工厂
- [x] 1.6 实现 `app/core/security.py` — API Key 哈希、常量时间比较
- [x] 1.7 创建 `app/models/base.py` — SQLAlchemy 声明式基类
- [x] 1.8 初始化 Alembic，配置异步 SQLite
- [x] 1.9 创建 `app/main.py` — FastAPI 应用骨架（含 lifespan）

## 2. 数据库模型
- [x] 2.1 实现 `app/models/credential.py` — 凭据表
- [x] 2.2 实现 `app/models/group.py` — 分组表
- [x] 2.3 实现 `app/models/api_key.py` — API Key 表（含额度字段）
- [x] 2.4 实现 `app/models/usage_log.py` — 消费日志表
- [x] 2.5 生成初始 Alembic 迁移文件
- [x] 2.6 测试：验证数据库创建和表结构

## 3. Pydantic Schema
- [x] 3.1 实现 `app/schemas/error.py` — ErrorResponse、AdminErrorResponse
- [x] 3.2 实现 `app/schemas/anthropic.py` — MessagesRequest、Tool、Thinking、ContentBlock 等
- [x] 3.3 实现 `app/schemas/openai.py` — ChatCompletionRequest、ChatCompletionResponse 等
- [x] 3.4 实现 `app/schemas/credential.py` — AddCredentialRequest、CredentialStatusItem、BalanceResponse、AccountStatusResponse
- [x] 3.5 实现 `app/schemas/api_key.py` — CreateApiKeyRequest、ApiKeyResponse、UsageLogResponse
- [x] 3.6 实现 `app/schemas/group.py` — CreateGroupRequest、GroupResponse
- [x] 3.7 实现 `app/schemas/admin.py` — SuccessResponse、LoadBalancingModeResponse

## 4. 工具类
- [x] 4.1 实现 `app/utils/http_client.py` — 支持代理的 httpx AsyncClient 构建器
- [x] 4.2 实现 `app/utils/machine_id.py` — 基于 SHA-256 的设备指纹生成
- [x] 4.3 实现 `app/utils/helpers.py` — 通用工具函数（RFC3339 时间戳等）

## 5. Token 管理（从 kiro.rs 移植）
- [x] 5.1 实现 Social Token 刷新 — POST OIDC 端点，grant_type=refresh_token
- [x] 5.2 实现 IdC Token 刷新 — POST 携带 client_id + client_secret
- [x] 5.3 实现 Token 过期检测（5 分钟提前量）
- [x] 5.4 实现 `TokenManager` 类 — 单凭据 Token 生命周期管理
- [x] 5.5 实现 `MultiTokenManager` 类，包含：
  - [x] 5.5.1 每凭据独立的 asyncio.Lock 防止并发刷新
  - [x] 5.5.2 优先级模式凭据选择
  - [x] 5.5.3 均衡模式凭据选择
  - [x] 5.5.4 Admin API 查询用快照方法
  - [x] 5.5.5 set_disabled / set_priority / reset_and_enable 操作
  - [x] 5.5.6 失败时切换到下一个凭据（switch_to_next）
  - [x] 5.5.7 刷新后将 Token 持久化到数据库
- [x] 5.6 实现后台刷新循环（可选，主动刷新 10 分钟内将过期的 Token）
- [x] 5.7 实现 Region 回退链（凭据.auth_region → 全局 AUTH_REGION → 全局 REGION）

## 6. Kiro Provider（从 kiro.rs 移植）
- [x] 6.1 实现 `KiroProvider` 类，包含：
  - [x] 6.1.1 按代理配置缓存 httpx AsyncClient
  - [x] 6.1.2 构建请求头（Authorization、x-amz-*、User-Agent、Host 等）
  - [x] 6.1.3 根据 api_region 构建 Base URL
  - [x] 6.1.4 为 WebSearch 构建 MCP URL
- [x] 6.2 实现 `call_api_stream()` — 带重试的流式上游调用
- [x] 6.3 实现 `call_api()` — 带重试的非流式上游调用
- [x] 6.4 实现重试逻辑：
  - [x] 6.4.1 每个凭据最多重试 3 次
  - [x] 6.4.2 总计最多重试 9 次
  - [x] 6.4.3 指数退避
  - [x] 6.4.4 持续失败时故障转移到下一凭据
- [x] 6.5 实现凭据级代理解析（凭据代理 → 全局代理 → 无代理）

## 7. 协议转换（从 kiro.rs 移植）
- [x] 7.1 实现模型名称映射（sonnet/opus/haiku → Kiro 模型 ID）
- [x] 7.2 实现消息转换：
  - [x] 7.2.1 用户消息 → Kiro UserMessage 格式
  - [x] 7.2.2 助手消息 → Kiro AssistantMessage 格式
  - [x] 7.2.3 系统消息 → userInputMessageContext
  - [x] 7.2.4 工具定义 → Kiro ToolSpecification
  - [x] 7.2.5 工具结果 → Kiro ToolResult
  - [x] 7.2.6 图片内容 → Kiro 图片格式
- [x] 7.3 实现对话状态组装（历史消息 + 当前消息）
- [x] 7.4 实现 Write/Edit 工具描述后缀注入
- [x] 7.5 实现系统分块策略注入
- [x] 7.6 实现从模型名称后缀自动覆盖 thinking 配置

## 8. 流式处理（从 kiro.rs 移植）
- [x] 8.1 实现 AWS Event Stream 帧解码器
- [x] 8.2 实现 Kiro 事件解析（AssistantResponse、ToolUse、ContextUsage、Exception 等）
- [x] 8.3 实现 `StreamContext` — 实时 SSE 转换：
  - [x] 8.3.1 生成 message_start（含估算的 input_tokens）
  - [x] 8.3.2 管理内容块生命周期（start/delta/stop）
  - [x] 8.3.3 thinking 标签检测（真实标签 vs. 引用标签）
  - [x] 8.3.4 组装工具调用 JSON
  - [x] 8.3.5 生成结束事件（message_delta + message_stop）
- [x] 8.4 实现 `BufferedStreamContext` — 用于 /cc/v1：
  - [x] 8.4.1 缓冲所有事件直到流结束
  - [x] 8.4.2 从 contextUsageEvent 修正 input_tokens
  - [x] 8.4.3 一次性发送所有事件
- [x] 8.5 实现 SSE 保活机制（每 25 秒发送 ping）

## 9. WebSearch 处理（从 kiro.rs 移植）
- [x] 9.1 实现 WebSearch 工具检测
- [x] 9.2 实现 MCP 请求构建（JSON-RPC 2.0）
- [x] 9.3 实现 MCP 响应解析
- [x] 9.4 实现 Anthropic 格式响应生成（tool_use + 搜索结果）

## 10. Anthropic API 路由
- [x] 10.1 实现 `app/api/v1/anthropic/router.py` — 路由注册
- [x] 10.2 实现 `GET /v1/models` — 模型列表端点
- [x] 10.3 实现 `POST /v1/messages` — 流式 + 非流式
- [x] 10.4 实现 `POST /cc/v1/messages` — 缓冲流式
- [x] 10.5 实现 `POST /v1/messages/count_tokens` — Token 估算
- [x] 10.6 实现请求体大小限制（50MB）

## 11. OpenAI API 路由
- [x] 11.1 实现 `app/api/v1/openai/router.py` — 路由注册
- [x] 11.2 实现 OpenAI → Anthropic 请求转换器
- [x] 11.3 实现 Anthropic → OpenAI 响应转换器（流式 + 非流式）
- [x] 11.4 实现 `POST /v1/chat/completions`

## 12. 中间件
- [x] 12.1 实现 `app/middleware/auth.py` — 外部 API Key 认证：
  - [x] 12.1.1 从 x-api-key 或 Authorization Bearer 提取 Key
  - [x] 12.1.2 在数据库中查找 SHA-256 哈希
  - [x] 12.1.3 检查启用状态
  - [x] 12.1.4 检查 Token 额度
  - [x] 12.1.5 将 group_id 注入请求状态
  - [x] 12.1.6 更新 last_used_at 和 request_count
- [x] 12.2 实现 `app/middleware/admin_auth.py` — Admin API Key 认证
- [x] 12.3 实现 `app/middleware/cors.py` — CORS（允许所有来源）

## 13. 业务服务
- [x] 13.1 实现 `app/services/credential_service.py`：
  - [x] 13.1.1 get_all_credentials（含状态快照）
  - [x] 13.1.2 add_credential（主动获取订阅等级）
  - [x] 13.1.3 delete_credential（要求先禁用）
  - [x] 13.1.4 set_disabled / set_priority / reset_and_enable
  - [x] 13.1.5 get_balance（5 分钟缓存）
  - [x] 13.1.6 get_account_status（解析上游 usage_data）
  - [x] 13.1.7 batch_get_account_status（批量查询）
- [x] 13.2 实现 `app/services/api_key_service.py`：
  - [x] 13.2.1 generate_api_key（密码学随机 + SHA-256 存储）
  - [x] 13.2.2 revoke_api_key
  - [x] 13.2.3 enable / disable
  - [x] 13.2.4 set_quota / reset_usage
  - [x] 13.2.5 list_api_keys
  - [x] 13.2.6 get_usage_logs（支持时间范围过滤）
- [x] 13.3 实现 `app/services/group_service.py`：
  - [x] 13.3.1 create_group
  - [x] 13.3.2 update_group
  - [x] 13.3.3 delete_group（检查关联）
  - [x] 13.3.4 list_groups

## 14. Admin API 路由
- [x] 14.1 实现 `app/api/v1/admin/router.py` — 路由注册
- [x] 14.2 实现凭据端点（GET/POST/DELETE + 子资源）
- [x] 14.3 实现 API Key 端点（GET/POST/DELETE + 子资源）
- [x] 14.4 实现分组端点（GET/POST/PUT/DELETE）
- [x] 14.5 实现配置端点（GET/PUT 负载均衡模式）
- [x] 14.6 实现账号状态端点（单个 + 批量）

## 15. 消费记录
- [x] 15.1 实现异步日志写入器（响应后通过 asyncio.create_task）
- [x] 15.2 实现 tokens_used 原子递增
- [x] 15.3 在消息处理器中接入消费记录（流/响应完成后）
- [x] 15.4 在 chat_completions 处理器中接入消费记录

## 16. 依赖注入与整体串联
- [x] 16.1 实现 `app/api/dependencies.py` — DB Session、当前 API Key 信息、KiroProvider
- [x] 16.2 在 `app/main.py` 中注册所有路由
- [x] 16.3 实现 lifespan：数据库初始化 → 加载凭据 → 创建 MultiTokenManager → 创建 KiroProvider → 启动后台任务
- [x] 16.4 实现优雅关闭：取消后台任务 → 关闭 httpx 客户端 → 关闭数据库

## 17. 测试与验证
- [x] 17.1 手动测试：启动服务，验证 `/v1/models` 返回模型列表
- [x] 17.2 手动测试：通过 Admin API 添加凭据，验证 Token 刷新
- [x] 17.3 手动测试：创建分组和 API Key，发送 `/v1/messages` 请求
- [x] 17.4 手动测试：验证流式 SSE 输出
- [x] 17.5 手动测试：验证 `/v1/chat/completions` OpenAI 兼容性
- [x] 17.6 手动测试：验证额度强制执行（超额返回 429）
- [x] 17.7 手动测试：验证消费日志写入
- [x] 17.8 手动测试：验证账号状态检测
