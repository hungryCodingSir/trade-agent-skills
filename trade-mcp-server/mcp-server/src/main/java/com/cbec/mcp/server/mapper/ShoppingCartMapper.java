package com.cbec.mcp.server.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cbec.mcp.common.entity.ShoppingCart;
import com.cbec.mcp.server.dto.CartItemVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ShoppingCartMapper extends BaseMapper<ShoppingCart> {

    /** 查询用户购物车明细（JOIN 商品表获取完整信息） */
    List<CartItemVO> selectCartWithProduct(@Param("userId") Long userId);
}
