# Admin API — API Key 管理

所有 API Key 管理端点的路径前缀为 `/api/admin/api-keys`。

当配置了 `ADMIN_API_KEY` 时，需要在请求头中传入 `x-admin-key`。

---

## GET /api/admin/api-keys

列出所有 API Key。

### 请求

无请求体。

### 响应

```json
[
  {
    "id": 1,
    "name": "测试 Key",
    "key_prefix": "sk-abc1...",
    "group_id": null,
    "is_enabled": true,
    "token_quota": 0,
    "tokens_used": 1500,
    "request_count": 10,
    "last_used_at": "2026-02-18T04:00:00",
    "created_at": "2026-02-18T03:00:00"
  }
]
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer | API Key ID（自增主键） |
| `name` | string | Key 名称（用于标识用途） |
| `key_prefix` | string | Key 前缀（如 `sk-abc1...`），用于辨识，不含完整密钥 |
| `group_id` | integer\|null | 绑定的分组 ID。null 表示使用所有凭据 |
| `is_enabled` | boolean | 是否已启用 |
| `token_quota` | integer | Token 额度上限。`0` 表示无限制 |
| `tokens_used` | integer | 已使用的 Token 数量 |
| `request_count` | integer | 累计请求次数 |
| `last_used_at` | string\|null | 上次使用时间（ISO 8601） |
| `created_at` | string\|null | 创建时间（ISO 8601） |

> **注意：** 完整的 API Key 值仅在创建时返回一次，之后只能看到 `key_prefix`。

---

## POST /api/admin/api-keys

创建新的 API Key。

### 请求

```json
{
  "name": "测试 Key",
  "group_id": null,
  "token_quota": 0
}
```

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|---|---|---|---|---|
| `name` | string | ✅ | — | Key 名称，用于标识用途 |
| `group_id` | integer | 否 | `null` | 绑定的分组 ID。绑定后此 Key 只能使用该分组内的凭据 |
| `token_quota` | integer | 否 | `0` | Token 额度上限。`0` 表示无限制，大于 0 时超出额度的请求会被拒绝 |

### 响应

```json
{
  "id": 1,
  "name": "测试 Key",
  "raw_key": "sk-abc123def456ghi789jkl012mno345pq",
  "key_prefix": "sk-abc1...",
  "group_id": null,
  "token_quota": 0,
  "created_at": "2026-02-18T03:00:00"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer | 新创建的 API Key ID |
| `name` | string | Key 名称 |
| `raw_key` | string | **完整的 API Key 值（⚠️ 仅此次返回，请立即保存）** |
| `key_prefix` | string | Key 前缀 |
| `group_id` | integer\|null | 绑定的分组 ID |
| `token_quota` | integer | Token 额度上限 |
| `created_at` | string | 创建时间 |

> **重要：** `raw_key` 是原始密钥，数据库中仅存储其 SHA-256 哈希值。创建后无法再次获取原始值。

---

## DELETE /api/admin/api-keys/{key_id}

吊销（永久删除）API Key。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `key_id` | path | integer | API Key ID |

### 响应

```json
{
  "success": true,
  "message": "API Key 已吊销"
}
```

---

## POST /api/admin/api-keys/{key_id}/enable

启用 API Key。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `key_id` | path | integer | API Key ID |

### 响应

```json
{
  "success": true,
  "message": "API Key 已启用"
}
```

---

## POST /api/admin/api-keys/{key_id}/disable

禁用 API Key。禁用后使用此 Key 的请求会返回 403。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `key_id` | path | integer | API Key ID |

### 响应

```json
{
  "success": true,
  "message": "API Key 已禁用"
}
```

---

## PUT /api/admin/api-keys/{key_id}/quota

设置 Token 额度上限。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `key_id` | path | integer | API Key ID |
| `token_quota` | query | integer | 新的 Token 额度。`0` 表示无限制 |

**示例：**

```bash
# 设置额度为 100000 tokens
curl -X PUT "http://127.0.0.1:8000/api/admin/api-keys/1/quota?token_quota=100000"

# 取消额度限制
curl -X PUT "http://127.0.0.1:8000/api/admin/api-keys/1/quota?token_quota=0"
```

### 响应

```json
{
  "success": true,
  "message": "Token 额度已设置为 100000"
}
```

**额度检查逻辑：** 每次请求前检查 `tokens_used < token_quota`（当 `token_quota > 0` 时）。超出额度返回 403。

---

## POST /api/admin/api-keys/{key_id}/reset-usage

重置已使用的 Token 数量（归零）。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `key_id` | path | integer | API Key ID |

### 响应

```json
{
  "success": true,
  "message": "已用 Token 数已重置"
}
```

---

## GET /api/admin/api-keys/usage-logs

获取消费日志列表。

### 请求

| 参数 | 位置 | 类型 | 必需 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `api_key_id` | query | integer | 否 | `null` | 按 API Key ID 过滤。不传则返回全部 |
| `limit` | query | integer | 否 | `100` | 每页条数（1-1000） |
| `offset` | query | integer | 否 | `0` | 偏移量 |

**示例：**

```bash
# 获取最近 50 条日志
curl "http://127.0.0.1:8000/api/admin/api-keys/usage-logs?limit=50"

# 按 API Key 过滤
curl "http://127.0.0.1:8000/api/admin/api-keys/usage-logs?api_key_id=1&limit=20"
```

### 响应

```json
{
  "total": 150,
  "items": [
    {
      "id": 1,
      "api_key_id": 1,
      "credential_id": 1,
      "model": "claude-sonnet-4-5-20250514",
      "endpoint": "/v1/messages",
      "client_ip": "127.0.0.1",
      "input_tokens": 2055,
      "output_tokens": 15,
      "total_tokens": 2070,
      "status_code": 200,
      "duration_ms": 3200,
      "created_at": "2026-02-18T04:00:00"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `total` | integer | 符合条件的总记录数 |
| `items[].id` | integer | 日志 ID |
| `items[].api_key_id` | integer\|null | 关联的 API Key ID |
| `items[].credential_id` | integer\|null | 使用的凭据 ID |
| `items[].model` | string | 请求的模型名称（用户传入的原始值） |
| `items[].endpoint` | string | 请求端点路径 |
| `items[].client_ip` | string\|null | 客户端 IP 地址 |
| `items[].input_tokens` | integer | 输入 Token 数 |
| `items[].output_tokens` | integer | 输出 Token 数 |
| `items[].total_tokens` | integer | 总 Token 数 |
| `items[].status_code` | integer | HTTP 响应状态码 |
| `items[].duration_ms` | integer | 请求处理耗时（毫秒） |
| `items[].created_at` | string | 记录创建时间（ISO 8601） |
