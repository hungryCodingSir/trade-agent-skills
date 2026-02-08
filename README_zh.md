# Trade Agent Skills - 跨境电商智能体

基于 LangChain1.2.6 + Deep Agents + AgentSkills 架构的跨境电商多智能体助手，此项目只是依靠跨境电商做示例，实际应用中可以扩展到其他聊天助手领域，这里提供一个参考架构。

## 技术栈（Java+Python）
本系统采用 Java (MCP Server) + Python (Agent Brain) 异构架构，基于 LangChain 1.x 最新设计理念，深度集成 Model Context Protocol (MCP) 规范。
项目提供了一套**生产级 Agent Skills 参考架构**，通过中间件生命周期钩子（Hooks）实现高度模块化与可扩展性，适用于复杂智能体应用及任务编排场景。

| 维度 | 技术/组件                                               | 说明 |
|------|-----------------------------------------------------|------|
| **Agent 框架** | LangChain 1.2.6 + Deep Agents 0.3 + LangGraph 1.0.7 | 核心编排与多智能体协作 |
| **LLM 引擎** | 阿里云百炼，自己按实际情况选择                                       | 
| **后端框架 (Py)** | FastAPI + Uvicorn + SQLAlchemy                      | Agent Brain 接口与服务 |
| **后端框架 (Java)**| Spring Boot 3.4.1 + Spring AI 1.0.0                 | MCP Server 工具服务端 |
| **数据库** | MySQL 8.0+                                          | 业务数据持久化存储 |
| **缓存/状态** | Redis                                               | 会话管理与临时状态缓存 |
| **向量检索** | Milvus (BM25 + Dense)                               | 混合检索记忆增强 |
| **数据访问** | MyBatis-Plus 3.5.9                                  | Java 侧 ORM 框架 |
| **工具协议** | MCP (Model Context Protocol)                        | 跨语言工具调用标准 (SSE) |
| **邮件服务** | Spring Mail (SMTP)                                  | 自动化邮件通知 |
| **评估体系** | agentevals + LLM-as-Judge                           | 自动化轨迹与质量评估 |

## 架构概览

```
                                ┌───────────────────────────────────────────────┐
                                │              FastAPI Gateway                  │
                                └────────────────────┬──────────────────────────┘
                                                     │
                                         ┌───────────▼────────────┐
                                         │   Deep Agent 主编排器   │
                                         │   Planning / Skills /  │
                                         │   FileSystem Backend   │
                                         └───────┬────────────────┘
                                                 │ 按需调度
                                    ┌────────────┼────────────────────────┐
                                    ▼            ▼            ▼           ▼
                                ┌────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
                                │订单专员  │ │物流专员  │ │沟通专员   │ │分析专员   │
                                └───┬────┘ └───┬─────┘ └───┬─────┘ └───┬──────┘
                                    └──────────┴─────┬─────┴────────────┘
                                                     │
                                            ┌────────▼────────┐
                                            │  MCP Protocol   │
                                            │  (SSE Client)   │
                                            └────────┬────────┘
                                                     │
                                         ┌───────────▼────────────┐
                                         │    Java mcp-server  	  │
                                         └────────────────────────┘
```

## 中间件层设计说明

系统在 LangChain Deep Agent 的 Middleware 机制上实现了三个中间件，分别覆盖 **记忆管理**、**消息持久化** 和 **响应质量兜底**。顺序挂载到 Orchestrator，在 Agent 生命周期的不同钩子处介入。

```
请求进入
  │
  ▼
MemoryMiddleware.before_agent      ← 恢复历史 + 检索上下文
PersistenceMiddleware.before_agent ← 持久化用户消息
  │
  ▼
[Agent 推理 / 工具调用]
  │
  ▼  (每次 LLM 调用)
MemoryMiddleware.before_model      ← 判断是否触发摘要压缩，此处没有采用官方的SummarizationMiddleware，因为需要把控定制化摘要时机和存储逻辑
QualityGuardMiddleware.wrap_model  ← 评估器-拦截低质量响应并重试
  │
  ▼
PersistenceMiddleware.after_agent  ← 持久化 AI 响应
```

## 邮件发送确认 (Human-in-the-Loop)

基于 LangGraph `interrupt()` 实现邮件发送前的人工确认：

```
用户请求发邮件 → Agent 起草 → interrupt() 暂停 → 前端展示预览
                                                    ↓
                                 用户: approve / reject / edit
                                                    ↓
                        POST /resume → Command(resume=决策) → 恢复执行
```

## 核心特性

