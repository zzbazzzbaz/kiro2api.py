# 设计文档：初始构建 — kiro2api

## 技术方案

Python 3.12+ 全异步 FastAPI 应用，使用 SQLAlchemy 2.0 异步 ORM 配合 SQLite。所有 I/O 操作（数据库、HTTP、文件）均使用 async/await。通过 httpx AsyncClient 调用上游 Kiro API，并按代理配置缓存客户端实例。

## 架构决策

### 决策：选用 FastAPI 而非 Flask/Django
- 原生异步支持，无需额外适配
- 内置 OpenAPI 文档自动生成
- 深度集成 Pydantic v2 进行请求/响应验证
- 支持依赖注入（`Depends()`）

### 决策：选用 SQLite 而非 PostgreSQL
- 零配置，单文件部署
- 对预期请求量已足够
- aiosqlite 提供异步访问
- Alembic 管理 Schema 迁移

### 决策：选用 httpx 而非 aiohttp
- httpx 原生支持 SOCKS5 代理（`httpx[socks]`）
- 类 requests 的熟悉 API
- 原生异步流式支持
- 按代理配置缓存 AsyncClient 实例（与 kiro.rs `client_cache` 模式一致）

### 决策：进程内 Token Manager 而非外部服务
- Token 刷新对延迟敏感，必须在 API 调用前完成
- asyncio.Lock 对单进程并发控制足够
- 状态保存在内存 + 数据库，无需 Redis

### 决策：异步消费日志写入
- 响应完成后通过 `asyncio.create_task()` 异步写入日志
- 不阻塞响应返回
- 进程崩溃时可能丢失少量日志（可接受，非关键业务）

## 数据流

### 请求处理流程
```
客户端请求
    │
    ▼
FastAPI 中间件（CORS → 认证）
    │
    ├── 提取 API Key → 查询 group_id
    ├── 检查 Token 额度（tokens_used < token_quota）
    │
    ▼
路由层（Anthropic / OpenAI / Admin）
    │
    ├── OpenAI 请求？→ 转换为 Anthropic 格式
    │
    ▼
协议转换（Anthropic → Kiro）
    │
    ▼
KiroProvider
    ├── 从分组中选择凭据（优先级/均衡模式）
    ├── 确保 Token 有效（如需则刷新）
    ├── 构建请求（头部、请求体、签名）
    ├── 调用上游 Kiro API
    ├── 失败时故障转移到下一凭据（每凭据最多重试 3 次，总计 9 次）
    │
    ▼
流式处理（Kiro → Anthropic SSE）
    ├── 解码 AWS Event Stream 帧
    ├── 转换为 Anthropic SSE 事件
    ├── /cc/v1：缓冲至 contextUsageEvent 后一次性发送
    ├── OpenAI 请求：进一步转换为 OpenAI SSE 格式
    │
    ▼
响应返回给客户端
    │
    ▼
异步：写入 usage_log + 累加 tokens_used
```

### Token 刷新流程
```
ensure_valid_token(凭据)
    │
    ├── Token 有效？→ 返回 access_token
    │
    └── Token 已过期或即将过期？
         │
         ├── 获取该凭据的 asyncio.Lock
         │
         ├── 二次检查（另一个协程可能已完成刷新）
         │
         ├── auth_method == "social"？
         │   └── POST oidc.{auth_region}.amazonaws.com/token
         │       grant_type=refresh_token
         │
         ├── auth_method == "idc"？
         │   └── POST oidc.{auth_region}.amazonaws.com/token
         │       grant_type=refresh_token + client_id + client_secret
         │
         ├── 更新数据库中的 Token（access_token、refresh_token、expires_at）
         │
         └── 释放锁，返回新 access_token
```

## 关键组件

### MultiTokenManager
- 启动时从数据库加载所有凭据到内存
- 每个凭据独立的 asyncio.Lock，防止并发刷新
- 提供 Admin API 查询用的快照方法
- 支持 set_disabled / set_priority / reset_and_enable 操作
- 可选：后台刷新循环，主动刷新 10 分钟内即将过期的 Token

