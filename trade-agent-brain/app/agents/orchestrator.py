"""
跨境电商 Deep Agent 编排器
- AgentSkills 渐进式加载（Progressive Disclosure）使用 FilesystemBackend 从磁盘加载 Skill，
框架仅读取 frontmatter → 按 description 匹配 → 按需读取完整内容
- SubAgent 委派（复杂任务自动委派给专业子智能体）、Planning Tool（内置任务规划器）、FileSystem Backend（磁盘文件系统，取代 StateBackend）
Token 用量说明:FilesystemBackend + skills=[path] → 仅 frontmatter + 按需读取 → 每次请求 ~500 tokens
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, cast, OrderedDict

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel

from app.middleware.user_context_enhance import inject_system_prompt
from app.utils.token_usage import log_qwen_token_usage
from app.agents.subagents import get_subagent_configs
from app.config.llm_config import main_model, mini_model
from app.config.settings import settings, BASE_DIR
from app.middleware.memory_middleware import MemoryMiddleware
from app.middleware.quality_guard_middleware import ResponseQualityGuardMiddleware
from app.middleware.qwen_caching_middleware import QwenPromptCachingMiddleware
from app.models.schemas import UserContext, UserType
from app.tools import get_all_tools
from app.utils.snowflake import generate_id


class AgentRuntimeContext(BaseModel):
    """贯穿请求生命周期的运行时上下文，传递给 Middleware 和 dynamic_prompt"""
    user_id: int
    username: str
    user_type: str
    company_name: Optional[str] = None
    language: str = "zh-CN"
    session_id: str
    request_time: Optional[datetime] = None
    retrieved_history: Optional[List[Dict[str, Any]]] = None  # Milvus 检索到的历史对话

    @classmethod
    def from_user_context(cls, user_ctx: UserContext, session_id: str):
        return cls(
            user_id=user_ctx.user_id,
            username=user_ctx.username,
            user_type=user_ctx.user_type.value,
            company_name=user_ctx.company_name,
            language=user_ctx.language,
            session_id=session_id,
            request_time=datetime.now(),
        )

class CrossBorderAgent:
    """跨境电商 Deep Agent Skills 按需加载"""
    def __init__(self, user_context: UserContext, session_id: str = None, checkpointer=None):
        """初始化 Deep Agent，包含 LLM + Tools + SubAgents + Middleware"""
        self.user_context = user_context
        self.session_id = session_id or str(uuid.uuid4())
        self.runtime_context = AgentRuntimeContext.from_user_context(
            user_context, self.session_id
        )
        self.checkpointer = checkpointer
        self._agent = self._create_deep_agent()

    def _create_deep_agent(self):
        """组装 Deep Agent: LLM + Tools + SubAgents + Middleware + Skills"""

        tools = get_all_tools()
        logger.info(f"Tools: {[t.name for t in tools]}")

        subagents = get_subagent_configs()
        logger.info(f"SubAgents: {[s['name'] for s in subagents]}")

        middlewares = [
            MemoryMiddleware(
                max_retrieved_messages=5,  # 新参数
                min_retrieval_score=0.3,
            ),
            # 动态提示词注入
            inject_system_prompt,
            # skills前页 + 系统提示词被千问显式缓存。
            QwenPromptCachingMiddleware(
                # 缓存 system prompt（含 skill metadata）
                cache_system_prompt=True,
                # 缓存到最后一条用户消息（多轮历史也被缓存）
                cache_last_user_message=True,
            ),
            ResponseQualityGuardMiddleware(max_retries=2, min_score=0.6),
        ]

        backend = FilesystemBackend(root_dir=str(BASE_DIR))

        agent = create_deep_agent(
            model=main_model,
            tools=tools,
            subagents=subagents,
            middleware=middlewares,
            skills=[settings.skills_dir],
            backend=backend,
            checkpointer=self.checkpointer,
            context_schema=AgentRuntimeContext,
        )

        return agent

    async def chat(self, message: str, thread_id: str = None) -> Dict[str, Any]:
        """与 Agent 对话，返回包含 message / session_id / 可能的 interrupt 信息。"""
        thread_id = thread_id or self.session_id

        input_data = {
            "messages": [HumanMessage(content=message, id=f"human-{generate_id()}")],
        }

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id
            },
        }

        try:
            result = await self._agent.ainvoke(input=cast(Any, input_data), config=config, context=self.runtime_context)

            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None
            # 统计 token 使用情况
            log_qwen_token_usage(result)
            response = {
                "message": last_message.content if last_message else "",
                "session_id": self.session_id,
                "thread_id": thread_id,
            }

            if result.get("__interrupt__"):
                response["requires_approval"] = True
                response["pending_action"] = result.get("__interrupt__")

            return response

        except Exception as e:
            logger.error(f"Agent chat error: {e}", exc_info=True)
            raise

    async def chat_stream(self, message: str, thread_id: str = None) -> AsyncGenerator[str, None]:
        """
        流式对话 — 使用 LangGraph 的 astream_events (v2) 逐 token 输出。

        Yields SSE 格式的 JSON 字符串，事件类型：
          - token      : LLM 生成的文本片段
          - tool_start : 工具调用开始
          - tool_end   : 工具调用结束（含结果摘要）
          - done       : 流结束，包含完整 session_id
          - error      : 出错
        """
        thread_id = thread_id or self.session_id

        input_data = {
            "messages": [HumanMessage(content=message, id=f"human-{generate_id()}")],
        }

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id
            },
        }

        full_content = ""  # 累积完整回复

        try:
            async for event in self._agent.astream_events(
                input=cast(Any, input_data),
                config=config,
                context=self.runtime_context,
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
                "session_id": self.session_id,
                "thread_id": thread_id,
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Agent stream error: {e}", exc_info=True)
            yield json.dumps({
                "event": "error",
                "content": f"流式响应异常: {str(e)}",
            }, ensure_ascii=False)

    async def resume(
        self,
        decision: Dict[str, Any],
        thread_id: str = None,
    ) -> Dict[str, Any]:
        """恢复被 interrupt() 暂停的图执行（如邮件发送确认）。"""
        thread_id = thread_id or self.session_id

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id
            },
        }

        try:
            result = await self._agent.ainvoke(
                input=Command(resume=decision),
                config=config,
                context=self.runtime_context,
            )

            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None

            return {
                "message": last_message.content if last_message else "",
                "session_id": self.session_id,
                "thread_id": thread_id,
                "resumed": True,
                "decision": decision.get("decision", "unknown"),
            }

        except Exception as e:
            logger.error(f"Agent resume error: {e}", exc_info=True)
            raise


class LRUCache:
    """线程安全的 LRU 缓存，配合 asyncio.Lock 使用"""
    def __init__(self, maxsize: int = 128):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize

    def get(self, key) -> Optional[Any]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key, value) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def __contains__(self, key) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

# Agent 实例缓存: (user_id, session_id) → CrossBorderAgent
_agent_cache: LRUCache = LRUCache(maxsize=256)
_factory_lock = asyncio.Lock()


async def create_cross_border_agent(
    user_context: UserContext,
    session_id: str = None,
) -> CrossBorderAgent:
    """工厂方法: 基于 (user_id, session_id) 复用或创建 Agent 实例。"""
    from app.main import checkpointer
    session_id = session_id or str(uuid.uuid4())
    cache_key = (user_context.user_id, session_id)

    cached_agent = _agent_cache.get(cache_key)
    if cached_agent is not None:
        if cached_agent.user_context.user_id == user_context.user_id:
            return cached_agent

    async with _factory_lock:
        cached_agent = _agent_cache.get(cache_key)
        if cached_agent is not None:
            return cached_agent

        agent = CrossBorderAgent(
            user_context=user_context,
            session_id=session_id,
            checkpointer=checkpointer,
        )
        _agent_cache.put(cache_key, agent)

        logger.info(
            f"New agent created: user={user_context.user_id}, "
            f"session={session_id[:8]}..., cache_size={len(_agent_cache)}"
        )
        return agent