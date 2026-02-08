package com.cbec.mcp.common.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("order_info")
public class OrderInfo implements Serializable {
    private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO)
    private Long id;
    private String orderNo;
    private Long buyerId;
    private Long sellerId;
    private BigDecimal totalAmount;
    private BigDecimal shippingFee;
    private BigDecimal taxAmount;
    private String currency;
    private String orderStatus;
    private String paymentStatus;
    private String paymentMethod;
    private LocalDateTime paidAt;
    private String shippingMethod;
    private String shippingAddress;
    private String buyerRemark;
    private String sellerRemark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
