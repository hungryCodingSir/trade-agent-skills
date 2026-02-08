"""
MCP 工具包

通过 MCP SSE 协议连接 Java cbec-mcp-server，提供:
- query_shopping_cart     购物车查询
- query_order_status      订单状态查询
- query_shipping_info     物流信息查询
- send_email_notification 邮件发送（带 Human-in-the-Loop 确认）
"""
import json
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from loguru import logger

from app.config.settings import settings


async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """通过 MCP SSE 调用 Java Server 上的工具"""
    from mcp.client.sse import sse_client
    from mcp import ClientSession

    logger.debug(f"MCP call: tool={tool_name}, args={arguments}")

    try:
        async with sse_client(
            url=settings.mcp_server_url,
            timeout=settings.mcp_call_timeout,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

                if result.isError:
                    error = result.content[0].text if result.content else "Unknown error"
                    logger.error(f"MCP error: {tool_name} → {error}")
                    return json.dumps({"success": False, "error": error}, ensure_ascii=False)

                if result.content:
                    return result.content[0].text

                return json.dumps({"success": True, "data": None}, ensure_ascii=False)

    except ConnectionRefusedError:
        msg = f"MCP Server 连接失败 ({settings.mcp_server_url})"
        logger.error(msg)
        return json.dumps({"success": False, "error": msg}, ensure_ascii=False)

    except TimeoutError:
        msg = f"MCP 调用超时 ({settings.mcp_call_timeout}s), tool={tool_name}"
        logger.error(msg)
        return json.dumps({"success": False, "error": msg}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"MCP 调用异常: {type(e).__name__}: {e}")
        return json.dumps({"success": False, "error": f"MCP 服务调用失败: {e}"}, ensure_ascii=False)


# --- Tool 定义 ---

@tool
async def query_order_status(order_no: str) -> str:
    """根据订单编号查询订单详情，包括订单状态、支付情况、商品明细、金额汇总等。

    Args:
        order_no: 订单编号，格式如 ORD20240101001
    """
    return await call_mcp_tool("queryOrderStatus", {"orderNo": order_no})


@tool
async def query_shopping_cart(config: RunnableConfig) -> str:
    """查询当前用户的购物车，返回所有商品详情（名称、单价、数量、库存、卖家信息）。"""
    user_id = config.get("configurable", {}).get("user_id")
    if user_id is None:
        return "无法获取用户信息，请重新登录"
    return await call_mcp_tool("queryShoppingCart", {"userId": user_id})


@tool
async def query_shipping_info(order_no: str) -> str:
    """根据订单编号查询物流信息，包括运单号、承运商、物流状态、清关进度、轨迹记录等。

    Args:
        order_no: 订单编号，格式如 ORD20240101001
    """
    return await call_mcp_tool("queryShippingInfo", {"orderNo": order_no})


@tool
async def send_email_notification(
    to_email: str,
    subject: str,
    content: str,
    email_type: str = "GENERAL",
    related_order_id: Optional[int] = None,
    cc_email: Optional[str] = None,
    user_id: Optional[int] = None,
) -> str:
    """发送邮件通知（触发 Human-in-the-Loop 确认）。

    支持类型: SHIPPING_DELAY, LATE_SHIPMENT, ORDER_CONFIRM, PAYMENT_REMIND, CUSTOMS_ALERT, GENERAL

    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        content: 邮件正文
        email_type: 邮件类型
        related_order_id: 关联订单ID
        cc_email: 抄送邮箱
        user_id: 操作用户ID
    """
    from app.agents.interrupt_handler import (
        request_email_confirmation,
        handle_email_decision,
    )

    # 暂停图执行，等待用户确认
    decision = request_email_confirmation(
        to_email=to_email,
        subject=subject,
        content=content,
        email_type=email_type,
        cc_email=cc_email,
        related_order_id=related_order_id,
    )

    original_email = {
        "to_email": to_email,
        "subject": subject,
        "content": content,
        "email_type": email_type,
        "cc_email": cc_email,
        "related_order_id": related_order_id,
    }
    result = handle_email_decision(decision, original_email)

    if result["action"] == "cancel":
        logger.info(f"邮件已取消: {result['reason']}")
        return json.dumps({
            "success": True,
            "cancelled": True,
            "message": result["message"],
        }, ensure_ascii=False)

    # 确认或编辑后发送
    email = result["email"]
    arguments: dict = {
        "toEmail": email["to_email"],
        "subject": email["subject"],
        "content": email["content"],
        "emailType": email["email_type"],
    }
    if email.get("related_order_id") is not None:
        arguments["relatedOrderId"] = email["related_order_id"]
    if email.get("cc_email"):
        arguments["ccEmail"] = email["cc_email"]
    if user_id is not None:
        arguments["userId"] = user_id

    mcp_result = await call_mcp_tool("sendEmailNotification", arguments)
    logger.info(f"邮件已发送: to={email['to_email']}, subject={email['subject']}")
    return mcp_result


# --- 工具注册 ---

_TOOL_REGISTRY: List[BaseTool] = [
    query_shopping_cart,
    query_order_status,
    query_shipping_info,
    send_email_notification,
]


def get_all_tools() -> List[BaseTool]:
    return list(_TOOL_REGISTRY)


def get_tool_names() -> List[str]:
    return [t.name for t in _TOOL_REGISTRY]
