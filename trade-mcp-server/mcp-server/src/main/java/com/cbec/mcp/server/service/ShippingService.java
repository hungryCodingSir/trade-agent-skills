package com.cbec.mcp.server.service;

import com.cbec.mcp.server.dto.ShippingDetailVO;
import com.cbec.mcp.server.mapper.ShippingInfoMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 物流领域服务，通过订单号关联查询物流概况及完整轨迹。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ShippingService {

    private final ShippingInfoMapper shippingMapper;

    /**
     * 根据订单编号查询物流详情（含轨迹列表）。
     *
     * @param orderNo 订单编号
     * @return 物流详情，未发货或未找到时返回 null
     */
    public ShippingDetailVO queryByOrderNo(String orderNo) {
        if (orderNo == null || orderNo.isBlank()) {
            throw new IllegalArgumentException("订单编号不能为空");
        }
        return shippingMapper.selectShippingDetail(orderNo.trim());
    }
}
