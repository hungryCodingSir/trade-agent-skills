"""
统一记忆中间件

整合三大记忆管理功能:
- before_agent: 从 MySQL 恢复历史消息 + 从 Milvus 检索相关上下文
- 持久化由 PersistenceMiddleware 单独负责
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    RemoveMessage,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from loguru import logger

from app.utils.message_utils import extract_text_content, extract_user_query
from app.utils.snowflake import generate_id

_executor = ThreadPoolExecutor(max_workers=4)
SUMMARY_PREFIX = "[历史对话摘要]"


class MemoryMiddleware(AgentMiddleware):
    """轻量记忆中间件：仅负责从 Milvus 检索历史对话注入动态提示词"""

    def __init__(
        self,
        max_retrieved_messages: int = 5,
        min_retrieval_score: float = 0.3,
    ):
        super().__init__()
        self.max_retrieved_messages = max_retrieved_messages
        self.min_retrieval_score = min_retrieval_score

    def before_agent(self, state, runtime):
        """从 Milvus 检索与当前问题相关的历史对话记录，注入到 runtime context"""
        context = runtime.context
        if not context:
            return None
        session_id = getattr(context, "session_id", None)
        user_id = getattr(context, "user_id", None)
        messages = state.get("messages", [])

        query = extract_user_query(messages)
        if query and len(query.strip()) >= 5:
            history = self._retrieve_history(query, session_id, user_id)
            if history and context:
                context.retrieved_history = history
        return None

    # --- 上下文检索 ---
    def _retrieve_history(
        self, query: str, session_id: str, user_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        """从 Milvus 检索相关上下文"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self._retrieve_async(query, session_id, user_id)
                )
            finally:
                loop.close()
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    lambda: asyncio.run(
                        self._retrieve_async(query, session_id, user_id)
                    )
                )
                return future.result(timeout=10.0)

    async def _retrieve_async(
        self, query: str, session_id: str, user_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        from app.services.chat_milvus_service import get_chat_milvus_service
        svc = get_chat_milvus_service()

        all_results = []

        # 当前会话
        results = await svc.hybrid_search(query=query, session_id=session_id)
        for r in results:
            if r.get("score", 0) >= self.min_retrieval_score:
                r["source"] = "current"
                all_results.append(r)

        # 跨会话
        results = await svc.hybrid_search(query=query, session_id=None)
        for r in results:
            if r.get("session_id") == session_id:
                continue
            if r.get("score", 0) >= self.min_retrieval_score:
                r["source"] = "history"
                all_results.append(r)

        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:self.max_retrieved_messages]
