# Token 管理规范

## 目的
自动管理 OAuth Token 生命周期，包括过期检测、Social 和 IdC 两种认证方式的 Token 刷新、以及刷新后的持久化。

## 需求

### 需求：Token 过期检测
系统应当（SHALL）在发起 API 调用前检测 Token 是否过期或即将过期。

#### 场景：Token 已过期
- 假设（GIVEN）凭据的 `expires_at` 已在过去
- 当（WHEN）请求获取 Token 用于 API 调用时
- 则（THEN）先刷新 Token 再使用

#### 场景：Token 即将在 5 分钟内过期
- 假设（GIVEN）凭据的 `expires_at` 在未来 5 分钟以内
- 当（WHEN）请求获取 Token 用于 API 调用时
- 则（THEN）主动刷新 Token

#### 场景：Token 仍然有效
- 假设（GIVEN）凭据的 `expires_at` 在 5 分钟之后
- 当（WHEN）请求获取 Token 时
- 则（THEN）直接返回现有 `access_token`，不执行刷新

### 需求：Social Token 刷新
系统应当（SHALL）通过 OIDC 端点刷新 Social（Google/Github）OAuth Token。

#### 场景：刷新成功
- 假设（GIVEN）一个 Social 凭据持有有效的 `refresh_token`
- 当（WHEN）触发刷新时
- 则（THEN）向 `https://oidc.{auth_region}.amazonaws.com/token` 发送 POST，携带 `grant_type=refresh_token`
- 且（AND）新的 `access_token`、`refresh_token` 和 `expires_at` 被持久化到数据库

#### 场景：refresh_token 无效
- 假设（GIVEN）一个 Social 凭据的 `refresh_token` 已过期或被撤销
- 当（WHEN）触发刷新时
- 则（THEN）记录错误日志
- 且（AND）该凭据的 `failure_count` 递增

### 需求：IdC Token 刷新
系统应当（SHALL）通过携带客户端凭证的 OIDC 端点刷新 IdC（BuilderId）OAuth Token。

#### 场景：刷新成功
- 假设（GIVEN）一个 IdC 凭据持有有效的 `refresh_token`、`client_id` 和 `client_secret`
- 当（WHEN）触发刷新时
- 则（THEN）向 `https://oidc.{auth_region}.amazonaws.com/token` 发送 POST，携带 `grant_type=refresh_token`、`client_id` 和 `client_secret`
- 且（AND）新 Token 被持久化

### 需求：并发刷新保护
系统必须（MUST）防止同一凭据被并发刷新。

#### 场景：并发请求同时触发刷新
- 假设（GIVEN）两个并发请求同时检测到 Token 已过期
- 当（WHEN）两者均尝试刷新时
- 则（THEN）仅执行一次实际刷新（通过 `asyncio.Lock`）
- 且（AND）两个请求都能获得刷新后的 Token

### 需求：Region 配置
系统应当（SHALL）支持凭据级和全局的 Region 配置，用于选择 Token 刷新端点。

#### 场景：凭据级 auth_region
- 假设（GIVEN）凭据配置了 `auth_region = "eu-west-1"`
- 当（WHEN）触发 Token 刷新时
- 则（THEN）OIDC 端点使用 `eu-west-1`

#### 场景：回退到全局 Region
- 假设（GIVEN）凭据未配置 `auth_region`
- 当（WHEN）触发 Token 刷新时
- 则（THEN）OIDC 端点使用全局配置 `AUTH_REGION`（或 `REGION`）

### 需求：Token 持久化
系统应当（SHALL）在刷新成功后立即将新 Token 写入数据库。

#### 场景：持久化成功
- 假设（GIVEN）Token 刷新成功
- 当（WHEN）收到新 Token 时
- 则（THEN）`access_token`、`refresh_token`（如有变化）和 `expires_at` 被写入数据库
