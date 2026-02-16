import os
from datetime import datetime
from typing import Any, Dict, List
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from loguru import logger


class PromptLoggerCallback(BaseCallbackHandler):
    """打印发送给 LLM 的完整提示词（包括所有中间件增强内容）"""

    def __init__(self):
        super().__init__()
        self.output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "output"
        )
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[BaseMessage]],
            **kwargs: Any,
    ) -> None:
        """在调用 Chat Model 前触发 - 此时所有中间件已处理完毕"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"prompt_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)

        lines = ["=" * 80, f"🚀 发送给大模型的完整提示词", "=" * 80]

        for batch_idx, message_batch in enumerate(messages):
            if len(messages) > 1:
                lines.append(f"--- Batch {batch_idx + 1} ---")

            for idx, msg in enumerate(message_batch):
                role = self._get_role_name(msg)
                icon = self._get_role_icon(msg)

                lines.append(f"\n{icon} 【{role}】(第 {idx + 1} 条)")
                lines.append("-" * 40)
                lines.append(self._format_content(msg.content))

        total_chars = sum(len(str(m.content)) for batch in messages for m in batch)
        lines.append("=" * 80)
        lines.append(f"📊 消息总数: {sum(len(b) for b in messages)}, 总字符数: {total_chars}")
        lines.append("=" * 80)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"📄 提示词已保存到: {filepath}")

    def _format_content(self, content: Any) -> str:
        """将消息内容格式化为字符串，处理多模态消息等复杂类型"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        parts.append(f"[图片: {item.get('image_url', {}).get('url', 'N/A')[:50]}...]")
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        else:
            return str(content)

    def _get_role_name(self, msg: BaseMessage) -> str:
        if isinstance(msg, SystemMessage):
            return "System (系统提示词/动态注入)"
        elif isinstance(msg, HumanMessage):
            return "Human (用户输入)"
        elif isinstance(msg, AIMessage):
            return "AI (助手回复)"
        return msg.__class__.__name__.replace("Message", "")

    def _get_role_icon(self, msg: BaseMessage) -> str:
        if isinstance(msg, SystemMessage):
            return "⚙️"
        elif isinstance(msg, HumanMessage):
            return "👤"
        elif isinstance(msg, AIMessage):
            return "🤖"
        return "📝"


# 全局回调实例
prompt_logger = PromptLoggerCallback()