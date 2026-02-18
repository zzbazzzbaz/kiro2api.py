# kiro2api

Kiro API 代理服务 — 将 Anthropic/OpenAI API 请求通过 Kiro 上游 API 进行代理，支持多凭据管理、分组、外部 API Key 管理、消费记录与 Token 额度控制。

本项目是 Rust 版 [kiro.rs](../../../kiro.rs) 的 Python 重写，基于 FastAPI 全异步架构。

## 功能特性

- **Anthropic API 兼容** — `/v1/messages`、`/v1/models`、`/v1/messages/count_tokens`、`/cc/v1/messages`
- **OpenAI API 兼容** — `/v1/chat/completions`，自动格式转换
- **多凭据故障转移** — 优先级/均衡模式负载均衡，自动故障转移（每凭据最多 3 次，总计 9 次）
- **Token 自动刷新** — 支持 Social 和 IdC (BuilderId) 两种认证方式
- **协议转换** — Anthropic ↔ Kiro 请求/响应转换，含流式 SSE 支持
- **扩展思考 (Thinking)** — 支持 enabled/adaptive 模式，含真实标签检测
- **WebSearch** — Anthropic WebSearch 工具 → Kiro MCP 转换
- **凭据池分组** — 隔离的凭据池，支持分组级负载均衡
- **外部 API Key 管理** — 生成、吊销、启用/禁用、绑定分组
- **Token 额度控制** — 每个 Key 独立设置 Token 上限，请求前前置检查
- **消费记录** — 异步记录每次请求的 IP、模型、输入/输出 Token 数
- **Admin API** — 凭据、API Key、分组、配置的完整 CRUD
- **凭据级代理** — 每个凭据可独立配置 HTTP/SOCKS5 代理

## 技术栈

| 组件 | 技术选型 |
|---|---|
| Web 框架 | FastAPI (全异步) |
| ORM | SQLAlchemy 2.0 (异步) |
| 数据库 | SQLite + aiosqlite |
| 迁移工具 | Alembic |
| HTTP 客户端 | httpx (支持 SOCKS5) |
| 配置管理 | pydantic-settings |
| Python | 3.12+ |

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入配置
```

### 3. 初始化数据库

```bash
uv run alembic upgrade head
```

### 4. 启动服务

```bash
uv run python run.py
```

服务启动后会自动从数据库加载凭据并初始化 Token 管理器。

### 5. 添加凭据

通过 Admin API 添加 Kiro 凭据：

**IdC (BuilderId) 凭据：**

```bash
curl -X POST http://127.0.0.1:8000/api/admin/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "你的refreshToken",
    "auth_method": "idc",
    "client_id": "你的clientId",
    "client_secret": "你的clientSecret",
    "region": "us-east-1"
  }'
```

**Social 凭据：**

```bash
curl -X POST http://127.0.0.1:8000/api/admin/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "你的refreshToken",
    "auth_method": "social"
  }'
```

> ⚠️ 添加凭据后需要重启服务以加载到内存中的 Token 管理器。

### 6. 测试请求

```bash
# Anthropic 格式（流式）
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 100,
    "stream": true,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# OpenAI 格式
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## API 端点

### Anthropic 兼容

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/models` | 模型列表 |
| POST | `/v1/messages` | 消息（流式/非流式） |
| POST | `/cc/v1/messages` | 消息（缓冲流式，修正 input_tokens） |
| POST | `/v1/messages/count_tokens` | Token 估算 |

### OpenAI 兼容

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/chat/completions` | Chat Completions（流式/非流式） |

### Admin API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/credentials` | 凭据列表 |
| POST | `/api/admin/credentials` | 添加凭据 |
| DELETE | `/api/admin/credentials/{id}` | 删除凭据（需先禁用） |
| POST | `/api/admin/credentials/{id}/disable` | 禁用凭据 |
| POST | `/api/admin/credentials/{id}/enable` | 启用凭据 |
| POST | `/api/admin/credentials/{id}/reset` | 重置并启用 |
| PUT | `/api/admin/credentials/{id}/priority` | 设置优先级 |
| GET | `/api/admin/api-keys` | API Key 列表 |
| POST | `/api/admin/api-keys` | 创建 API Key |
| DELETE | `/api/admin/api-keys/{id}` | 吊销 API Key |
| POST | `/api/admin/api-keys/{id}/enable` | 启用 |
| POST | `/api/admin/api-keys/{id}/disable` | 禁用 |
| PUT | `/api/admin/api-keys/{id}/quota` | 设置额度 |
| POST | `/api/admin/api-keys/{id}/reset-usage` | 重置用量 |
| GET | `/api/admin/api-keys/usage-logs` | 消费日志 |
| GET | `/api/admin/groups` | 分组列表 |
| POST | `/api/admin/groups` | 创建分组 |
| PUT | `/api/admin/groups/{id}` | 更新分组 |
| DELETE | `/api/admin/groups/{id}` | 删除分组 |
| GET | `/api/admin/config/load-balancing-mode` | 获取负载均衡模式 |
| PUT | `/api/admin/config/load-balancing-mode` | 设置负载均衡模式 |

