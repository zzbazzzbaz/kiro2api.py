# 分组管理规范

## 目的
通过凭据池分组，实现隔离的凭据池、分组级负载均衡、以及 API Key 与特定分组的绑定。

## 需求

### 需求：分组 CRUD
系统应当（SHALL）支持凭据分组的创建、读取、更新和删除。

#### 场景：创建分组
- 假设（GIVEN）提供一个唯一的分组名称
- 当（WHEN）调用 POST `/api/admin/groups` 时
- 则（THEN）创建一个带有自增 ID 的新分组

#### 场景：分组名称重复
- 假设（GIVEN）分组名称已存在
- 当（WHEN）调用 POST `/api/admin/groups` 时
- 则（THEN）返回 400 错误

#### 场景：删除有关联的分组
- 假设（GIVEN）分组下存在关联的凭据或 API Key
- 当（WHEN）调用 DELETE `/api/admin/groups/{id}` 时
- 则（THEN）返回 400 错误："需先移除关联凭据和 Key"

#### 场景：删除空分组
- 假设（GIVEN）分组下没有关联的凭据或 API Key
- 当（WHEN）调用 DELETE `/api/admin/groups/{id}` 时
- 则（THEN）分组被删除

### 需求：分组级负载均衡
每个分组应当（SHALL）拥有独立的负载均衡模式配置。

#### 场景：优先级模式
- 假设（GIVEN）分组的 `load_balancing_mode = "priority"`
- 当（WHEN）从该分组选择凭据时
- 则（THEN）选择已启用且 `priority` 值最小的凭据

#### 场景：均衡模式
- 假设（GIVEN）分组的 `load_balancing_mode = "balanced"`
- 当（WHEN）从该分组选择凭据时
- 则（THEN）选择已启用且 `success_count` 最小的凭据

### 需求：分组隔离
系统必须（MUST）确保不同分组的凭据池完全隔离。

#### 场景：分组内故障转移
- 假设（GIVEN）分组 A 中凭据 #1 失败、凭据 #2 可用
- 当（WHEN）凭据 #1 的请求失败时
- 则（THEN）故障转移切换至分组 A 内的凭据 #2
- 且（AND）绝不考虑其他分组的凭据

#### 场景：按 API Key 路由请求
- 假设（GIVEN）API Key `sk-ext-aaa` 绑定到分组 A
- 当（WHEN）携带 `sk-ext-aaa` 的请求到达时
- 则（THEN）仅使用分组 A 的凭据处理该请求
