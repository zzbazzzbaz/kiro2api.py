# 凭据管理规范

## 目的
管理 Kiro OAuth 凭据（Token），包括存储、生命周期、多凭据故障转移、以及上游账号状态检测。

## 需求

### 需求：凭据存储
系统应当（SHALL）将凭据持久化到 SQLite 数据库，包含 OAuth Token 刷新所需的全部字段。

#### 场景：Social 凭据
- 假设（GIVEN）一个 Social（Google/Github）OAuth 凭据
- 当（WHEN）存储时
- 则（THEN）持久化 `refresh_token`、`auth_method = "social"` 及可选的 `profile_arn`

#### 场景：IdC 凭据
- 假设（GIVEN）一个 IdC（BuilderId）OAuth 凭据
- 当（WHEN）存储时
- 则（THEN）持久化 `refresh_token`、`auth_method = "idc"`、`client_id`、`client_secret` 和 `region`

### 需求：凭据优先级与排序
系统应当（SHALL）支持基于优先级的凭据排序。

#### 场景：优先级排序
- 假设（GIVEN）凭据的优先级分别为 0、1、2
- 当（WHEN）在 "priority" 模式下选择凭据时
- 则（THEN）优先选择优先级数字最小的凭据

#### 场景：均衡排序
- 假设（GIVEN）凭据处于 "balanced" 模式
- 当（WHEN）选择凭据时
- 则（THEN）选择 `success_count` 最小的凭据

### 需求：凭据禁用
系统应当（SHALL）支持禁用凭据使其不参与选择。

#### 场景：禁用当前活跃凭据
- 假设（GIVEN）当前活跃凭据被禁用
- 当（WHEN）下一个请求到达时
- 则（THEN）系统切换到同一分组内的下一个可用凭据

#### 场景：所有凭据被禁用
- 假设（GIVEN）某分组内所有凭据均被禁用
- 当（WHEN）该分组的请求到达时
- 则（THEN）返回 529 overloaded_error 响应

### 需求：失败追踪与自动禁用
系统宜（SHOULD）跟踪连续失败次数，并在多次失败后自动禁用凭据。

#### 场景：失败计数递增
- 假设（GIVEN）凭据的 `failure_count = 2`
- 当（WHEN）使用该凭据的 API 调用失败时
- 则（THEN）`failure_count` 递增为 3

#### 场景：成功重置失败计数
- 假设（GIVEN）凭据的 `failure_count > 0`
- 当（WHEN）使用该凭据的 API 调用成功时
- 则（THEN）`failure_count` 重置为 0
- 且（AND）`success_count` 递增

### 需求：凭据 CRUD（通过 Admin API）
系统应当（SHALL）提供凭据管理的 Admin API 端点。

#### 场景：添加凭据
- 假设（GIVEN）提供有效的 `refresh_token` 和 `auth_method`
- 当（WHEN）调用 POST `/api/admin/credentials` 时
- 则（THEN）创建一个自增 ID 的新凭据
- 且（AND）主动获取订阅等级信息

#### 场景：删除凭据
- 假设（GIVEN）一个已禁用的凭据
- 当（WHEN）调用 DELETE `/api/admin/credentials/{id}` 时
- 则（THEN）从数据库中移除该凭据

#### 场景：删除未禁用的凭据
- 假设（GIVEN）一个未被禁用的凭据
- 当（WHEN）调用 DELETE `/api/admin/credentials/{id}` 时
- 则（THEN）返回 400 错误："请先禁用凭据"

#### 场景：重置并重新启用
- 假设（GIVEN）一个已禁用且 `failure_count > 0` 的凭据
- 当（WHEN）调用 POST `/api/admin/credentials/{id}/reset` 时
- 则（THEN）`failure_count` 重置为 0
- 且（AND）`disabled` 设为 false

### 需求：凭据级代理
系统应当（SHALL）支持每个凭据独立配置代理。

#### 场景：凭据使用自定义代理
- 假设（GIVEN）凭据配置了 `proxy_url = "socks5://1.2.3.4:1080"`
- 当（WHEN）使用该凭据进行 API 调用时
- 则（THEN）使用凭据的代理而非全局代理

#### 场景：凭据使用 "direct" 代理
- 假设（GIVEN）凭据配置了 `proxy_url = "direct"`
- 当（WHEN）使用该凭据进行 API 调用时
- 则（THEN）不使用任何代理，即使全局配置了代理

#### 场景：凭据未配置代理
- 假设（GIVEN）凭据的 `proxy_url = None`
- 当（WHEN）使用该凭据进行 API 调用时
- 则（THEN）使用全局代理配置（如有）

### 需求：账号状态检测
系统应当（SHALL）通过上游 `getUsageLimits` API 检测 Kiro 账号状态（正常/已封禁）。

#### 场景：正常账号
- 假设（GIVEN）凭据对应一个有效的 Kiro 账号
- 当（WHEN）`getUsageLimits` 返回成功时
- 则（THEN）`account_status = "normal"`，并缓存 `usage_data`

#### 场景：已封禁账号
- 假设（GIVEN）凭据对应一个已封禁的 Kiro 账号
- 当（WHEN）`getUsageLimits` 返回 `BANNED:*` 错误时
- 则（THEN）`account_status = "banned"`，且自动禁用该凭据

### 需求：订阅等级过滤
系统应当（SHALL）根据订阅等级过滤模型访问权限。

#### 场景：免费版使用 Opus 模型
- 假设（GIVEN）凭据的 `subscription_title = "KIRO FREE"`
- 当（WHEN）收到 Opus 模型的请求时
- 则（THEN）拒绝请求，返回错误提示 Opus 需要付费订阅

#### 场景：付费版使用任意模型
- 假设（GIVEN）凭据的 `subscription_title = "KIRO PRO+"`
- 当（WHEN）收到任意模型的请求时
- 则（THEN）正常处理请求
