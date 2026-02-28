"""聊天消息存储服务"""
from loguru import logger
from app.config.database import get_db_session
from app.models.db_models import ChatMessage
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