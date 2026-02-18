# kiro2api API 文档 — 通用说明

## 基础信息

| 项目 | 值 |
|---|---|
| 基础 URL | `http://{HOST}:{PORT}` |
| 默认地址 | `http://127.0.0.1:8000` |
| 协议 | HTTP/1.1 |
| 内容类型 | `application/json` |
| 流式响应 | `text/event-stream` (SSE) |

## 认证

### 外部 API Key 认证

当 `.env` 中设置 `REQUIRE_API_KEY=true` 时，所有 `/v1/*` 和 `/cc/v1/*` 端点需要认证。

**传递方式（二选一）：**

| 方式 | Header | 格式 |
|---|---|---|
| x-api-key | `x-api-key: sk-xxx` | 直接传入 |
| Bearer Token | `Authorization: Bearer sk-xxx` | 标准 Bearer 格式 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "x-api-key: sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-5-20250514","max_tokens":100,"messages":[{"role":"user","content":"Hi"}]}'
```

**认证失败响应：**

```json
{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "无效的 API Key"
  }
}
```

### Admin API Key 认证

当 `.env` 中设置了 `ADMIN_API_KEY` 时，所有 `/api/admin/*` 端点需要认证。

**传递方式：**

```
x-admin-key: 你的admin密钥
```

**未配置 ADMIN_API_KEY 时：** Admin API 无需认证（开发模式）。

## 错误响应格式

### Anthropic 兼容格式（/v1/* 端点）

```json
{
  "type": "error",
  "error": {
    "type": "错误类型",
    "message": "错误描述"
  }
}
```

| 错误类型 | HTTP 状态码 | 说明 |
|---|---|---|
| `invalid_request_error` | 400 | 请求参数无效（如不支持的模型、空消息等） |
| `authentication_error` | 401 | API Key 无效或未提供 |
| `permission_error` | 403 | API Key 已禁用或额度用尽 |
| `api_error` | 502 | 上游 Kiro API 调用失败 |
| `overloaded_error` | 503 | 服务不可用（KiroProvider 未初始化等） |

### OpenAI 兼容格式（/v1/chat/completions 端点）

```json
{
  "error": {
    "message": "错误描述",
    "type": "错误类型"
  }
}
```

### Admin API 格式

**成功响应：**

```json
{
  "success": true,
  "message": "操作描述"
}
```

**错误响应：**

```json
{
  "detail": "错误描述"
}
```

| HTTP 状态码 | 说明 |
|---|---|
| 400 | 请求参数无效或业务规则冲突 |
| 401 | Admin API Key 无效 |
| 404 | 资源不存在 |

## 支持的模型

### 外部模型 ID → Kiro 内部模型映射

| 外部模型 ID（用户传入） | Kiro 内部模型 ID | 说明 |
|---|---|---|
| `claude-sonnet-4-5-20250514` | `claude-sonnet-4.5` | 推荐 |
| `claude-sonnet-4-20250514` | `claude-sonnet-4.5` | |
| `claude-3-5-sonnet-20241022` | `claude-sonnet-4.5` | 旧版兼容 |
| `claude-3-5-sonnet-20240620` | `claude-sonnet-4.5` | 旧版兼容 |
| `claude-opus-4-20250514` | `claude-opus-4.6` | |
| `claude-3-opus-20240229` | `claude-opus-4.6` | 旧版兼容 |
| `claude-opus-4-5-*` | `claude-opus-4.5` | 含 "4-5" 或 "4.5" |
| `claude-haiku-4-5-20250514` | `claude-haiku-4.5` | |
| `claude-3-5-haiku-20241022` | `claude-haiku-4.5` | 旧版兼容 |
| `claude-3-haiku-20240307` | `claude-haiku-4.5` | 旧版兼容 |

**映射规则：** 模型名称中包含 `sonnet`/`opus`/`haiku` 关键词即可匹配，不限于上表中的具体 ID。

**Thinking 后缀：** 模型名末尾加 `-thinking` 会自动启用扩展思考模式（budget_tokens=20000）。例如 `claude-sonnet-4-5-20250514-thinking`。

## 通用端点

### GET /health

健康检查。

**响应：**

```json
{
  "status": "ok"
}
```

### GET /docs

Swagger UI 自动生成的交互式 API 文档。
