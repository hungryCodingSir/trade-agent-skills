"""SQLAlchemy ORM 模型"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime
from app.config.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    msg_id = Column(String(64), nullable=False, comment="消息ID")
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False, comment="human/ai/tool")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