### 其他

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/docs` | Swagger UI（自动生成） |

## 项目结构

```
kiro2api/
├── app/
│   ├── api/                          # API 路由
│   │   ├── v1/
│   │   │   ├── anthropic/            # Anthropic 兼容端点
│   │   │   │   ├── messages.py       # POST /v1/messages
│   │   │   │   ├── messages_cc.py    # POST /cc/v1/messages
│   │   │   │   ├── models.py         # GET /v1/models
│   │   │   │   ├── count_tokens.py   # POST /v1/messages/count_tokens
│   │   │   │   └── router.py
│   │   │   ├── openai/               # OpenAI 兼容端点
│   │   │   │   ├── chat_completions.py
│   │   │   │   └── router.py
│   │   │   └── admin/                # Admin API
│   │   │       ├── credentials.py
│   │   │       ├── api_keys.py
│   │   │       ├── groups.py
│   │   │       ├── config.py
│   │   │       └── router.py
│   │   └── dependencies.py           # 公共依赖项
│   ├── core/                         # 核心配置
│   │   ├── config.py                 # pydantic-settings 配置
│   │   ├── database.py               # 异步 SQLAlchemy 引擎
│   │   └── security.py               # API Key 哈希与验证
│   ├── models/                       # ORM 模型
│   │   ├── base.py
│   │   ├── credential.py             # 凭据表
│   │   ├── group.py                  # 分组表
│   │   ├── api_key.py                # API Key 表
│   │   └── usage_log.py              # 消费日志表
│   ├── schemas/                      # Pydantic Schema
│   │   ├── anthropic.py              # Anthropic API 类型
│   │   ├── openai.py                 # OpenAI API 类型
│   │   ├── credential.py
│   │   ├── api_key.py
│   │   ├── group.py
│   │   ├── admin.py
│   │   └── error.py
│   ├── services/                     # 业务逻辑
│   │   ├── token_manager.py          # Token 管理（单/多凭据）
│   │   ├── kiro_provider.py          # Kiro API 调用 + 重试
│   │   ├── converter.py              # Anthropic ↔ Kiro 协议转换
│   │   ├── stream.py                 # AWS Event Stream 解码 + SSE 转换
│   │   ├── websearch.py              # WebSearch → MCP
│   │   ├── credential_service.py
│   │   ├── api_key_service.py
│   │   ├── group_service.py
│   │   └── usage_logger.py           # 异步消费日志
│   ├── middleware/                    # 中间件
│   │   ├── auth.py                   # 外部 API Key 认证
│   │   └── admin_auth.py             # Admin API Key 认证
│   ├── utils/                        # 工具类
│   │   ├── http_client.py            # httpx 客户端构建器
│   │   ├── machine_id.py             # 设备指纹生成
│   │   └── helpers.py                # 通用工具函数
│   └── main.py                       # 应用入口 + lifespan
├── alembic/                          # 数据库迁移
├── data/                             # SQLite 数据文件
├── pyproject.toml
├── alembic.ini
├── .env.example
└── README.md
```

## 配置说明

所有配置项通过环境变量或 `.env` 文件设置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `REGION` | `us-east-1` | 默认区域 |
| `AUTH_REGION` | (同 REGION) | Token 刷新区域 |
| `API_REGION` | (同 REGION) | API 请求区域 |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/kiro2api.db` | 数据库连接 |
| `ADMIN_API_KEY` | (空) | Admin API 密钥，留空则不鉴权 |
| `REQUIRE_API_KEY` | `false` | 是否要求外部 API Key |
| `LOAD_BALANCING_MODE` | `priority` | 负载均衡：`priority` / `balanced` |
| `PROXY_URL` | (空) | 全局代理（支持 http/socks5） |
| `KIRO_VERSION` | `0.9.2` | Kiro IDE 版本伪装 |

## 支持的模型

| 模型 ID | 映射到 Kiro |
|---|---|
| `claude-sonnet-4-5-*` / `claude-3-5-sonnet-*` | `claude-sonnet-4.5` |
| `claude-opus-4-5-*` | `claude-opus-4.5` |
| `claude-opus-4-*` (非 4.5) | `claude-opus-4.6` |
| `claude-haiku-4-5-*` / `claude-3-5-haiku-*` | `claude-haiku-4.5` |

模型名称末尾加 `-thinking` 后缀会自动启用扩展思考模式。

## 负载均衡模式

- **priority** — 始终使用优先级最高（数字最小）的可用凭据
- **balanced** — Least-Used 策略，选择成功调用次数最少的凭据，平局按优先级

## 故障转移机制

1. 每个凭据最多连续失败 **3 次**后自动禁用
2. 跨凭据总计最多重试 **9 次**
3. 指数退避（200ms ~ 2s）+ 随机抖动
4. 所有凭据自动禁用后触发**自愈**（重置并重新启用）
5. 额度用尽（402 MONTHLY_REQUEST_COUNT）立即禁用，不触发自愈

## 参考项目

- [kiro.rs](../../../kiro.rs) — Rust 参考实现
- [kiro-account-manager](../../../kiro-account-manager) — Tauri 桌面应用

## License

MIT
