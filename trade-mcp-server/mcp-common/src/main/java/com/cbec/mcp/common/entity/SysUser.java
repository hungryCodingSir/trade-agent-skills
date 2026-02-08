package com.cbec.mcp.common.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("sys_user")
public class SysUser implements Serializable {
    private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO)
    private Long id;
    private String username;
    private String password;
    private String email;
    private String phone;
    private String userType;
    private String companyName;
    private String country;
    private String timezone;
    private String language;
    private String avatarUrl;
    private Integer status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
