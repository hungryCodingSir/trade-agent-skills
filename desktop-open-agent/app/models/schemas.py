"""请求 / 响应数据模型"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DesktopRequest(BaseModel):
    """桌面操作请求"""
    message: str = Field(..., description="自然语言指令，如: 帮我打开微信")
    session_id: Optional[str] = Field(None, description="会话ID（可选，自动生成）")
    stream: bool = Field(False, description="是否使用 SSE 流式响应")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"message": "帮我打开微信"},
                {"message": "打开浏览器", "stream": True},
                {"message": "你能打开哪些应用？"},
            ]
        }
    }


class ApiResponse(BaseModel):
    """统一 API 响应"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)
