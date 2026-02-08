package com.cbec.mcp.server.dto;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 购物车条目视图，关联商品表后的完整展示字段。
 */
@Data
public class CartItemVO {
    private Long cartId;
    private Long productId;
    private String productName;
    private String productNameEn;
    private String sku;
    private BigDecimal unitPrice;
    private String currency;
    private Integer quantity;
    private BigDecimal subtotal;
    private Integer selected;
    private Integer stockQuantity;
    private Integer minOrderQuantity;
    private String originCountry;
    private LocalDateTime addedAt;
}
