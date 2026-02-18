# Admin API — 配置管理

所有配置管理端点的路径前缀为 `/api/admin/config`。

当配置了 `ADMIN_API_KEY` 时，需要在请求头中传入 `x-admin-key`。

---

## GET /api/admin/config/load-balancing-mode

获取当前的负载均衡模式。

### 请求

无请求体。

### 响应

```json
{
  "mode": "priority"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | string | 当前负载均衡模式：`"priority"` 或 `"balanced"` |

**模式说明：**

| 模式 | 策略 | 说明 |
|---|---|---|
| `priority` | 固定优先级 | 始终选择优先级最高（数字最小）的可用凭据 |
| `balanced` | Least-Used | 选择成功调用次数最少的可用凭据，平局时按优先级排序 |

---

## PUT /api/admin/config/load-balancing-mode

设置负载均衡模式。修改会**立即生效**，无需重启。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|---|---|---|---|
| `mode` | query | string | 新的负载均衡模式：`"priority"` 或 `"balanced"` |

**示例：**

```bash
# 切换到均衡模式
curl -X PUT "http://127.0.0.1:8000/api/admin/config/load-balancing-mode?mode=balanced"

# 切换回优先级模式
curl -X PUT "http://127.0.0.1:8000/api/admin/config/load-balancing-mode?mode=priority"
```

### 响应

**成功：**

```json
{
  "success": true,
  "message": "负载均衡模式已设置为 balanced"
}
```

**失败（无效模式）：**

```json
{
  "detail": "无效的负载均衡模式: invalid_mode"
}
```

### 负载均衡详细说明

#### Priority 模式（默认）

```
凭据 A (priority=0) ← 始终选择这个（如果可用）
凭据 B (priority=1)
凭据 C (priority=2)
```

- 始终使用 `priority` 值最小的可用凭据
- 当前凭据被禁用后，自动切换到下一个
- 适合有主备关系的凭据配置

#### Balanced 模式

```
凭据 A (success_count=10)
凭据 B (success_count=5)  ← 选择这个（使用次数最少）
凭据 C (success_count=8)
```

- 选择 `success_count` 最小的可用凭据
- 成功调用次数相同时，按 `priority` 排序
- 适合均匀分散负载、延长每个凭据的额度周期
