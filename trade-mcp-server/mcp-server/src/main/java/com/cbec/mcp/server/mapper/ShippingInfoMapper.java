package com.cbec.mcp.server.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cbec.mcp.common.entity.ShippingInfo;
import com.cbec.mcp.server.dto.ShippingDetailVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface ShippingInfoMapper extends BaseMapper<ShippingInfo> {

    /** 根据订单号查询物流详情（JOIN 订单 + 物流轨迹） */
    ShippingDetailVO selectShippingDetail(@Param("orderNo") String orderNo);
}
