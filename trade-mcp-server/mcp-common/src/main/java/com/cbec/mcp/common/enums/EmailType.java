package com.cbec.mcp.common.enums;

/**
 * 跨境电商场景下的邮件类型，每种类型对应一个默认模板。
 */
public enum EmailType {

    SHIPPING_DELAY("物流延迟通知",
            "您的订单 %s 物流出现延迟，预计延后 %s 天到达，敬请谅解。"),
    LATE_SHIPMENT("延迟发货通知",
            "您的订单 %s 由于供应商备货原因，发货时间将延后，我们会尽快为您处理。"),
    ORDER_CONFIRM("订单确认通知",
            "您的订单 %s 已确认，卖家正在处理中，请耐心等待。"),
    PAYMENT_REMIND("付款提醒",
            "您的订单 %s 尚未完成付款，请在 %s 前完成支付，避免订单自动取消。"),
    CUSTOMS_ALERT("清关提醒",
            "您的订单 %s 正在进行海关清关，预计需要 %s 个工作日，请您耐心等待。"),
    GENERAL("通用通知", "%s");

    private final String label;
    private final String template;

    EmailType(String label, String template) {
        this.label = label;
        this.template = template;
    }

    public String getLabel() {
        return label;
    }

    public String getTemplate() {
        return template;
    }
}
