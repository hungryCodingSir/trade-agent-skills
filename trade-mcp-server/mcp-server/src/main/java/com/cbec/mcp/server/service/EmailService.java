package com.cbec.mcp.server.service;

import com.cbec.mcp.common.entity.EmailLog;
import com.cbec.mcp.common.enums.EmailType;
import com.cbec.mcp.server.mapper.EmailLogMapper;
import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;

/**
 * 邮件领域服务，负责邮件的实际发送以及发送记录的持久化。
 * <p>
 * 发送结果（成功/失败）均会记录到 email_log 表，便于后续审计与重试。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EmailService {

    private final JavaMailSender mailSender;
    private final EmailLogMapper emailLogMapper;

    @Value("${spring.mail.username}")
    private String fromEmail;

    /**
     * 发送 HTML 邮件并持久化发送记录。
     *
     * @param toEmail        收件人
     * @param subject        主题
     * @param content        正文（支持 HTML）
     * @param emailType      邮件类型枚举名，解析失败时降级为 GENERAL
     * @param relatedOrderId 关联订单ID，可为 null
     * @param ccEmail        抄送地址，可为 null
     * @param userId         操作用户ID，可为 null
     * @return 持久化后的 EmailLog（含生成的 id）
     */
    public EmailLog send(String toEmail, String subject, String content,
                         String emailType, Long relatedOrderId,
                         String ccEmail, Long userId) {

        EmailType type = resolveType(emailType);

        try {
            doSend(toEmail, subject, content, ccEmail);
            log.info("邮件发送成功: to={}", toEmail);
            return saveLog(userId, toEmail, ccEmail, subject, content,
                    type, relatedOrderId, "SENT", null);
        } catch (Exception e) {
            log.error("邮件发送失败: to={}", toEmail, e);
            saveLog(userId, toEmail, ccEmail, subject, content,
                    type, relatedOrderId, "FAILED", e.getMessage());
            throw new RuntimeException("邮件发送失败: " + e.getMessage(), e);
        }
    }

    private void doSend(String toEmail, String subject, String content, String ccEmail) throws Exception {
        MimeMessage message = mailSender.createMimeMessage();
        MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");
        helper.setFrom(fromEmail);
        helper.setTo(toEmail.trim());
        helper.setSubject(subject);
        helper.setText(content, true);
        if (StringUtils.hasText(ccEmail)) {
            helper.setCc(ccEmail.trim());
        }
        mailSender.send(message);
    }

    private EmailLog saveLog(Long userId, String toEmail, String ccEmail,
                             String subject, String content, EmailType type,
                             Long relatedOrderId, String status, String errorMsg) {
        EmailLog emailLog = new EmailLog();
        emailLog.setUserId(userId);
        emailLog.setToEmail(toEmail.trim());
        emailLog.setCcEmail(ccEmail);
        emailLog.setSubject(subject);
        emailLog.setContent(content);
        emailLog.setEmailType(type.name());
        emailLog.setRelatedOrderId(relatedOrderId);
        emailLog.setStatus(status);
        emailLog.setSentAt("SENT".equals(status) ? LocalDateTime.now() : null);
        emailLog.setErrorMsg(errorMsg);
        emailLog.setRetryCount(0);
        emailLog.setCreatedAt(LocalDateTime.now());
        try {
            emailLogMapper.insert(emailLog);
        } catch (Exception ex) {
            log.error("持久化邮件日志失败", ex);
        }
        return emailLog;
    }

    private EmailType resolveType(String emailType) {
        if (!StringUtils.hasText(emailType)) {
            return EmailType.GENERAL;
        }
        try {
            return EmailType.valueOf(emailType.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            log.warn("无法识别的邮件类型 '{}', 降级为 GENERAL", emailType);
            return EmailType.GENERAL;
        }
    }
}
