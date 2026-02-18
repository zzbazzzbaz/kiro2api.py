# kiro2api Admin UI — OpenSpec

## 1. 项目概述

kiro2api 的管理后台前端，用于管理凭据、API Key、分组、配置和消费日志。

## 2. 技术栈

| 项目 | 选型 |
|---|---|
| 构建工具 | Vite 5 |
| 框架 | React 18 |
| 语言 | JavaScript (JSX) |
| 样式 | Tailwind CSS 3 |
| HTTP 客户端 | fetch (原生) |
| 状态管理 | React hooks (useState/useEffect/useContext) |
| 图标 | Lucide React |
| 通知 | sonner |

## 3. 页面结构

```
App
├── LoginPage              — Admin Key 登录
└── Layout                 — 侧边栏 + 主内容区
    ├── DashboardPage      — 总览统计
    ├── CredentialsPage    — 凭据管理
    ├── ApiKeysPage        — API Key 管理
    ├── GroupsPage         — 分组管理
    └── UsageLogsPage      — 消费日志
```

## 4. 页面功能详细

### 4.1 LoginPage

- 输入 Admin API Key + 后端地址（默认当前域名）
- 存储到 localStorage
- 验证方式：调用 `GET /api/admin/credentials` 检测是否 401

### 4.2 DashboardPage（总览）

统计卡片：
- 凭据总数 / 可用数 / 已禁用数
- API Key 总数 / 已启用数
- 分组总数
- 负载均衡模式（可切换）

### 4.3 CredentialsPage（凭据管理）

功能列表：
- **列表展示**：卡片式，显示 ID、邮箱、订阅类型、优先级、状态、失败计数、最后使用时间
- **添加凭据**：对话框，支持 Social / IdC 两种模式，IdC 需填 client_id/client_secret
- **禁用/启用**：单个操作
- **重置失败**：重置 fail_count 并重新启用
- **删除**：需先禁用
- **设置优先级**：inline 编辑
- **查询余额**：调用 `GET /credentials/{id}/balance`，显示已用/总量/剩余/使用率
- **批量操作**：多选后批量删除、批量验活

### 4.4 ApiKeysPage（API Key 管理）

功能列表：
- **列表展示**：表格式，显示名称、前缀、分组、状态、额度、已用量、请求次数
- **创建 Key**：对话框，输入名称、分组、额度
- **创建成功提示**：显示完整 raw_key，提醒仅此一次
- **启用/禁用**
- **设置额度**
- **重置已用量**
- **吊销（删除）**

### 4.5 GroupsPage（分组管理）

功能列表：
- **列表展示**：表格式，名称、描述、负载均衡模式、凭据数、Key 数
- **创建分组**
- **编辑分组**
- **删除分组**（需无关联资源）

### 4.6 UsageLogsPage（消费日志）

功能列表：
- **表格展示**：模型、端点、Token 用量、状态码、耗时、时间
- **按 API Key 过滤**
- **分页**：limit/offset

## 5. API 对接

所有请求发送到 `{BASE_URL}/api/admin/*`，Header 带 `x-admin-key`。

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/admin/credentials` | GET | 凭据列表 |
| `/api/admin/credentials` | POST | 添加凭据 |
| `/api/admin/credentials/{id}` | DELETE | 删除凭据 |
| `/api/admin/credentials/{id}/disable` | POST | 禁用 |
| `/api/admin/credentials/{id}/enable` | POST | 启用 |
| `/api/admin/credentials/{id}/reset` | POST | 重置失败 |
| `/api/admin/credentials/{id}/priority?priority=N` | PUT | 设置优先级 |
| `/api/admin/credentials/{id}/balance` | GET | 查询余额 |
| `/api/admin/api-keys` | GET | Key 列表 |
| `/api/admin/api-keys` | POST | 创建 Key |
| `/api/admin/api-keys/{id}` | DELETE | 吊销 Key |
| `/api/admin/api-keys/{id}/enable` | POST | 启用 |
| `/api/admin/api-keys/{id}/disable` | POST | 禁用 |
| `/api/admin/api-keys/{id}/quota?token_quota=N` | PUT | 设置额度 |
| `/api/admin/api-keys/{id}/reset-usage` | POST | 重置用量 |
| `/api/admin/api-keys/usage-logs` | GET | 消费日志 |
| `/api/admin/groups` | GET | 分组列表 |
| `/api/admin/groups` | POST | 创建分组 |
| `/api/admin/groups/{id}` | PUT | 更新分组 |
| `/api/admin/groups/{id}` | DELETE | 删除分组 |
| `/api/admin/config/load-balancing-mode` | GET | 获取 LB 模式 |
| `/api/admin/config/load-balancing-mode?mode=X` | PUT | 设置 LB 模式 |

## 6. 文件结构

```
admin-ui/
├── index.html
├── package.json
├── vite.config.js
├── postcss.config.js
├── tailwind.config.js
├── public/
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── index.css
    ├── api/
    │   └── client.js          — fetch 封装 + Admin Key 注入
    ├── context/
    │   └── AuthContext.jsx     — 登录状态 + BASE_URL + Admin Key
    ├── components/
    │   ├── Layout.jsx          — 侧边栏布局
    │   ├── LoginPage.jsx
    │   ├── DashboardPage.jsx
    │   ├── credentials/
    │   │   ├── CredentialsPage.jsx
    │   │   ├── CredentialCard.jsx
    │   │   ├── AddCredentialDialog.jsx
    │   │   └── BalanceDialog.jsx
    │   ├── api-keys/
    │   │   ├── ApiKeysPage.jsx
    │   │   └── CreateApiKeyDialog.jsx
    │   ├── groups/
    │   │   ├── GroupsPage.jsx
    │   │   └── GroupDialog.jsx
    │   └── logs/
    │       └── UsageLogsPage.jsx
    └── lib/
        └── utils.js            — 格式化、时间处理等工具函数
```

## 7. UI 设计原则

- 深色/浅色主题切换（Tailwind dark mode）
- 中文界面
- 响应式布局（移动端侧边栏折叠）
- 操作反馈：sonner toast 通知
- 危险操作需确认
- 凭据卡片式展示，其余页面表格展示
