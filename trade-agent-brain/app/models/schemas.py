"""Pydantic 数据模型"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class UserType(str, Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    ADMIN = "ADMIN"


class UserContext(BaseModel):
    user_id: int
    username: str
    user_type: UserType
    company_name: Optional[str] = None
    language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"


class AgentRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = False


class ResumeRequest(BaseModel):
    """中断恢复请求 — 用户审批邮件后提交"""
    session_id: str
    decision: str  # approve / reject / edit
    reason: Optional[str] = None
    edited_subject: Optional[str] = None
    edited_content: Optional[str] = None
    edited_to_email: Optional[str] = None


class AgentResponse(BaseModel):
    message: str
    session_id: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)