| 特性 | 说明 |
|------|------|
| **AgentSkills** | 7 个领域技能按需加载，降低 token 开销 |
| **SubAgent 委派** | 复杂任务自动调度给专业子智能体 |
| **Planning Tool** | 内置任务规划器，拆解多步骤请求 |
| **FileSystem 上下文** | 虚拟文件系统管理长文档和分析报告 |
| **混合记忆** | MySQL 持久化 + Milvus 向量检索 + Redis 会话缓存 |
| **MCP 工具调用** | 通过 SSE 协议连接 Java 后端 |
| **Human-in-the-Loop** | 邮件发送前强制人工确认 |
| **四层评估体系** | 轨迹 + 质量 + 安全 + LLM-as-Judge |

## 项目结构

```
trade-agent-brain/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py        # Deep Agent 主编排器
│   │   └── subagents.py           # 子智能体定义
│   ├── config/
│   │   ├── settings.py            # 配置管理
│   │   ├── llm_config.py          # 模型配置
│   │   ├── database.py            # MySQL 连接
│   │   └── redis_config.py        # Redis 连接
│   ├── middleware/
│   │   ├── memory_middleware.py    # 统一记忆中间件
│   │   ├── persistence_middleware.py # 持久化中间件
│   │   └── quality_guard_middleware.py # 结果评估中间件
│   ├── models/                    # 数据模型
│   ├── routers/                   # API 路由
│   ├── services/                  # 业务服务
│   ├── tools/                     # MCP 工具
│   └── main.py                    # FastAPI 入口
├── skills/                        # AgentSkills 目录
│   ├── order-management/  # 订单技能
│   │   └── SKILL.md
│   ├── logistics-tracking/ # 物流技能
│   │   └── SKILL.md
│   ├── cart-management/
│   │   └── SKILL.md
│   ├── email-notification/
│   │   └── SKILL.md
│   ├── customs-clearance/
│   │   └── SKILL.md
│   ├── data-analytics/
│   │   └── SKILL.md
│   └── dispute-resolution/
│       └── SKILL.md
├── tests/
├── requirements.txt
├── .env.example
└── README.md

trade-mcp-server/                          # Java MCP Server（Maven 多模块）
├── pom.xml                               
├── mcp-common/                            
│   ├── pom.xml
│   └── src/main/java/com/cbec/mcp/common/
│       ├── entity/
│       ├── enums/
│       ├── result/
│       └── util/
├── mcp-server/                            # MCP Server 主模块
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/cbec/mcp/server/
│       │   ├── McpServerApplication.java
│       │   ├── config/
│       │   │   └── McpConfig.java         # MCP 工具统一注册配置
│       │   ├── dto/                       # 视图对象
│       │   ├── mapper/                    # MyBatis-Plus Mapper 接口
│       │   ├── service/                   # 领域服务层
│       │   └── tool/                      # MCP Tool 定义（@Tool 注解）
│       └── resources/
│           ├── application.yml          
│           └── mapper/                    
└── sql/                                   # 数据库脚本目录

sql/                                       # 全局 SQL 脚本
├── schema.sql                             # 数据库建表脚本
└── data-demo.sql                          # 演示数据
```

## trade-mcp-server 说明

### 模块说明

- **mcp-common**：公共层，包含数据库实体（Entity）、枚举、统一返回结构 `McpResult`、JSON 工具类，被 `mcp-server` 依赖。
- **mcp-server**：核心服务模块，包含 MCP Tool 定义、Service 业务逻辑、MyBatis Mapper 以及 Spring Boot 启动入口。

### MCP 工具清单

通过 `McpConfig` 统一注册，所有工具均使用 `@Tool` 注解声明，自动暴露在 SSE 端点供 MCP Client 发现和调用


### 与 trade-agent-brain 的连接

`trade-agent-brain`（Python 侧）通过 MCP SSE Client 连接 `trade-mcp-server`，连接地址配置在 `.env` 文件中：

```
MCP_SERVER_URL=http://127.0.0.1:8081/sse
MCP_CALL_TIMEOUT=30
```

Python 侧的 `app/tools/__init__.py` 中定义了 `call_mcp_tool()` 通用调用函数，使用 `mcp.client.sse.sse_client` 建立 SSE 连接，通过 `ClientSession.call_tool()` 远程调用 Java 侧注册的 `@Tool` 方法。调用链路为：

```
Agent 推理 → Python @tool 函数 → MCP SSE Client → Java MCP Server (SSE 端点)
  → @Tool 注解方法 → Service → MyBatis Mapper → MySQL → 返回 McpResult JSON
```

### 快速启动

当前项目还未完善，后续将提供启动指南
