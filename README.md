# Trade Agent Skills — Cross-Border E-Commerce Multi-Agent Assistant

A production-grade multi-agent assistant built on **LangChain 1.2.6 + Deep Agents + AgentSkills** architecture, designed for cross-border e-commerce scenarios. While e-commerce serves as the reference domain, the architecture is fully extensible to other conversational AI use cases.

## Tech Stack (Java + Python)

This system adopts a **Java (MCP Server) + Python (Agent Brain)** heterogeneous architecture, deeply integrated with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) specification and built on the latest LangChain 1.x design principles.

It provides a **production-grade Agent Skills reference architecture** with highly modular and extensible middleware lifecycle hooks, suitable for complex agent applications and task orchestration scenarios.

| Layer | Technology | Description |
|---|---|---|
| **Agent Framework** | LangChain 1.2.6 + Deep Agents 0.3 + LangGraph 1.0.7 | Core orchestration & multi-agent collaboration |
| **LLM Engine** | Alibaba Cloud Bailian (customizable) | Swap in any LLM provider as needed |
| **Backend (Python)** | FastAPI + Uvicorn + SQLAlchemy | Agent Brain API & services |
| **Backend (Java)** | Spring Boot 3.4.1 + Spring AI 1.0.0 | MCP Server tool services |
| **Database** | MySQL 8.0+ | Business data persistence |
| **Cache / State** | Redis | Session management & ephemeral state |
| **Vector Search** | Milvus (BM25 + Dense) | Hybrid retrieval for memory augmentation |
| **ORM (Java)** | MyBatis-Plus 3.5.9 | Java-side data access |
| **Tool Protocol** | MCP (Model Context Protocol) | Cross-language tool invocation standard (SSE) |
| **Email Service** | Spring Mail (SMTP) | Automated email notifications |
| **Evaluation** | agentevals + LLM-as-Judge | Automated trajectory & quality assessment |

## Architecture Overview

```
                                ┌───────────────────────────────────────────────┐
                                │              FastAPI Gateway                  │
                                └────────────────────┬──────────────────────────┘
                                                     │
                                         ┌───────────▼────────────┐
                                         │   Deep Agent Orchestrator│
                                         │   Planning / Skills /    │
                                         │   FileSystem Backend     │
                                         └───────┬────────────────┘
                                                 │ On-demand dispatch
                                    ┌────────────┼────────────────────────┐
                                    ▼            ▼            ▼           ▼
                                ┌────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
                                │ Order  │ │Logistics│ │Comms    │ │Analytics │
                                │ Agent  │ │ Agent   │ │ Agent   │ │ Agent    │
                                └───┬────┘ └───┬─────┘ └───┬─────┘ └───┬──────┘
                                    └──────────┴─────┬─────┴────────────┘
                                                     │
                                            ┌────────▼────────┐
                                            │  MCP Protocol   │
                                            │  (SSE Client)   │
                                            └────────┬────────┘
                                                     │
                                         ┌───────────▼────────────┐
                                         │    Java MCP Server     │
                                         └────────────────────────┘
```

## Middleware Layer Design

The system implements three middlewares on top of LangChain Deep Agent's middleware mechanism, covering **memory management**, **message persistence**, and **response quality guardrails**. They are mounted on the Orchestrator in sequence and intervene at different lifecycle hooks.

```
Request Incoming
  │
  ▼
MemoryMiddleware.before_agent      ← Restore history + retrieve context
PersistenceMiddleware.before_agent ← Persist user message
  │
  ▼
[Agent Reasoning / Tool Calls]
  │
  ▼  (on each LLM call)
MemoryMiddleware.before_model      ← Trigger summarization if needed *
QualityGuardMiddleware.wrap_model  ← Evaluate & retry low-quality responses
  │
  ▼
PersistenceMiddleware.after_agent  ← Persist AI response
```

> \* A custom summarization strategy is used instead of the built-in `SummarizationMiddleware` to allow fine-grained control over summarization timing and storage logic.

## Human-in-the-Loop: Email Confirmation

Email sending requires explicit human approval, implemented via LangGraph's `interrupt()`:

```
User requests email → Agent drafts → interrupt() pauses → Frontend shows preview
                                                            ↓
                                         User: approve / reject / edit
                                                            ↓
                            POST /resume → Command(resume=decision) → Resume execution
```

## Key Features

| Feature | Description |
|---|---|
| **AgentSkills** | 7 domain skills loaded on demand to reduce token overhead |
| **SubAgent Delegation** | Complex tasks are automatically dispatched to specialized sub-agents |
| **Planning Tool** | Built-in task planner that decomposes multi-step requests |
| **FileSystem Context** | Virtual file system for managing long documents and analysis reports |
| **Hybrid Memory** | MySQL persistence + Milvus vector retrieval + Redis session cache |
| **MCP Tool Calls** | Connects to the Java backend via SSE protocol |
| **Human-in-the-Loop** | Mandatory human confirmation before sending emails |
| **4-Layer Evaluation** | Trajectory + Quality + Safety + LLM-as-Judge |

## Project Structure

```
trade-agent-brain/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py          # Deep Agent orchestrator
│   │   └── subagents.py             # Sub-agent definitions
│   ├── config/
│   │   ├── settings.py              # Configuration management
│   │   ├── llm_config.py            # LLM configuration
│   │   ├── database.py              # MySQL connection
│   │   └── redis_config.py          # Redis connection
│   ├── middleware/
│   │   ├── memory_middleware.py      # Unified memory middleware
│   │   ├── persistence_middleware.py # Persistence middleware
│   │   └── quality_guard_middleware.py # Quality guard middleware
│   ├── models/                      # Data models
│   ├── routers/                     # API routes
│   ├── services/                    # Business services
│   ├── tools/                       # MCP tools
│   └── main.py                      # FastAPI entry point
├── skills/                          # AgentSkills directory
│   ├── order-management/
│   │   └── SKILL.md
│   ├── logistics-tracking/
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

trade-mcp-server/                             # Java MCP Server (Maven multi-module)
├── pom.xml
├── mcp-common/
│   ├── pom.xml
│   └── src/main/java/com/cbec/mcp/common/
│       ├── entity/
│       ├── enums/
│       ├── result/
│       └── util/
├── mcp-server/                               # MCP Server main module
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/cbec/mcp/server/
│       │   ├── McpServerApplication.java
│       │   ├── config/
│       │   │   └── McpConfig.java            # Unified MCP tool registration
│       │   ├── dto/                          # Data transfer objects
│       │   ├── mapper/                       # MyBatis-Plus mapper interfaces
│       │   ├── service/                      # Domain service layer
│       │   └── tool/                         # MCP Tool definitions (@Tool)
│       └── resources/
│           ├── application.yml
│           └── mapper/
└── sql/                                      # Database scripts

sql/                                          # Global SQL scripts
├── schema.sql                                # Table creation script
└── data-demo.sql                             # Demo data
```

## trade-mcp-server

### Module Overview

- **mcp-common** — Shared layer containing database entities, enums, the unified response wrapper `McpResult`, and JSON utilities. Depended on by `mcp-server`.
- **mcp-server** — Core service module containing MCP Tool definitions, service logic, MyBatis mappers, and the Spring Boot entry point.

### MCP Tools

All tools are registered centrally via `McpConfig` using the `@Tool` annotation, and are automatically exposed on the SSE endpoint for MCP Client discovery and invocation.

### Connecting to trade-agent-brain

The Python side (`trade-agent-brain`) connects to `trade-mcp-server` via MCP SSE Client. The connection URL is configured in `.env`:

```env
MCP_SERVER_URL=http://127.0.0.1:8081/sse
MCP_CALL_TIMEOUT=30
```

`app/tools/__init__.py` defines a generic `call_mcp_tool()` function that establishes an SSE connection using `mcp.client.sse.sse_client` and invokes remote Java-side `@Tool` methods via `ClientSession.call_tool()`. The full call chain is:

```
Agent Reasoning → Python @tool → MCP SSE Client → Java MCP Server (SSE endpoint)
  → @Tool method → Service → MyBatis Mapper → MySQL → McpResult JSON response
```

## Getting Started

> 🚧 The project is still under active development. A full setup guide will be provided soon.

## License

[MIT](LICENSE)