### KiroProvider
- 管理 httpx.AsyncClient 实例（按代理配置缓存）
- 重试逻辑：每个凭据最多重试 3 次，跨凭据总计 9 次
- 指数退避策略
- 构建 Kiro API 请求头（Authorization、x-amz-*、User-Agent）

### StreamContext / BufferedStreamContext
- **StreamContext**：实时 SSE 转换，用于 `/v1/messages`
- **BufferedStreamContext**：缓冲全部事件，从 contextUsageEvent 修正 input_tokens，再一次性发送，用于 `/cc/v1/messages`
- 两者均处理 thinking 标签检测、工具调用组装、内容块生命周期管理

### OpenAI 格式转换器
- 请求方向：OpenAI messages → Anthropic messages + 提取 system 消息
- 响应方向（流式）：Anthropic SSE → OpenAI `chat.completion.chunk` SSE
- 响应方向（非流式）：Anthropic JSON → OpenAI `chat.completion` JSON

## 文件变更清单

所有文件均为新建（全新项目）：

### 核心层
- `app/main.py` — FastAPI 应用入口 + lifespan
- `app/core/config.py` — pydantic-settings 配置类
- `app/core/database.py` — SQLAlchemy 异步引擎
- `app/core/security.py` — API Key 哈希与验证工具函数

### ORM 模型
- `app/models/base.py` — 声明式基类
- `app/models/credential.py` — 凭据表
- `app/models/group.py` — 分组表
- `app/models/api_key.py` — API Key 表（含额度字段）
- `app/models/usage_log.py` — 消费日志表

### Pydantic Schema
- `app/schemas/anthropic.py` — Anthropic API 类型
- `app/schemas/openai.py` — OpenAI API 类型
- `app/schemas/credential.py` — 凭据请求/响应
- `app/schemas/api_key.py` — API Key 请求/响应
- `app/schemas/group.py` — 分组请求/响应
- `app/schemas/admin.py` — 通用 Admin 响应
- `app/schemas/error.py` — 错误响应模型

### 服务层
- `app/services/token_manager.py` — TokenManager + MultiTokenManager
- `app/services/kiro_provider.py` — 上游 API 调用 + 重试
- `app/services/converter.py` — Anthropic ↔ Kiro 格式转换
- `app/services/stream.py` — SSE 事件流处理
- `app/services/websearch.py` — WebSearch → MCP
- `app/services/credential_service.py` — 凭据业务逻辑
- `app/services/api_key_service.py` — API Key 业务逻辑
- `app/services/group_service.py` — 分组业务逻辑

### API 路由
- `app/api/v1/anthropic/router.py` — /v1 + /cc/v1 路由注册
- `app/api/v1/anthropic/messages.py` — 消息处理器
- `app/api/v1/anthropic/messages_cc.py` — 缓冲消息处理器
- `app/api/v1/anthropic/models.py` — 模型列表处理器
- `app/api/v1/anthropic/count_tokens.py` — Token 计数处理器
- `app/api/v1/openai/router.py` — /v1/chat 路由注册
- `app/api/v1/openai/chat_completions.py` — Chat Completions 处理器
- `app/api/v1/admin/router.py` — /api/admin 路由注册
- `app/api/v1/admin/credentials.py` — 凭据 CRUD 处理器
- `app/api/v1/admin/api_keys.py` — API Key 处理器
- `app/api/v1/admin/groups.py` — 分组处理器
- `app/api/v1/admin/config.py` — 配置处理器
- `app/api/dependencies.py` — 公共依赖项

### 中间件
- `app/middleware/auth.py` — 外部 API Key 认证
- `app/middleware/admin_auth.py` — Admin API Key 认证
- `app/middleware/cors.py` — CORS（允许所有来源）

### 工具类
- `app/utils/http_client.py` — httpx 客户端构建器
- `app/utils/machine_id.py` — 设备指纹生成
- `app/utils/helpers.py` — 通用工具函数

### 项目配置
- `pyproject.toml` — 项目元数据 + 依赖
- `.env.example` — 环境变量示例
- `alembic/` — 数据库迁移文件
