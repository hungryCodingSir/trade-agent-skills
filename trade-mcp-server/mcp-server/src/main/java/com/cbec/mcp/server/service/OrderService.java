package com.cbec.mcp.server.service;

import com.cbec.mcp.server.dto.OrderDetailVO;
import com.cbec.mcp.server.mapper.OrderInfoMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 订单领域服务，封装订单查询的核心逻辑。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderInfoMapper orderMapper;

    /**
     * 根据订单编号查询订单详情（含买卖家信息与商品明细行）。
     *
     * @param orderNo 订单编号，如 ORD202501001
     * @return 订单详情，未找到时返回 null
     */
    public OrderDetailVO queryByOrderNo(String orderNo) {
        if (orderNo == null || orderNo.isBlank()) {
            throw new IllegalArgumentException("订单编号不能为空");
        }
        return orderMapper.selectOrderDetail(orderNo.trim());
    }
}
