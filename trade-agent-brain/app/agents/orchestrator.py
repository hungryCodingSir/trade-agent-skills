"""
跨境电商 Deep Agent 编排器（进程级单例）

Agent 图在应用启动时编译一次，所有请求共享同一图实例。
会话隔离由 LangGraph Checkpointer (Redis) + thread_id 保证。

- AgentSkills 渐进式加载（Progressive Disclosure）使用 FilesystemBackend 从磁盘加载 Skill，
框架仅读取 frontmatter → 按 description 匹配 → 按需读取完整内容
- SubAgent 委派（复杂任务自动委派给专业子智能体）、Planning Tool（内置任务规划器）、FileSystem Backend（磁盘文件系统，取代 StateBackend）
Token 用量说明:FilesystemBackend + skills=[path] → 仅 frontmatter + 按需读取 → 每次请求 ~500 tokens
"""
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel

from app.agents.subagents import get_subagent_configs
from app.config.llm_config import main_model
from app.config.settings import settings, BASE_DIR
from app.middleware.memory_middleware import MemoryMiddleware
from app.middleware.quality_guard_middleware import ResponseQualityGuardMiddleware
from app.middleware.qwen_caching_middleware import QwenPromptCachingMiddleware
from app.middleware.user_context_enhance import inject_system_prompt
from app.models.schemas import UserContext
from app.tools import get_all_tools
from app.utils.snowflake import generate_id
from app.utils.token_usage import log_qwen_token_usage


# 运行时上下文（请求级，每次请求现场构造）
class AgentRuntimeContext(BaseModel):
    """请求级运行时上下文，传递给 Middleware 和 dynamic_prompt"""
    user_id: int
    username: str
    user_type: str
    company_name: Optional[str] = None
    language: str = "zh-CN"
    session_id: str
    request_time: Optional[datetime] = None
    retrieved_history: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_request(cls, user_ctx: UserContext, session_id: str):
        return cls(
            user_id=user_ctx.user_id,
            username=user_ctx.username,
            user_type=user_ctx.user_type.value,
            company_name=user_ctx.company_name,
            language=user_ctx.language,
            session_id=session_id,
            request_time=datetime.now(),
        )


# 由 init_agent() 在 lifespan 中赋值
_agent: Optional[CompiledStateGraph] = None

def init_agent(checkpointer) -> None:
    """应用启动时调用一次，编译并缓存 Agent 图。"""
    global _agent

    tools = get_all_tools()
    subagents = get_subagent_configs()
    logger.info(f"Tools: {[t.name for t in tools]}")
    logger.info(f"SubAgents: {[s['name'] for s in subagents]}")

    middlewares = [
        MemoryMiddleware(
            max_retrieved_messages=5,
            min_retrieval_score=0.3,
        ),
        # 动态提示词注入
        inject_system_prompt,
        # skills前页 + 系统提示词被千问显式缓存。
        QwenPromptCachingMiddleware(
            cache_system_prompt=True,
            cache_last_user_message=True,
        ),
        ResponseQualityGuardMiddleware(max_retries=2, min_score=0.6),
    ]

    backend = FilesystemBackend(root_dir=str(BASE_DIR))

    _agent = create_deep_agent(
        model=main_model,
        tools=tools,
        subagents=subagents,
        middleware=middlewares,
        skills=[settings.skills_dir],
        backend=backend,
        checkpointer=checkpointer,
        context_schema=AgentRuntimeContext,
    )

    logger.info("Agent graph compiled (process-level singleton)")


def get_agent() -> CompiledStateGraph:
    """获取编译好的 Agent 图实例。"""
    if _agent is None:
        raise RuntimeError("Agent not initialized. Call init_agent() in lifespan first.")
    return _agent


# 无状态服务函数

