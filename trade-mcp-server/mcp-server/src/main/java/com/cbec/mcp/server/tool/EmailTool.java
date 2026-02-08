package com.cbec.mcp.server.tool;

import com.cbec.mcp.common.entity.EmailLog;
import com.cbec.mcp.common.result.McpResult;
import com.cbec.mcp.common.util.JsonUtil;
import com.cbec.mcp.server.service.EmailService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.util.HashMap;
import java.util.Map;

/**
 * 邮件 MCP 工具，向 LLM 暴露邮件发送能力。
 * <p>
 * 支持多种跨境电商场景的邮件通知，发送结果会持久化到 email_log 表。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class EmailTool {

    private final EmailService emailService;

    @Tool(name = "sendEmailNotification",
          description = "发送邮件通知，支持多种跨境电商场景：物流延迟(SHIPPING_DELAY)、延迟发货(LATE_SHIPMENT)、"
                      + "订单确认(ORDER_CONFIRM)、付款提醒(PAYMENT_REMIND)、清关提醒(CUSTOMS_ALERT)、"
                      + "通用通知(GENERAL)。发送后会记录到邮件日志表中。")
    public String sendEmailNotification(
            @ToolParam(description = "收件人邮箱地址，必填") String toEmail,
            @ToolParam(description = "邮件主题，必填") String subject,
            @ToolParam(description = "邮件正文内容，必填") String content,
            @ToolParam(description = "邮件类型：SHIPPING_DELAY/LATE_SHIPMENT/ORDER_CONFIRM/PAYMENT_REMIND/CUSTOMS_ALERT/GENERAL，默认GENERAL") String emailType,
            @ToolParam(description = "关联订单ID，选填，用于日志记录关联") Long relatedOrderId,
            @ToolParam(description = "抄送邮箱，选填") String ccEmail,
            @ToolParam(description = "发起操作的用户ID，选填，用于日志记录") Long userId) {

        log.info("sendEmailNotification called, to={}, type={}", toEmail, emailType);

        if (!StringUtils.hasText(toEmail)) {
            return JsonUtil.toJson(McpResult.fail("收件人邮箱不能为空"));
        }
        if (!StringUtils.hasText(subject)) {
            return JsonUtil.toJson(McpResult.fail("邮件主题不能为空"));
        }
        if (!StringUtils.hasText(content)) {
            return JsonUtil.toJson(McpResult.fail("邮件内容不能为空"));
        }

        try {
            EmailLog emailLog = emailService.send(toEmail, subject, content,
                    emailType, relatedOrderId, ccEmail, userId);

            Map<String, Object> result = new HashMap<>();
            result.put("emailLogId", emailLog.getId());
            result.put("toEmail", toEmail);
            result.put("emailType", emailLog.getEmailType());
            result.put("sentAt", emailLog.getSentAt() != null ? emailLog.getSentAt().toString() : null);

            return JsonUtil.toJson(McpResult.ok("邮件发送成功", result));
        } catch (Exception e) {
            log.error("发送邮件异常", e);
            return JsonUtil.toJson(McpResult.fail("邮件发送失败: " + e.getMessage()));
        }
    }
}
