"""消息内容提取工具"""
from typing import Union, List, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage


def extract_text_content(content: Union[str, List, Any]) -> str:
    """从消息内容中提取纯文本（兼容 str / list / dict 格式）"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif "text" in item:
                    parts.append(item["text"])
        return "\n".join(parts) if parts else ""
    return str(content)


def extract_user_query(messages: List[BaseMessage]) -> Optional[str]:
    """从消息列表中提取最新的用户问题"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        return item
                    if isinstance(item, dict) and item.get("type") == "text":
                        return item.get("text", "")
    return None
