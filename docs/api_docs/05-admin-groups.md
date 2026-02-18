# Admin API — 分组管理

所有分组管理端点的路径前缀为 `/api/admin/groups`。

当配置了 `ADMIN_API_KEY` 时，需要在请求头中传入 `x-admin-key`。

## 分组概念

分组用于隔离凭据池。一个分组包含若干凭据，API Key 可以绑定到特定分组，从而只使用该分组内的凭据。

- 未绑定分组的凭据属于**默认池**，所有未绑定分组的 API Key 都可使用
- 绑定了分组的 API Key **只能使用该分组内的凭据**
- 每个分组可以独立设置负载均衡模式

---

## GET /api/admin/groups

列出所有分组。

### 请求

无请求体。

### 响应

```json
[
  {
    "id": 1,
    "name": "生产环境",
    "description": "Pro 账号专用",
    "load_balancing_mode": "balanced",
    "credential_count": 3,
    "api_key_count": 2,
    "created_at": "2026-02-18T03:00:00",
    "updated_at": "2026-02-18T04:00:00"
  }
]
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer | 分组 ID（自增主键） |
| `name` | string | 分组名称 |
| `description` | string\|null | 分组描述 |
| `load_balancing_mode` | string\|null | 分组级负载均衡模式。`null` 表示使用全局配置 |
| `credential_count` | integer | 分组内凭据数量 |
| `api_key_count` | integer | 绑定到此分组的 API Key 数量 |
| `created_at` | string\|null | 创建时间（ISO 8601） |
| `updated_at` | string\|null | 最后更新时间（ISO 8601） |

---

## POST /api/admin/groups

创建新分组。

### 请求

```json
{
  "name": "生产环境",
  "description": "Pro 账号专用",
  "load_balancing_mode": "balanced"
}
```

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|---|---|---|---|---|
| `name` | string | ✅ | — | 分组名称 |
| `description` | string | 否 | `null` | 分组描述 |
| `load_balancing_mode` | string | 否 | `null` | 负载均衡模式：`"priority"` / `"balanced"`。`null` 使用全局配置 |

### 响应

```json
{
  "id": 1,
  "name": "生产环境",
  "message": "分组已创建"
}
```

---

## PUT /api/admin/groups/{group_id}

更新分组信息。只需传入要修改的字段。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `group_id` | path | integer | 分组 ID |

```json
{
  "name": "新名称",
  "description": "新描述",
  "load_balancing_mode": "priority"
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `name` | string | 否 | 新的分组名称 |
| `description` | string | 否 | 新的描述 |
| `load_balancing_mode` | string | 否 | 新的负载均衡模式：`"priority"` / `"balanced"` / `null` |

### 响应

```json
{
  "success": true,
  "message": "分组已更新"
}
```

---

## DELETE /api/admin/groups/{group_id}

删除分组。**如果分组内仍有凭据或绑定了 API Key，则无法删除。**

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `group_id` | path | integer | 分组 ID |

### 响应

**成功：**

```json
{
  "success": true,
  "message": "分组已删除"
}
```

**失败（有关联资源）：**

```json
{
  "detail": "分组下仍有凭据或 API Key，无法删除"
}
```

### 请求示例

```bash
# 创建分组
curl -X POST http://127.0.0.1:8000/api/admin/groups \
  -H "Content-Type: application/json" \
  -d '{"name":"Pro账号池","description":"仅限Pro订阅","load_balancing_mode":"balanced"}'

# 列出分组
curl http://127.0.0.1:8000/api/admin/groups

# 更新分组
curl -X PUT http://127.0.0.1:8000/api/admin/groups/1 \
  -H "Content-Type: application/json" \
  -d '{"description":"已更新描述"}'

# 删除分组
curl -X DELETE http://127.0.0.1:8000/api/admin/groups/1
```
