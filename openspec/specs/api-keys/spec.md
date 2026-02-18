# API Key 管理规范

## 目的
管理外部 API Key 的完整生命周期，包括生成、吊销、启用/禁用、额度管理和消费统计查询。

## 需求

### 需求：API Key 生成
系统应当（SHALL）生成加密安全的 API Key，并支持绑定到指定分组。

#### 场景：生成新 Key
- 假设（GIVEN）提供有效的 `group_id` 和可选的 `name`
- 当（WHEN）调用 POST `/api/admin/api-keys` 时
- 则（THEN）生成一个新 API Key（例如 `sk-ext-<随机字符串>`）
- 且（AND）明文 Key 仅在响应中返回一次
- 且（AND）数据库中仅存储 SHA-256 哈希值

### 需求：API Key 吊销
系统应当（SHALL）支持吊销 API Key。

#### 场景：删除 Key
- 假设（GIVEN）一个存在的 API Key ID
- 当（WHEN）调用 DELETE `/api/admin/api-keys/{id}` 时
- 则（THEN）该 Key 从数据库中移除
- 且（AND）后续携带该 Key 的请求返回 401

### 需求：API Key 启用/禁用
系统应当（SHALL）支持在不删除的情况下启用或禁用 API Key。

#### 场景：禁用 Key
- 假设（GIVEN）一个已启用的 API Key
- 当（WHEN）调用 POST `/api/admin/api-keys/{id}/enabled`，请求体为 `{"enabled": false}` 时
- 则（THEN）该 Key 被禁用
- 且（AND）后续携带该 Key 的请求返回 401

#### 场景：重新启用 Key
- 假设（GIVEN）一个已禁用的 API Key
- 当（WHEN）调用 POST `/api/admin/api-keys/{id}/enabled`，请求体为 `{"enabled": true}` 时
- 则（THEN）该 Key 被重新启用

### 需求：Token 额度管理
系统应当（SHALL）支持为每个 API Key 配置 Token 使用额度。

#### 场景：设置额度
- 假设（GIVEN）一个 API Key ID 和额度值
- 当（WHEN）调用 POST `/api/admin/api-keys/{id}/quota`，请求体为 `{"token_quota": 500000}` 时
- 则（THEN）该 Key 的额度被更新

#### 场景：移除额度（无限制）
- 假设（GIVEN）一个 API Key ID
- 当（WHEN）调用 POST `/api/admin/api-keys/{id}/quota`，请求体为 `{"token_quota": null}` 时
- 则（THEN）额度被移除，使用不受限制

#### 场景：重置消费计数
- 假设（GIVEN）一个已累积 `tokens_used` 的 API Key
- 当（WHEN）调用 POST `/api/admin/api-keys/{id}/reset-usage` 时
- 则（THEN）`tokens_used` 重置为 0

### 需求：API Key 列表查询
系统应当（SHALL）提供所有 API Key 的列表及其状态和使用统计。

#### 场景：列出所有 Key
- 假设（GIVEN）数据库中存在多个 API Key
- 当（WHEN）调用 GET `/api/admin/api-keys` 时
- 则（THEN）返回所有 Key，包含 `id`、`key_prefix`、`name`、`group_id`、`enabled`、`created_at`、`last_used_at`、`request_count`、`token_quota`、`tokens_used`
- 且（AND）完整的 Key 哈希值不暴露
