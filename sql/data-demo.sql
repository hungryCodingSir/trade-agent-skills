-- ============================================================
-- 演示数据 — 可选执行，用于本地开发和功能验证
-- 前置条件: 已执行 schema.sql
-- ============================================================

USE `cross_border_agent`;

-- 用户
INSERT INTO `sys_user` (`id`, `username`, `password`, `email`, `phone`, `user_type`, `company_name`, `country`) VALUES
(1, 'buyer_test',  '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iKT/7dLqL2Wc0t5.5t5a5E5E5E5E', 'buyer@test.com',  '13800138000', 'BUYER',  'Test Buyer Co.',   'China'),
(2, 'seller_test', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iKT/7dLqL2Wc0t5.5t5a5E5E5E5E', 'seller@test.com', '13900139000', 'SELLER', 'Test Seller Inc.', 'USA'),
(3, 'admin_test',  '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iKT/7dLqL2Wc0t5.5t5a5E5E5E5E', 'admin@test.com',  '13700137000', 'ADMIN',  'Platform Admin',   'China');

-- 商品分类
INSERT INTO `product_category` (`id`, `parent_id`, `name_zh`, `name_en`, `hs_code`, `tax_rate`) VALUES
(1, 0, '电子产品',   'Electronics',           '8471', 0.00),
(2, 0, '服装鞋帽',   'Clothing & Footwear',   '6204', 6.50),
(3, 0, '家居用品',   'Home & Garden',         '9403', 0.00),
(4, 0, '机械设备',   'Machinery',             '8428', 0.00);

-- 商品
INSERT INTO `product` (`id`, `seller_id`, `category_id`, `sku`, `name_zh`, `name_en`, `description`, `price`, `currency`, `stock_quantity`, `min_order_quantity`, `weight`, `origin_country`, `hs_code`) VALUES
(1, 2, 1, 'ELEC-001', '智能手机', 'Smart Phone',      '高性能智能手机，5G支持',    299.99, 'USD', 1000, 10,  0.200, 'China', '8517.12'),
(2, 2, 1, 'ELEC-002', '无线耳机', 'Wireless Earbuds',  '蓝牙5.0无线耳机',          49.99,  'USD', 5000, 50,  0.050, 'China', '8518.30'),
(3, 2, 2, 'CLTH-001', '运动鞋',   'Sports Shoes',      '轻便透气运动鞋',           39.99,  'USD', 3000, 100, 0.400, 'China', '6404.11');

-- 购物车
INSERT INTO `shopping_cart` (`id`, `user_id`, `product_id`, `quantity`, `selected`) VALUES
(1, 1, 2, 20, 1),
(2, 1, 3, 50, 1);

-- 订单
INSERT INTO `order_info` (`id`, `order_no`, `buyer_id`, `seller_id`, `total_amount`, `shipping_fee`, `tax_amount`, `currency`, `order_status`, `payment_status`, `shipping_method`, `shipping_address`) VALUES
(1, 'ORD202501001', 1, 2, 3049.90, 150.00, 0.00, 'USD', 'SHIPPED',         'PAID',   'SEA', '{"name":"John Doe","address":"123 Main St","city":"Los Angeles","state":"California","zip":"90001","country":"USA","phone":"+1234567890"}'),
(2, 'ORD202501002', 1, 2, 2499.50, 200.00, 0.00, 'USD', 'PENDING_PAYMENT', 'UNPAID', 'AIR', '{"name":"John Doe","address":"123 Main St","city":"Los Angeles","state":"California","zip":"90001","country":"USA","phone":"+1234567890"}');

-- 订单明细
INSERT INTO `order_item` (`id`, `order_id`, `product_id`, `product_name`, `product_sku`, `unit_price`, `quantity`, `subtotal`) VALUES
(1, 1, 1, '智能手机', 'ELEC-001', 299.99, 10, 2999.90),
(2, 1, 2, '无线耳机', 'ELEC-002',  49.99,  1,   49.99),
(3, 2, 2, '无线耳机', 'ELEC-002',  49.99, 50, 2499.50);

-- 发货信息
INSERT INTO `shipping_info` (`id`, `order_id`, `tracking_no`, `carrier`, `shipping_method`, `origin_port`, `destination_port`, `estimated_departure`, `actual_departure`, `estimated_arrival`, `customs_status`, `shipping_status`) VALUES
(1, 1, 'MAEU1234567890', 'MAERSK', 'SEA', 'Shanghai Port', 'Los Angeles Port', '2025-01-15', '2025-01-16', '2025-02-15', 'NOT_STARTED', 'IN_TRANSIT');

-- 物流轨迹
INSERT INTO `shipping_track` (`id`, `shipping_id`, `track_time`, `location`, `status`, `description`) VALUES
(1, 1, '2025-01-16 10:00:00', 'Shanghai Port',  'DEPARTED',   '货物已从上海港发出'),
(2, 1, '2025-01-20 15:30:00', 'Pacific Ocean',  'IN_TRANSIT', '货物在太平洋航行中');
