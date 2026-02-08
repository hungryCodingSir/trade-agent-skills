"""聊天消息存储服务"""
from typing import List, Optional
from sqlalchemy.orm import Session
from loguru import logger
from app.config.database import get_db_session
from app.models.db_models import ChatMessage, ChatMessageSummary
from app.utils.snowflake import generate_id


class ChatStorageService:

    @staticmethod
    def save_message(msg_id: str, user_id: int, session_id: str, role: str, content: str):
        message = ChatMessage(
            id=generate_id(), msg_id=msg_id, user_id=user_id,
            session_id=session_id, role=role, content=content,
        )
        with get_db_session() as session:
            session.add(message)
            logger.debug(f"Saved {role} message, session={session_id[:8]}...")
        return message

    @staticmethod
    def save_summary(summary_id: str, user_id: int, session_id: str, content: str,
                     mes_id_start: str, mes_id_end: str):
        summary = ChatMessageSummary(
            id=generate_id(), summary_id=summary_id, user_id=user_id,
            session_id=session_id, content=content,
            mes_id_start=mes_id_start, mes_id_end=mes_id_end,
        )
        with get_db_session() as session:
            session.add(summary)
            logger.info(f"Summary saved, session={session_id[:8]}...")
        return summary

    @staticmethod
    def get_messages_by_session(session_id: str, limit: int = None, order_desc: bool = False):
        with get_db_session() as session:
            q = session.query(ChatMessage).filter(ChatMessage.session_id == session_id)
            q = q.order_by(ChatMessage.created_at.desc() if order_desc else ChatMessage.created_at.asc())
            if limit:
                q = q.limit(limit)
            messages = q.all()
            for m in messages:
                _ = m.role, m.content, m.msg_id
                session.expunge(m)
            return messages

    @staticmethod
    def get_latest_summary(session_id: str) -> Optional[ChatMessageSummary]:
        with get_db_session() as session:
            summary = session.query(ChatMessageSummary).filter(
                ChatMessageSummary.session_id == session_id
            ).order_by(ChatMessageSummary.created_at.desc()).first()
            if summary:
                _ = summary.content, summary.summary_id, summary.mes_id_end
                session.expunge(summary)
            return summary

    @staticmethod
    def get_messages_after_summary(session_id: str, end_msg_id: str):
        with get_db_session() as session:
            end_msg = session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.msg_id == end_msg_id,
            ).first()
            if not end_msg:
                return []
            messages = session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.id > end_msg.id,
            ).order_by(ChatMessage.created_at.asc()).all()
            for m in messages:
                _ = m.role, m.content, m.msg_id
                session.expunge(m)
            return messages
