# Admin API — 凭据管理

所有凭据管理端点的路径前缀为 `/api/admin/credentials`。

当配置了 `ADMIN_API_KEY` 时，需要在请求头中传入 `x-admin-key`。

---

## GET /api/admin/credentials

获取所有凭据列表。

### 请求

无请求体。

### 响应

```json
[
  {
    "id": 1,
    "auth_method": "idc",
    "email": "user@example.com",
    "subscription_title": "KIRO FREE",
    "priority": 0,
    "is_disabled": false,
    "group_id": null,
    "region": "us-east-1",
    "auth_region": null,
    "api_region": null,
    "proxy_url": null,
    "fail_count": 0,
    "last_used_at": "2026-02-18T04:00:00",
    "expires_at": "2026-02-18T12:52:57",
    "created_at": "2026-02-18T03:55:00"
  }
]
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer | 凭据 ID（自增主键） |
| `auth_method` | string | 认证方式：`"social"` 或 `"idc"` |
| `email` | string\|null | 关联的邮箱地址（Token 刷新后从上游获取） |
| `subscription_title` | string\|null | 订阅类型：`"KIRO FREE"` / `"KIRO PRO+"` 等（Token 刷新后从上游获取） |
| `priority` | integer | 优先级，数字越小越高（0 为最高） |
| `is_disabled` | boolean | 是否已禁用 |
| `group_id` | integer\|null | 所属分组 ID（null 表示默认分组） |
| `region` | string\|null | 凭据级 Region |
| `auth_region` | string\|null | 凭据级 Auth Region（Token 刷新用） |
| `api_region` | string\|null | 凭据级 API Region（API 请求用） |
| `proxy_url` | string\|null | 凭据级代理地址 |
| `fail_count` | integer | 连续失败次数（达到 3 次自动禁用） |
| `last_used_at` | string\|null | 上次使用时间（ISO 8601） |
| `expires_at` | string\|null | Token 过期时间 |
| `created_at` | string\|null | 创建时间（ISO 8601） |

---

## POST /api/admin/credentials

添加新凭据。

### 请求

**IdC (BuilderId) 凭据：**

```json
{
  "refresh_token": "aorAAAAA...",
  "auth_method": "idc",
  "client_id": "WWf3TGfG...",
  "client_secret": "eyJraWQi...",
  "region": "us-east-1"
}
```

**Social 凭据：**

```json
{
  "refresh_token": "eyJjdHki...",
  "auth_method": "social"
}
```

**完整请求体（含所有可选字段）：**

```json
{
  "refresh_token": "刷新令牌",
  "auth_method": "idc",
  "client_id": "OIDC Client ID",
  "client_secret": "OIDC Client Secret",
  "profile_arn": "arn:aws:...",
  "group_id": 1,
  "priority": 0,
  "region": "us-east-1",
  "auth_region": "us-east-1",
  "api_region": "us-east-1",
  "machine_id": "de6daefc-b21f-4cb1-857e-37b7cd757d07",
  "proxy_url": "socks5://127.0.0.1:1080",
  "proxy_username": "",
  "proxy_password": ""
}
```

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|---|---|---|---|---|
| `refresh_token` | string | ✅ | — | 刷新令牌。IdC 凭据约 233 字符，Social 凭据约 200+ 字符 |
| `auth_method` | string | 否 | `"social"` | 认证方式：`"social"` / `"idc"` / `"builder-id"` / `"iam"`。后三者均映射为 IdC |
| `client_id` | string | IdC 必需 | `null` | AWS SSO OIDC 客户端 ID（约 35 字符） |
| `client_secret` | string | IdC 必需 | `null` | AWS SSO OIDC 客户端密钥（JWT 格式，约 4780 字符） |
| `profile_arn` | string | 否 | `null` | AWS Profile ARN |
| `group_id` | integer | 否 | `null` | 绑定的分组 ID。null 表示默认分组 |
| `priority` | integer | 否 | `0` | 优先级，数字越小越高 |
| `region` | string | 否 | `null` | 凭据级 Region（覆盖全局）。默认为全局 `REGION` 或 `"us-east-1"` |
| `auth_region` | string | 否 | `null` | 凭据级 Auth Region（Token 刷新用）。回退到 `region` |
| `api_region` | string | 否 | `null` | 凭据级 API Region（API 请求用）。回退到全局 `API_REGION` |
| `machine_id` | string | 否 | `null` | 设备指纹。支持 64 字符十六进制或 UUID 格式。为空时自动从 refresh_token 派生 |
| `proxy_url` | string | 否 | `null` | 凭据级代理。`"direct"` 表示不使用代理。支持 `http://`、`https://`、`socks5://` |
| `proxy_username` | string | 否 | `null` | 代理用户名 |
| `proxy_password` | string | 否 | `null` | 代理密码 |

### 响应

```json
{
  "id": 1,
  "message": "凭据已添加"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer | 新创建的凭据 ID |
| `message` | string | 操作结果描述 |

> **注意：** 添加凭据后需要重启服务以将其加载到内存中的 Token 管理器。

---

## DELETE /api/admin/credentials/{credential_id}

删除指定凭据。**要求先禁用**才能删除。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `credential_id` | path | integer | 凭据 ID |

### 响应

**成功：**

```json
{
  "success": true,
  "message": "凭据已删除"
}
```

**失败（未禁用）：**

```json
{
  "detail": "请先禁用凭据再删除"
}
```

---

## POST /api/admin/credentials/{credential_id}/disable

禁用指定凭据。禁用后该凭据不参与负载均衡。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `credential_id` | path | integer | 凭据 ID |

### 响应

```json
{
  "success": true,
  "message": "凭据已禁用"
}
```

---

## POST /api/admin/credentials/{credential_id}/enable

启用指定凭据。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `credential_id` | path | integer | 凭据 ID |

### 响应

```json
{
  "success": true,
  "message": "凭据已启用"
}
```

---

## POST /api/admin/credentials/{credential_id}/reset

重置凭据失败计数并重新启用。用于凭据因连续失败被自动禁用后的恢复。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `credential_id` | path | integer | 凭据 ID |

### 响应

```json
{
  "success": true,
  "message": "凭据已重置并启用"
}
```

---

## PUT /api/admin/credentials/{credential_id}/priority

设置凭据优先级。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `credential_id` | path | integer | 凭据 ID |
| `priority` | query | integer | 新优先级值（数字越小越高，0 为最高） |

**示例：**

```bash
curl -X PUT "http://127.0.0.1:8000/api/admin/credentials/1/priority?priority=5"
```

### 响应

```json
{
  "success": true,
  "message": "优先级已设置为 5"
}
```
