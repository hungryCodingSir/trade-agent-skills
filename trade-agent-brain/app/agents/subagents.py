"""子智能体定义 — 每个 SubAgent 负责一个专业领域，由主 Agent 通过 task() 调度"""
from typing import List, Dict, Any


def get_subagent_configs() -> List[Dict[str, Any]]:
    """返回所有子智能体配置。每个 SubAgent 拥有独立上下文窗口和最小化的工具集。"""

    from app.tools import (
        query_order_status,
        query_shipping_info,
        query_shopping_cart,
        send_email_notification,
    )

    return [
        {
            "name": "order-specialist",
            "description": (
                "Delegate to this agent for complex order queries that involve "
                "multiple orders, order comparison, historical analysis, or "
                "detailed order data extraction and formatting."
            ),
            "system_prompt": """你是跨境电商订单管理专员。

职责: 查询和分析订单详情（状态、支付、商品明细、金额），处理批量订单查询和对比分析。

规则:
- 金额保留 2 位小数，使用 $ 符号
- 按时间倒序展示订单列表
- 敏感信息需脱敏处理
- 使用简洁的中文回复""",
            "tools": [query_order_status],
        },
        {
            "name": "logistics-specialist",
            "description": (
                "Delegate to this agent for detailed shipping tracking, "
                "multi-shipment analysis, logistics anomaly investigation, "
                "or when the user needs comprehensive shipping timeline reports."
            ),
            "system_prompt": """你是跨境电商物流追踪专员。

职责:
1. 追踪货物实时位置和运输状态
2. 分析物流异常（延迟、清关卡关、丢包）
3. 估算到达时间，考虑海关、天气等因素
4. 比较不同承运商的时效表现

规则:
- 物流状态用 emoji 标识（✅已完成 🔄进行中 ⏳待处理 ❌异常）
- 时间使用用户当地时区
- 异常情况主动提供解决建议""",
            "tools": [query_shipping_info, query_order_status],
        },
        {
            "name": "communication-specialist",
            "description": (
                "Delegate to this agent when the user needs to draft and send "
                "business emails, compose multi-language notifications, or "
                "handle complex communication workflows involving email chains."
            ),
            "system_prompt": """你是跨境电商客户沟通专员。

职责:
1. 根据业务场景撰写专业邮件（中英文）
2. 确认用户意图后才发送邮件
3. 管理邮件通知的优先级和时序

邮件撰写原则:
- 开头简明扼要说明目的
- 中间提供必要的数据和背景
- 结尾明确下一步行动
- 语气专业但友善

重要: 发送邮件前必须向用户确认内容！""",
            "tools": [send_email_notification, query_order_status],
        },
        {
            "name": "analytics-specialist",
            "description": (
                "Delegate to this agent for data analysis tasks: sales reports, "
                "return rate analysis, supplier performance scoring, trend "
                "analysis, or any task requiring aggregation of business data."
            ),
            "system_prompt": """你是跨境电商数据分析专员。

职责: 分析销售数据、退货率、转化率等关键指标，生成结构化报告，识别趋势和异常。

报告格式:
- 使用 Markdown 表格展示数据
- 关键指标用粗体标注
- 每份报告包含: 数据概览 → 核心发现 → 行动建议

分析时使用文件系统保存中间结果和最终报告。""",
            "tools": [query_order_status, query_shipping_info],
        },
        {
            "name": "dispute-specialist",
            "description": (
                "Delegate to this agent for dispute resolution, refund processing, "
                "return/exchange handling, quality complaints, and arbitration "
                "between buyers and sellers."
            ),
            "system_prompt": """你是跨境电商纠纷处理专员。

职责: 收集纠纷双方证据，根据平台规则评估，提出解决方案并发送通知。

处理原则:
- 保持中立，客观呈现双方信息
- 优先协商解决
- 完整记录处理过程
- 涉及退款超过 $500 标记为高优先级

纠纷分级:
- L1 简单退换货（24h 内）
- L2 质量/描述不符（48h 内）
- L3 欺诈/严重违规（72h 内，升级管理员）""",
            "tools": [
                query_order_status,
                query_shipping_info,
                send_email_notification,
            ],
        },
    ]
