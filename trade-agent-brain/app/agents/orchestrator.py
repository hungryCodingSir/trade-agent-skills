"""
跨境电商 Deep Agent 编排器

基于 LangChain Deep Agents + AgentSkills 构建，支持:
- AgentSkills 渐进式加载（7 个领域技能按需注入）
- SubAgent 委派（复杂任务自动委派给专业子智能体）
- Planning Tool（内置任务规划器）
- FileSystem Backend（虚拟文件系统管理长上下文）
- 混合记忆（Redis + MySQL + Milvus）
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from deepagents import create_deep_agent
from deepagents.middleware.filesystem import FileData
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel

from app.agents.subagents import get_subagent_configs
from app.config.llm_config import main_model, mini_model
from app.config.settings import settings
from app.middleware.memory_middleware import MemoryMiddleware
from app.middleware.persistence_middleware import PersistenceMiddleware
from app.middleware.quality_guard_middleware import ResponseQualityGuardMiddleware
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


def _load_skill_files(skills_dir: str) -> Dict[str, FileData]:
    """从磁盘读取所有 SKILL.md，映射为 StateBackend 需要的虚拟文件路径。"""
    skill_files: Dict[str, FileData] = {}
    skills_path = Path(skills_dir)

    if not skills_path.exists():
        logger.warning(f"Skills 目录不存在: {skills_dir}")
        return skill_files

    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    virtual_path = f"/skills/{skill_dir.name}/{file_path.name}"
                    now = datetime.now().isoformat()
                    skill_files[virtual_path] = FileData(
                        content=content.split("\n"),
                        created_at=now,
                        modified_at=now,
                    )
                    logger.debug(f"Loaded skill: {virtual_path}")
                except Exception as e:
                    logger.error(f"Failed to load {file_path}: {e}")

    logger.info(f"Loaded {len(skill_files)} skill files from {skills_dir}")
    return skill_files


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
2. **简单任务自己处理**：单次工具调用即可完成的任务（如查一个订单、查一次物流），
   你直接按照 Skill 中的指引调用工具并回复
3. **复杂任务委派 SubAgent**：仅当任务满足以下任一条件时，才委派给专业子智能体：
   - 需要多次工具调用且结果间有依赖关系（如对比多个订单）
   - 需要聚合分析（如统计退货率、生成报告）
   - 涉及多领域协作（如查订单+查物流+发通知）
   - 需要长篇格式化输出（如完整的分析报告）
4. **绝不重复**：SubAgent 不需要再读 Skill，它有自己的专业 system_prompt

委派判断示例：
- "查一下 ORD001 的状态" → 简单，自己处理
- "对比我最近5个订单的物流时效" → 复杂，委派 logistics-specialist
- "帮我给供应商写封催货邮件" → 复杂，委派 communication-specialist
- "我的购物车里有什么" → 简单，自己处理
- "分析本月退货率并生成报告" → 复杂，委派 analytics-specialist"""


class CrossBorderAgent:
    """
    跨境电商 Deep Agent

    封装 create_deep_agent() 创建的智能体，提供 chat / resume 接口。
    支持 Planning + FileSystem + SubAgent + Middleware。
    """

    def __init__(self, user_context: UserContext, session_id: str = None, checkpointer=None):
        """初始化 Deep Agent，包含 LLM + Tools + SubAgents + Middleware + Skills"""
        self.user_context = user_context
        self.session_id = session_id or str(uuid.uuid4())
        self.runtime_context = AgentRuntimeContext.from_user_context(
            user_context, self.session_id
        )
        self.checkpointer = checkpointer
        self._skill_files = _load_skill_files(settings.skills_dir)
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
        ]

        system_prompt = _build_system_prompt(self.user_context)

        agent = create_deep_agent(
            model=main_model,
            tools=tools,
            subagents=subagents,
            middleware=middlewares,
            system_prompt=system_prompt,
            skills=["./skills/"],
            checkpointer=self.checkpointer,
        )

        return agent

    async def chat(self, message: str, thread_id: str = None) -> Dict[str, Any]:
        """与 Agent 对话，返回包含 message / session_id / 可能的 interrupt 信息。"""
        thread_id = thread_id or self.session_id

        # 任务复杂度预判，辅助 LLM 路由
        complexity = self._estimate_complexity(message)
        hint = (
            f"\n[系统提示: 任务复杂度预判={complexity}，"
            f"{'建议委派给专业 SubAgent' if complexity == 'complex' else '建议直接处理'}]"
        )

        input_data = {
            "messages": [
                HumanMessage(
                    content=message + hint,
                    id=f"human-{generate_id()}"
                )
            ],
            "files": self._skill_files,
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
