package com.cbec.mcp.server.dto;

import lombok.Data;

/**
 * 邮件发送请求参数。
 */
@Data
public class EmailSendRequest {
    private Long userId;
    private String toEmail;
    private String ccEmail;
    private String subject;
    private String content;
    private String emailType;
    private Long relatedOrderId;
}
