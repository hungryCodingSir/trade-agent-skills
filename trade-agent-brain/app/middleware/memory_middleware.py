"""
统一记忆中间件

整合三大记忆管理功能:
- before_agent: 从 MySQL 恢复历史消息 + 从 Milvus 检索相关上下文
- before_model: 按阈值触发对话摘要压缩
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
    """统一记忆中间件: 历史恢复 + 上下文检索 + 摘要压缩"""

    def __init__(
        self,
        summary_model: BaseChatModel,
        max_messages_trigger: int = 10,
        max_tokens_trigger: int = 4000,
        messages_to_keep: int = 4,
        enable_history_recovery: bool = True,
        enable_summarization: bool = True,
        enable_context_retrieval: bool = True,
        max_retrieved_summaries: int = 3,
        min_retrieval_score: float = 0.3,
    ):
        super().__init__()
        self.summary_model = summary_model
        self.max_messages_trigger = max_messages_trigger
        self.max_tokens_trigger = max_tokens_trigger
        self.messages_to_keep = messages_to_keep
        self.enable_history_recovery = enable_history_recovery
        self.enable_summarization = enable_summarization
        self.enable_context_retrieval = enable_context_retrieval
        self.max_retrieved_summaries = max_retrieved_summaries
        self.min_retrieval_score = min_retrieval_score

    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        """Agent 开始前: 恢复历史消息 + 检索相关上下文"""
        context = runtime.context
        if not context:
            return None

        session_id = getattr(context, "session_id", None)
        user_id = getattr(context, "user_id", None)
        messages = state.get("messages", [])

        updates = {}

        # 历史恢复（仅首次请求）
        if self.enable_history_recovery and len(messages) <= 1:
            recovered = self._recover_history(session_id)
            if recovered:
                current_msg = messages[-1] if messages else None
                final_messages = recovered.copy()
                if current_msg and isinstance(current_msg, HumanMessage):
                    final_messages.append(current_msg)
                updates["messages"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + final_messages
                logger.info(f"恢复 {len(recovered)} 条历史消息, session={session_id[:8]}...")

        # 相关上下文检索
        if self.enable_context_retrieval and session_id:
            query = extract_user_query(messages)
            if query and len(query.strip()) >= 5:
                summaries = self._retrieve_context(query, session_id, user_id)
                if summaries and context:
                    context.retrieved_summaries = summaries
                    logger.info(f"检索到 {len(summaries)} 条相关上下文")

        return updates if updates else None

    def before_model(self, state: dict, runtime: Runtime) -> Optional[Dict[str, Any]]:
        """LLM 调用前: 检查是否需要摘要压缩"""
        if not self.enable_summarization:
            return None

        messages = state.get("messages", [])
        if not self._should_summarize(messages):
            return None

        context = runtime.context
        session_id = getattr(context, "session_id", None) if context else None
        if not session_id:
            return None

        try:
            messages_to_keep, messages_to_summarize = self._split_messages(messages)
            if not messages_to_summarize:
                return None

            summary_content = self._generate_summary(messages_to_summarize)
            if not summary_content:
                return None

            summary_id = f"summary-{generate_id()}"
            summary_msg = HumanMessage(
                content=f"{SUMMARY_PREFIX}\n{summary_content}",
                id=summary_id,
            )

            # 异步持久化，不阻塞主流程
            self._persist_summary_async(
                summary_id=summary_id,
                user_id=getattr(context, "user_id", None),
                session_id=session_id,
                content=summary_content,
                messages=messages_to_summarize,
            )

            new_messages = [summary_msg] + messages_to_keep
            logger.info(
                f"摘要: {len(messages_to_summarize)} 条 → 1 条, "
                f"保留 {len(messages_to_keep)} 条近期消息"
            )

            return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + new_messages}

        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            return None

    # --- 历史恢复 ---

    def _recover_history(self, session_id: str) -> List[BaseMessage]:
        """从 MySQL 恢复历史消息（优先从摘要恢复）"""
        try:
            from app.services.chat_storage_service import ChatStorageService

            latest_summary = ChatStorageService.get_latest_summary(session_id)
            if latest_summary:
                recovered = [HumanMessage(
                    content=f"{SUMMARY_PREFIX}\n{latest_summary.content}",
                    id=latest_summary.summary_id,
                )]
                recent = ChatStorageService.get_messages_after_summary(
                    session_id=session_id,
                    end_msg_id=latest_summary.mes_id_end,
                )
                for db_msg in recent:
                    msg = self._convert_db_message(db_msg)
                    if msg:
                        recovered.append(msg)
                return recovered

            recent = ChatStorageService.get_messages_by_session(
                session_id=session_id,
                limit=self.messages_to_keep,
                order_desc=False,
            )
            return [m for db in recent if (m := self._convert_db_message(db))]

        except Exception as e:
            logger.error(f"历史恢复失败: {e}")
            return []

    @staticmethod
    def _convert_db_message(db_msg) -> Optional[BaseMessage]:
        role = getattr(db_msg, "role", None)
        content = getattr(db_msg, "content", None)
        msg_id = getattr(db_msg, "msg_id", None)
        if not role or not content:
            return None
        if role == "human":
            return HumanMessage(content=content, id=msg_id)
        elif role == "ai":
            return AIMessage(content=content, id=msg_id)
        return None

    # --- 上下文检索 ---

    def _retrieve_context(
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
        from app.services.summary_milvus_service import get_summary_milvus_service
        svc = get_summary_milvus_service()

        all_results = []

        # 当前会话
        results = await svc.hybrid_search(query=query, session_id=session_id,
                                          top_k=self.max_retrieved_summaries)
        for r in results:
            if r.get("score", 0) >= self.min_retrieval_score:
                r["source"] = "current"
                all_results.append(r)

        # 跨会话
        results = await svc.hybrid_search(query=query, session_id=None,
                                          top_k=self.max_retrieved_summaries)
        for r in results:
            if r.get("session_id") == session_id:
                continue
            if r.get("score", 0) >= self.min_retrieval_score:
                r["source"] = "history"
                all_results.append(r)

        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:self.max_retrieved_summaries]

    # --- 摘要生成 ---

    def _should_summarize(self, messages: List[BaseMessage]) -> bool:
        if len(messages) >= self.max_messages_trigger:
            return True
        token_count = sum(len(extract_text_content(m.content)) // 3 for m in messages)
        return token_count >= self.max_tokens_trigger

    def _split_messages(
        self, messages: List[BaseMessage]
    ) -> Tuple[List[BaseMessage], List[BaseMessage]]:
        if len(messages) <= self.messages_to_keep:
            return messages, []

        split_idx = len(messages) - self.messages_to_keep

        # 避免拆开 AI/Tool 消息对
        while split_idx < len(messages) and isinstance(messages[split_idx], ToolMessage):
            split_idx -= 1

        return messages[split_idx:], messages[:split_idx]

    def _generate_summary(self, messages: List[BaseMessage]) -> Optional[str]:
        try:
            formatted = "\n".join(
                f"{'用户' if isinstance(m, HumanMessage) else '助手'}: "
                f"{extract_text_content(m.content)}"
                for m in messages
                if extract_text_content(m.content)
            )

            prompt = f"""请简洁地总结以下对话，保留关键信息:
