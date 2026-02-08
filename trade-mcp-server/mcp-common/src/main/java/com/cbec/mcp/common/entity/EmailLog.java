package com.cbec.mcp.common.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("email_log")
public class EmailLog implements Serializable {
    private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long userId;
    private String toEmail;
    private String ccEmail;
    private String subject;
    private String content;
    private String emailType;
    private Long relatedOrderId;
    private String status;
    private LocalDateTime sentAt;
    private String errorMsg;
    private Integer retryCount;
    private LocalDateTime createdAt;
}
