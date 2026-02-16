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
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel
from app.utils.token_usage import log_qwen_token_usage
from app.agents.subagents import get_subagent_configs
from app.config.llm_config import main_model, mini_model
from app.config.settings import settings, BASE_DIR
from app.middleware.memory_middleware import MemoryMiddleware
from app.middleware.persistence_middleware import PersistenceMiddleware
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
    retrieved_summaries: Optional[List[Dict[str, Any]]] = None

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


def _build_system_prompt(user_ctx: UserContext) -> str:
    """构建角色感知的系统提示词（核心身份 + 通用规则，业务知识由 Skills 按需提供）。"""
    role_map = {
        UserType.BUYER: ("买家", "查询订单、追踪物流、管理购物车、售后支持"),
        UserType.SELLER: ("卖家", "发货管理、客户沟通、清关支持、数据分析"),
        UserType.ADMIN: ("管理员", "平台监控、纠纷仲裁、用户管理、数据分析"),
    }

    role_name, role_focus = role_map.get(
        UserType(user_ctx.user_type), ("用户", "通用服务")
    )

    return f"""你是跨境电商平台的智能助手。

当前用户: {user_ctx.username}（{role_name}）
公司: {user_ctx.company_name or "个人用户"}
语言: {user_ctx.language}

核心职责: 为{role_name}提供 {role_focus}

工作方式:
1. 收到用户问题后，先从 /skills/ 目录读取对应领域的 SKILL.md 获取业务知识
2. **绝大多数任务自己处理**：
   - 查一个或多个订单 → 自己并行调用 query_order_status
   - 查物流 → 自己调用 query_shipping_info
   - 查购物车 → 自己调用 query_shopping_cart
   - 简单对比（如对比几个订单的状态/金额）→ 自己查完后对比
3. **仅以下情况委派 SubAgent**：
   - 需要生成完整的数据分析报告（含图表、统计指标）
   - 需要跨 3 个以上领域协作（如查订单+查物流+查海关+发邮件）
   - 用户明确要求详细的、多页面的报告
4. **并行优先**：当需要查多个订单/物流时，一次返回多个工具调用，不要串行

关键原则：
- 能自己做的绝不委派，委派的开销是自己做的 2-3 倍
- 对比分析不等于复杂任务，查完数据你自己就能对比
- 宁可自己多调几个工具，也不要轻易启动 SubAgent"""


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
                summary_model=mini_model,
                max_messages_trigger=settings.agent_messages_to_trigger,
                max_tokens_trigger=settings.agent_max_tokens_before_summary,
                messages_to_keep=settings.agent_messages_to_keep,
            ),
            ResponseQualityGuardMiddleware(max_retries=2, min_score=0.6),
            PersistenceMiddleware(),
            # skills metadata + system prompt 被千问显式缓存。
            QwenPromptCachingMiddleware(
                cache_system_prompt=True,  # 缓存 system prompt（含 skill metadata）
                cache_last_user_message=True,  # 缓存到最后一条用户消息（多轮历史也被缓存）
            ),
        ]

        system_prompt = _build_system_prompt(self.user_context)

        backend = FilesystemBackend(root_dir=str(BASE_DIR))

        agent = create_deep_agent(
            model=main_model,
            tools=tools,
            subagents=subagents,
            middleware=middlewares,
            system_prompt=system_prompt,
            skills=[settings.skills_dir],  # 框架的渐进式披露
            backend=backend,
            checkpointer=self.checkpointer,
        )

        return agent

    async def chat(self, message: str, thread_id: str = None) -> Dict[str, Any]:
        """与 Agent 对话，返回包含 message / session_id / 可能的 interrupt 信息。"""
        thread_id = thread_id or self.session_id

        # 任务复杂度预判，辅助 LLM 路由
        # complexity = self._estimate_complexity(message)
        # hint = (
        #     f"\n[系统提示: 任务复杂度预判={complexity}，"
        #     f"{'建议委派给专业 SubAgent' if complexity == 'complex' else '建议直接处理'}]"
        # )

        # FilesystemBackend 从磁盘读取，无需手动注入文件到 state
        input_data = {
            # "messages": [HumanMessage(content=message + hint, id=f"human-{generate_id()}")],
            "messages": [HumanMessage(content=message, id=f"human-{generate_id()}")],
        }

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": self.user_context.user_id,
                "username": self.user_context.username,
                "user_type": self.user_context.user_type.value,
                "company_name": self.user_context.company_name,
                "language": self.user_context.language,
            },
        }

        try:
            result = await self._agent.ainvoke(input=cast(Any, input_data), config=config)

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
                "thread_id": thread_id,
                "user_id": self.user_context.user_id,
                "username": self.user_context.username,
                "user_type": self.user_context.user_type.value,
                "company_name": self.user_context.company_name,
                "language": self.user_context.language,
            },
        }

        full_content = ""  # 累积完整回复

        try:
            async for event in self._agent.astream_events(
                input=cast(Any, input_data),
                config=config,
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
                "thread_id": thread_id,
                "user_id": self.user_context.user_id,
                "username": self.user_context.username,
                "user_type": self.user_context.user_type.value,
                "company_name": self.user_context.company_name,
                "language": self.user_context.language,
            },
        }

        try:
            result = await self._agent.ainvoke(
                input=Command(resume=decision),
                config=config,
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


    def _estimate_complexity(self, message: str) -> str:
        """轻量级复杂度预判，辅助 LLM 路由"""
        complex_signals = [
            "对比", "分析", "报告", "统计", "趋势", "批量",
            "所有订单", "最近几个", "汇总", "compare", "analyze",
            "report", "多个", "历史记录",
        ]
        count = sum(1 for s in complex_signals if s in message)
        return "complex" if count >= 2 else "simple"

# Agent 实例缓存: (user_id, session_id) → CrossBorderAgent
_agent_cache: Dict[tuple, CrossBorderAgent] = {}
_factory_lock = asyncio.Lock()


async def create_cross_border_agent(
    user_context: UserContext,
    session_id: str = None,
) -> CrossBorderAgent:
    """工厂方法: 基于 (user_id, session_id) 复用或创建 Agent 实例。"""
    from app.main import checkpointer
    session_id = session_id or str(uuid.uuid4())
    cache_key = (user_context.user_id, session_id)

    if cache_key in _agent_cache:
        agent = _agent_cache[cache_key]
        if agent.user_context.user_id == user_context.user_id:
            return agent

    async with _factory_lock:
        if cache_key in _agent_cache:
            return _agent_cache[cache_key]

        agent = CrossBorderAgent(
            user_context=user_context,
            session_id=session_id,
            checkpointer=checkpointer,
        )
        _agent_cache[cache_key] = agent

        logger.info(
            f"New agent created: user={user_context.user_id}, "
            f"session={session_id[:8]}..., cache_size={len(_agent_cache)}"
        )
        return agent