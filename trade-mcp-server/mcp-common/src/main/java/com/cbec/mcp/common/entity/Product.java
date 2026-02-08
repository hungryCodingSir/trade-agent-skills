package com.cbec.mcp.common.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("product")
public class Product implements Serializable {
    private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long sellerId;
    private Long categoryId;
    private String sku;
    private String nameZh;
    private String nameEn;
    private String description;
    private BigDecimal price;
    private String currency;
    private Integer stockQuantity;
    private Integer minOrderQuantity;
    private BigDecimal weight;
    private String originCountry;
    private String hsCode;
    private String images;
    private Integer status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