- 用户的主要问题和需求
- 已执行的操作和结果
- 重要数据（订单号、金额等）

对话:
{formatted}

摘要（300字以内）:"""

            response = self.summary_model.invoke([
                HumanMessage(content=prompt, id=f"summary-{generate_id()}")
            ])
            return response.content.strip()
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return None

    def _persist_summary_async(self, **kwargs):
        """异步持久化摘要到 MySQL + Milvus"""
        def _do_persist():
            try:
                from app.services.chat_storage_service import ChatStorageService

                msg_ids = [m.id for m in kwargs.get("messages", []) if m.id]

                ChatStorageService.save_summary(
                    summary_id=kwargs["summary_id"],
                    user_id=kwargs["user_id"],
                    session_id=kwargs["session_id"],
                    content=kwargs["content"],
                    mes_id_start=msg_ids[0] if msg_ids else None,
                    mes_id_end=msg_ids[-1] if msg_ids else None,
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from app.services.summary_milvus_service import get_summary_milvus_service
                svc = get_summary_milvus_service()
                loop.run_until_complete(svc.save_summary_vector(
                    context_text=kwargs["content"],
                    user_id=kwargs["user_id"],
                    session_id=kwargs["session_id"],
                    summary_id=kwargs["summary_id"],
                ))
            except Exception as e:
                logger.error(f"摘要持久化失败: {e}")

        _executor.submit(_do_persist)
