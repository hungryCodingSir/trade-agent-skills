package com.cbec.mcp.server.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cbec.mcp.common.entity.OrderInfo;
import com.cbec.mcp.server.dto.OrderDetailVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface OrderInfoMapper extends BaseMapper<OrderInfo> {

    /** 根据订单号查询订单详情（JOIN 买家/卖家 + 订单明细） */
    OrderDetailVO selectOrderDetail(@Param("orderNo") String orderNo);
}
