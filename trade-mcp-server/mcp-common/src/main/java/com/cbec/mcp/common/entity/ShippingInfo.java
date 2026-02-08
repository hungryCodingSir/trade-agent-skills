package com.cbec.mcp.common.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("shipping_info")
public class ShippingInfo implements Serializable {
    private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long orderId;
    private String trackingNo;
    private String carrier;
    private String shippingMethod;
    private String originPort;
    private String destinationPort;
    private LocalDate estimatedDeparture;
    private LocalDate actualDeparture;
    private LocalDate estimatedArrival;
    private LocalDate actualArrival;
    private String customsStatus;
    private String shippingStatus;
    private String packageInfo;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
