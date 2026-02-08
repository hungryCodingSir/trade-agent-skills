package com.cbec.mcp.common.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("shipping_track")
public class ShippingTrack implements Serializable {
    private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long shippingId;
    private LocalDateTime trackTime;
    private String location;
    private String status;
    private String description;
    private LocalDateTime createdAt;
}