async def chat(
        user_context: UserContext,
        session_id: str,
        message: str,
) -> Dict[str, Any]:
    """与 Agent 对话，返回包含 message / session_id / 可能的 interrupt 信息。"""
    agent = get_agent()
    ctx = AgentRuntimeContext.from_request(user_context, session_id)

    config: RunnableConfig = {
        "configurable": {"thread_id": session_id},
    }
    input_data = {
        "messages": [HumanMessage(content=message, id=f"human-{generate_id()}")],
    }

    try:
        result = await agent.ainvoke(input=input_data, config=config, context=ctx)

        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None
        log_qwen_token_usage(result)

        response = {
            "message": last_message.content if last_message else "",
            "session_id": session_id,
        }

        if result.get("__interrupt__"):
            response["requires_approval"] = True
            response["pending_action"] = result.get("__interrupt__")

        return response

    except Exception as e:
        logger.error(f"Agent chat error: {e}", exc_info=True)
        raise


async def chat_stream(
        user_context: UserContext,
        session_id: str,
        message: str,
) -> AsyncGenerator[str, None]:
    """
    流式对话 — 使用 LangGraph 的 astream_events (v2) 逐 token 输出。

    Yields SSE 格式的 JSON 字符串，事件类型：
      - token      : LLM 生成的文本片段
      - tool_start : 工具调用开始
      - tool_end   : 工具调用结束（含结果摘要）
      - done       : 流结束，包含完整 session_id
      - error      : 出错
    """
    agent = get_agent()
    ctx = AgentRuntimeContext.from_request(user_context, session_id)

    config: RunnableConfig = {
        "configurable": {"thread_id": session_id},
    }
    input_data = {
        "messages": [HumanMessage(content=message, id=f"human-{generate_id()}")],
    }

    full_content = ""

    try:
        async for event in agent.astream_events(
                input=input_data,
                config=config,
                context=ctx,
                version="v2",
        ):
            kind = event.get("event", "")

            # ── 1. LLM 逐 token 流 ──
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token_text = chunk.content
                    full_content += token_text
                    yield json.dumps({
                        "event": "token",
                        "content": token_text,
                    }, ensure_ascii=False)

            # ── 2. 工具调用开始 ──
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown_tool")
                tool_input = event.get("data", {}).get("input", {})
                yield json.dumps({
                    "event": "tool_start",
                    "tool": tool_name,
                    "input": tool_input if isinstance(tool_input, dict) else str(tool_input),
                }, ensure_ascii=False)

            # ── 3. 工具调用结束 ──
            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown_tool")
                tool_output = event.get("data", {}).get("output", "")
                # 截断过长的工具输出，避免 SSE 消息过大
                output_str = str(tool_output)
                if len(output_str) > 500:
                    output_str = output_str[:500] + "...(truncated)"
                yield json.dumps({
                    "event": "tool_end",
                    "tool": tool_name,
                    "output": output_str,
                }, ensure_ascii=False)

        # ── 4. 流结束 ──
        yield json.dumps({
            "event": "done",
            "content": full_content,
            "session_id": session_id,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Agent stream error: {e}", exc_info=True)
        yield json.dumps({
            "event": "error",
            "content": f"流式响应异常: {str(e)}",
        }, ensure_ascii=False)


async def resume(
        user_context: UserContext,
        session_id: str,
        decision: Dict[str, Any],
) -> Dict[str, Any]:
    """恢复被 interrupt() 暂停的图执行（如邮件发送确认）。"""
    agent = get_agent()
    ctx = AgentRuntimeContext.from_request(user_context, session_id)

    config: RunnableConfig = {
        "configurable": {"thread_id": session_id},
    }

    try:
        result = await agent.ainvoke(
            input=Command(resume=decision),
            config=config,
            context=ctx,
        )

        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None

        return {
            "message": last_message.content if last_message else "",
            "session_id": session_id,
            "resumed": True,
            "decision": decision.get("decision", "unknown"),
        }

    except Exception as e:
        logger.error(f"Agent resume error: {e}", exc_info=True)
        raise
