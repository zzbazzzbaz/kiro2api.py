# 提案：初始构建 — kiro2api

## 意图
构建一个 Python FastAPI 服务，将 Anthropic/OpenAI API 请求通过 Kiro 上游 API 进行代理，同时新增多凭据管理、凭据池分组、外部 API Key 管理、消费记录和 Token 额度管理等功能。

本项目是 Rust 版 `kiro.rs` 的 Python 重写，在保留核心功能的基础上新增了多租户使用场景所需的扩展能力。

## 范围

### 纳入范围
- **Anthropic API 兼容**：`/v1/messages`、`/v1/models`、`/v1/messages/count_tokens`、`/cc/v1/messages`
- **OpenAI API 兼容**：`/v1/chat/completions`，支持格式自动转换
- **Token 管理**：Social 和 IdC 两种认证方式的 OAuth Token 自动刷新
- **多凭据故障转移**：基于优先级和均衡模式的负载均衡，支持自动故障转移
- **协议转换**：Anthropic ↔ Kiro 请求/响应转换，含流式（SSE）支持
- **凭据池分组**：隔离的凭据池，支持分组级负载均衡
- **外部 API Key 管理**：生成、吊销、启用/禁用、绑定分组
- **Token 额度强制执行**：每个 Key 独立设置 Token 上限，请求前前置检查
- **消费记录**：异步记录每次请求的 IP、模型、输入/输出 Token 数
- **Kiro 账号状态**：通过上游 `getUsageLimits` API 检测账号状态（正常/封禁）、订阅等级及剩余积分
- **Admin API**：凭据、API Key、分组、配置的完整 CRUD
- **WebSearch**：Anthropic WebSearch 工具 → Kiro MCP 转换
- **Thinking 模式**：扩展思考支持，含真实标签检测
- **凭据级代理**：每个凭据可独立配置代理

### 不纳入范围
- 前端 Admin 管理界面（当前仅提供 API）
- 超出 Token 额度之外的速率限制
- 多区域部署
- 水平扩展 / 分布式状态
- 用户自助注册 / 自助创建 API Key

## 实施方法
1. **基础建设**：搭建 FastAPI 项目，配置 SQLAlchemy 异步 ORM、SQLite、Alembic 迁移、pydantic-settings 配置管理
2. **核心引擎**：从 kiro.rs 移植 Token 管理和 KiroProvider
3. **协议层**：从 kiro.rs 移植 Anthropic ↔ Kiro 转换器和流式处理器
4. **API 层**：实现 Anthropic 和 OpenAI 兼容端点
5. **多租户层**：新增分组、外部 API Key、消费记录、额度强制执行
6. **Admin API**：实现所有管理端点
7. **账号状态**：集成上游 getUsageLimits，实现账号健康状态监控

## 参考项目
- `kiro.rs` — Rust 参考实现（核心逻辑、协议转换、流式处理）
- `kiro-account-manager` — Tauri 桌面应用（账号状态检测、getUsageLimits API 格式）
