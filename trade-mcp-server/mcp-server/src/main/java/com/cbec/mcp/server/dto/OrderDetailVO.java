package com.cbec.mcp.server.dto;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 订单详情视图，包含订单头信息与商品明细行。
 */
@Data
public class OrderDetailVO {
    private Long orderId;
    private String orderNo;
    private String buyerName;
    private String sellerName;
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
    private LocalDateTime createdAt;
    private List<OrderItemVO> items;

    @Data
    public static class OrderItemVO {
        private Long productId;
        private String productName;
        private String productSku;
        private BigDecimal unitPrice;
        private Integer quantity;
        private BigDecimal subtotal;
    }
}
