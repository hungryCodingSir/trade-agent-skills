"""消息持久化中间件 — 将用户消息和 AI 响应保存到 MySQL"""
from typing import Any, Optional, Dict

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from loguru import logger

from app.utils.message_utils import extract_text_content


class PersistenceMiddleware(AgentMiddleware):
    """before_agent 保存用户消息，after_agent 保存 AI 响应"""

    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        context = runtime.context
        if not context:
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, HumanMessage):
            return None

        content = extract_text_content(last_msg.content)
        self._save(
            msg_id=last_msg.id,
            user_id=getattr(context, "user_id", None),
            session_id=getattr(context, "session_id", None),
            role="human",
            content=content,
        )
        return None

    def after_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        context = runtime.context
        if not context:
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        content = extract_text_content(last_msg.content)
        if not content or not content.strip():
            return None

        self._save(
            msg_id=last_msg.id,
            user_id=getattr(context, "user_id", None),
            session_id=getattr(context, "session_id", None),
            role="ai",
            content=content,
        )
        return None

    @staticmethod
    def _save(msg_id: str, user_id: int, session_id: str, role: str, content: str):
        try:
            from app.services.chat_storage_service import ChatStorageService
            ChatStorageService.save_message(
                msg_id=msg_id,
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
            )
            logger.debug(f"Persisted {role} message, session={session_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to persist {role} message: {e}")
