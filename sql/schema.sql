-- ============================================================
-- 跨境电商 MCP Server 数据库初始化脚本
-- 目标数据库: cross_border_agent (MySQL 8.0+)
-- ============================================================

CREATE DATABASE IF NOT EXISTS `cross_border_agent`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `cross_border_agent`;

-- cross_border_agent.chat_messages definition

CREATE TABLE `chat_messages` (
  `id` bigint NOT NULL COMMENT '主键ID',
  `msg_id` varchar(64) NOT NULL COMMENT '消息ID',
  `user_id` int NOT NULL COMMENT '用户ID',
  `session_id` varchar(64) NOT NULL COMMENT '所属会话ID',
  `role` varchar(20) NOT NULL COMMENT '角色 (human/ai)',
  `content` text NOT NULL COMMENT '消息内容',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='对话消息表';

-- cross_border_agent.chat_messages_summaries definition

CREATE TABLE `chat_messages_summaries` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `summary_id` varchar(64) NOT NULL COMMENT '摘要ID',
  `user_id` int NOT NULL COMMENT '用户ID',
  `session_id` varchar(64) NOT NULL COMMENT '所属会话ID',
  `mes_id_start` varchar(64) NOT NULL COMMENT '原始消息的起始ID',
  `mes_id_end` varchar(64) NOT NULL COMMENT '原始消息的结束ID',
  `content` text NOT NULL COMMENT '摘要消息内容',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7425448665549901826 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='聊天摘要表';
-- -----------------------------------------------------------
-- 用户基础信息表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sys_user` (
    `id`           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username`     VARCHAR(50)  NOT NULL                COMMENT '用户名',
    `password`     VARCHAR(255) NOT NULL                COMMENT '密码（加密存储）',
    `email`        VARCHAR(100) DEFAULT NULL            COMMENT '邮箱',
    `phone`        VARCHAR(20)  DEFAULT NULL            COMMENT '手机号',
    `user_type`    ENUM('BUYER','SELLER','ADMIN') NOT NULL COMMENT '用户类型',
    `company_name` VARCHAR(200) DEFAULT NULL            COMMENT '公司名称',
    `country`      VARCHAR(50)  DEFAULT NULL            COMMENT '所在国家',
    `timezone`     VARCHAR(50)  DEFAULT 'Asia/Shanghai' COMMENT '时区',
    `language`     VARCHAR(10)  DEFAULT 'zh-CN'         COMMENT '语言偏好',
    `avatar_url`   VARCHAR(500) DEFAULT NULL            COMMENT '头像URL',
    `status`       TINYINT      DEFAULT 1               COMMENT '状态: 0-禁用, 1-启用',
    `created_at`   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_user_type` (`user_type`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户基础信息表';

-- -----------------------------------------------------------
-- 商品分类表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `product_category` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '分类ID',
    `parent_id`  BIGINT       DEFAULT 0               COMMENT '父分类ID',
    `name_zh`    VARCHAR(100) NOT NULL                 COMMENT '中文名称',
    `name_en`    VARCHAR(100) DEFAULT NULL             COMMENT '英文名称',
    `hs_code`    VARCHAR(20)  DEFAULT NULL             COMMENT 'HS编码（海关编码）',
    `tax_rate`   DECIMAL(5,2) DEFAULT 0.00             COMMENT '默认税率（%）',
    `sort_order` INT          DEFAULT 0                COMMENT '排序权重',
    `created_at` DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_parent_id` (`parent_id`),
    KEY `idx_hs_code` (`hs_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品分类表';

-- -----------------------------------------------------------
-- 商品信息表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `product` (
    `id`                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '商品ID',
    `seller_id`          BIGINT       NOT NULL                COMMENT '卖家ID',
    `category_id`        BIGINT       DEFAULT NULL            COMMENT '分类ID',
    `sku`                VARCHAR(50)  NOT NULL                COMMENT 'SKU编码',
    `name_zh`            VARCHAR(200) NOT NULL                COMMENT '商品名称（中文）',
    `name_en`            VARCHAR(200) DEFAULT NULL            COMMENT '商品名称（英文）',
    `description`        TEXT                                 COMMENT '商品描述',
    `price`              DECIMAL(12,2) NOT NULL               COMMENT '单价（USD）',
    `currency`           VARCHAR(10)  DEFAULT 'USD'           COMMENT '货币类型',
    `stock_quantity`     INT          DEFAULT 0               COMMENT '库存数量',
    `min_order_quantity` INT          DEFAULT 1               COMMENT '最小起订量',
    `weight`             DECIMAL(10,3) DEFAULT NULL           COMMENT '重量（kg）',
    `origin_country`     VARCHAR(50)  DEFAULT NULL            COMMENT '原产国',
    `hs_code`            VARCHAR(20)  DEFAULT NULL            COMMENT 'HS编码',
    `images`             JSON         DEFAULT NULL            COMMENT '商品图片URL列表',
    `status`             TINYINT      DEFAULT 1               COMMENT '状态: 0-下架, 1-上架',
    `created_at`         DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`         DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_sku` (`sku`),
    KEY `idx_seller_id` (`seller_id`),
    KEY `idx_category_id` (`category_id`),
    KEY `idx_status` (`status`),
    FULLTEXT KEY `ft_product_name` (`name_zh`, `name_en`),
    CONSTRAINT `fk_product_seller`   FOREIGN KEY (`seller_id`)   REFERENCES `sys_user` (`id`),
    CONSTRAINT `fk_product_category` FOREIGN KEY (`category_id`) REFERENCES `product_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品信息表';

-- -----------------------------------------------------------
-- 购物车表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `shopping_cart` (
    `id`         BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id`    BIGINT   NOT NULL                COMMENT '用户ID',
    `product_id` BIGINT   NOT NULL                COMMENT '商品ID',
    `quantity`   INT      NOT NULL DEFAULT 1       COMMENT '数量',
    `selected`   TINYINT  DEFAULT 1                COMMENT '是否选中: 0-否, 1-是',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_product` (`user_id`, `product_id`),
    KEY `idx_user_id` (`user_id`),
    CONSTRAINT `fk_cart_user`    FOREIGN KEY (`user_id`)    REFERENCES `sys_user` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cart_product` FOREIGN KEY (`product_id`) REFERENCES `product` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='购物车表';

-- -----------------------------------------------------------
-- 订单主表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `order_info` (
    `id`               BIGINT        NOT NULL AUTO_INCREMENT COMMENT '订单ID',
    `order_no`         VARCHAR(50)   NOT NULL                COMMENT '订单编号',
    `buyer_id`         BIGINT        NOT NULL                COMMENT '买家ID',
    `seller_id`        BIGINT        NOT NULL                COMMENT '卖家ID',
    `total_amount`     DECIMAL(12,2) NOT NULL                COMMENT '订单总金额（USD）',
    `shipping_fee`     DECIMAL(10,2) DEFAULT 0.00            COMMENT '运费（USD）',
    `tax_amount`       DECIMAL(10,2) DEFAULT 0.00            COMMENT '关税金额（USD）',
    `currency`         VARCHAR(10)   DEFAULT 'USD'           COMMENT '货币类型',
    `order_status`     ENUM('PENDING_PAYMENT','PAID','PROCESSING','SHIPPED',
                            'IN_TRANSIT','CUSTOMS_CLEARANCE','DELIVERED',
                            'COMPLETED','CANCELLED','REFUNDED')
                       DEFAULT 'PENDING_PAYMENT'             COMMENT '订单状态',
    `payment_status`   ENUM('UNPAID','PAID','REFUNDED')
                       DEFAULT 'UNPAID'                      COMMENT '支付状态',
    `payment_method`   VARCHAR(50)   DEFAULT NULL             COMMENT '支付方式',
    `paid_at`          DATETIME      DEFAULT NULL             COMMENT '支付时间',
    `shipping_method`  ENUM('SEA','AIR','EXPRESS','RAIL')
                       DEFAULT NULL                           COMMENT '运输方式',
    `shipping_address` JSON          DEFAULT NULL             COMMENT '收货地址',
    `buyer_remark`     VARCHAR(500)  DEFAULT NULL             COMMENT '买家备注',
    `seller_remark`    VARCHAR(500)  DEFAULT NULL             COMMENT '卖家备注',
    `created_at`       DATETIME      DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`       DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_buyer_id` (`buyer_id`),
    KEY `idx_seller_id` (`seller_id`),
    KEY `idx_order_status` (`order_status`),
    KEY `idx_created_at` (`created_at`),
    CONSTRAINT `fk_order_buyer`  FOREIGN KEY (`buyer_id`)  REFERENCES `sys_user` (`id`),
    CONSTRAINT `fk_order_seller` FOREIGN KEY (`seller_id`) REFERENCES `sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单主表';

-- -----------------------------------------------------------
-- 订单明细表（下单时快照商品信息，避免商品变更影响历史订单）
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `order_item` (
    `id`           BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `order_id`     BIGINT        NOT NULL                COMMENT '订单ID',
    `product_id`   BIGINT        NOT NULL                COMMENT '商品ID',
    `product_name` VARCHAR(200)  NOT NULL                COMMENT '商品名称（快照）',
    `product_sku`  VARCHAR(50)   NOT NULL                COMMENT 'SKU（快照）',
    `unit_price`   DECIMAL(12,2) NOT NULL                COMMENT '单价（USD）',
    `quantity`     INT           NOT NULL                 COMMENT '数量',
    `subtotal`     DECIMAL(12,2) NOT NULL                COMMENT '小计（USD）',
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_order_id` (`order_id`),
    KEY `idx_product_id` (`product_id`),
    CONSTRAINT `fk_item_order`   FOREIGN KEY (`order_id`)   REFERENCES `order_info` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_item_product` FOREIGN KEY (`product_id`) REFERENCES `product` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单明细表';

-- -----------------------------------------------------------
-- 发货信息表（一个订单对应一条发货记录）
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `shipping_info` (
    `id`                  BIGINT       NOT NULL AUTO_INCREMENT COMMENT '发货ID',
    `order_id`            BIGINT       NOT NULL                COMMENT '订单ID',
    `tracking_no`         VARCHAR(100) DEFAULT NULL            COMMENT '物流单号',
    `carrier`             VARCHAR(100) DEFAULT NULL            COMMENT '承运商',
    `shipping_method`     ENUM('SEA','AIR','EXPRESS','RAIL')
                          DEFAULT NULL                         COMMENT '运输方式',
    `origin_port`         VARCHAR(100) DEFAULT NULL            COMMENT '起运港/始发地',
    `destination_port`    VARCHAR(100) DEFAULT NULL            COMMENT '目的港/目的地',
    `estimated_departure` DATE         DEFAULT NULL            COMMENT '预计发货日期',
    `actual_departure`    DATE         DEFAULT NULL            COMMENT '实际发货日期',
    `estimated_arrival`   DATE         DEFAULT NULL            COMMENT '预计到达日期',
    `actual_arrival`      DATE         DEFAULT NULL            COMMENT '实际到达日期',
    `customs_status`      ENUM('NOT_STARTED','DOCUMENTS_SUBMITTED','UNDER_REVIEW',
                                'CLEARED','HELD','REJECTED')
                          DEFAULT 'NOT_STARTED'                COMMENT '清关状态',
    `shipping_status`     ENUM('PENDING','PICKED_UP','IN_TRANSIT','ARRIVED_PORT',
                                'CUSTOMS_CLEARANCE','OUT_FOR_DELIVERY','DELIVERED','EXCEPTION')
                          DEFAULT 'PENDING'                    COMMENT '物流状态',
    `package_info`        JSON         DEFAULT NULL            COMMENT '包裹信息（件数、重量、体积等）',
    `remark`              VARCHAR(500) DEFAULT NULL            COMMENT '备注',
    `created_at`          DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`          DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_id` (`order_id`),
    KEY `idx_tracking_no` (`tracking_no`),
    KEY `idx_shipping_status` (`shipping_status`),
    CONSTRAINT `fk_shipping_order` FOREIGN KEY (`order_id`) REFERENCES `order_info` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='发货信息表';

-- -----------------------------------------------------------
-- 物流轨迹表（一条发货记录对应多条轨迹）
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `shipping_track` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `shipping_id` BIGINT       NOT NULL                COMMENT '发货ID',
    `track_time`  DATETIME     NOT NULL                COMMENT '轨迹时间',
    `location`    VARCHAR(200) DEFAULT NULL            COMMENT '位置',
    `status`      VARCHAR(100) DEFAULT NULL            COMMENT '状态描述',
    `description` VARCHAR(500) DEFAULT NULL            COMMENT '详细描述',
    `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_shipping_id` (`shipping_id`),
    KEY `idx_track_time` (`track_time`),
    CONSTRAINT `fk_track_shipping` FOREIGN KEY (`shipping_id`) REFERENCES `shipping_info` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物流轨迹表';

-- -----------------------------------------------------------
-- 邮件发送记录表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `email_log` (
    `id`               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id`          BIGINT       DEFAULT NULL            COMMENT '操作用户ID',
    `to_email`         VARCHAR(200) NOT NULL                COMMENT '收件人邮箱',
    `cc_email`         VARCHAR(500) DEFAULT NULL            COMMENT '抄送邮箱',
    `subject`          VARCHAR(500) NOT NULL                COMMENT '邮件主题',
    `content`          TEXT         NOT NULL                COMMENT '邮件正文',
    `email_type`       ENUM('SHIPPING_DELAY','LATE_SHIPMENT','ORDER_CONFIRM',
                            'PAYMENT_REMIND','CUSTOMS_ALERT','GENERAL')
                       NOT NULL                             COMMENT '邮件类型',
    `related_order_id` BIGINT       DEFAULT NULL            COMMENT '关联订单ID',
    `status`           ENUM('PENDING','SENT','FAILED')
                       DEFAULT 'PENDING'                    COMMENT '发送状态',
    `sent_at`          DATETIME     DEFAULT NULL            COMMENT '发送时间',
    `error_msg`        VARCHAR(500) DEFAULT NULL            COMMENT '错误信息',
    `retry_count`      INT          DEFAULT 0               COMMENT '重试次数',
    `created_at`       DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`),
    KEY `idx_email_type` (`email_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邮件发送记录表';
