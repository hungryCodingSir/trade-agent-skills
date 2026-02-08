"""
Human-in-the-Loop 中断处理器

通过 LangGraph interrupt() + Command(resume=...) 实现邮件发送前的人工确认。
图在 interrupt() 处暂停并持久化到 Checkpointer，前端展示邮件预览，
用户做出 approve/reject/edit 决策后通过 Command(resume=...) 恢复执行。
"""
from enum import Enum
from typing import Any, Dict, Optional

from langgraph.types import interrupt
from loguru import logger


class InterruptDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


def request_email_confirmation(
    to_email: str,
    subject: str,
    content: str,
    email_type: str = "GENERAL",
    cc_email: Optional[str] = None,
    related_order_id: Optional[int] = None,
) -> Dict[str, Any]:
    """触发邮件发送确认中断，暂停图执行并将预览信息推送给前端。"""

    email_preview = {
        "interrupt_type": "email_confirmation",
        "title": "📧 邮件发送确认",
        "description": "以下邮件待您确认后发送，请审阅内容：",
        "email_preview": {
            "to": to_email,
            "cc": cc_email,
            "subject": subject,
            "body": content,
            "type": email_type,
            "related_order_id": related_order_id,
        },
        "available_actions": [
            {"action": "approve", "label": "✅ 确认发送"},
            {"action": "reject",  "label": "❌ 取消发送"},
            {"action": "edit",    "label": "✏️ 修改内容"},
        ],
    }

    logger.info(f"[Interrupt] 等待邮件确认 → to={to_email}, subject={subject}")

    decision = interrupt(email_preview)

    logger.info(f"[Interrupt] 用户决策: {decision}")
    return decision


def handle_email_decision(
    decision: Dict[str, Any],
    original_email: Dict[str, str],
) -> Dict[str, Any]:
    """
    处理用户的邮件审批决策，返回 send 或 cancel 指令。

    decision 格式:
        approve → {"decision": "approve"}
        reject  → {"decision": "reject", "reason": "..."}
        edit    → {"decision": "edit", "edited_subject": "...", "edited_content": "..."}
    """
    action = decision.get("decision", "reject")

    if action == InterruptDecision.APPROVE:
        return {
            "action": "send",
            "email": original_email,
            "message": "用户已确认，正在发送邮件...",
        }

    elif action == InterruptDecision.EDIT:
        edited_email = {**original_email}
        if "edited_subject" in decision:
            edited_email["subject"] = decision["edited_subject"]
        if "edited_content" in decision:
            edited_email["content"] = decision["edited_content"]
        if "edited_to_email" in decision:
            edited_email["to_email"] = decision["edited_to_email"]

        return {
            "action": "send",
            "email": edited_email,
            "message": "用户已修改内容，正在发送邮件...",
        }

    else:
        reason = decision.get("reason", "用户取消发送")
        return {
            "action": "cancel",
            "reason": reason,
            "message": f"邮件已取消发送。原因: {reason}",
        }
