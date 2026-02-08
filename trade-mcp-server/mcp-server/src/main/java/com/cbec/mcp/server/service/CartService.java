package com.cbec.mcp.server.service;

import com.cbec.mcp.server.dto.CartItemVO;
import com.cbec.mcp.server.mapper.ShoppingCartMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;

/**
 * 购物车领域服务，负责查询购物车中的商品明细（关联商品表获取完整信息）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CartService {

    private final ShoppingCartMapper cartMapper;

    /**
     * 查询指定用户的购物车商品列表。
     *
     * @param userId 用户ID
     * @return 购物车商品明细列表，购物车为空时返回空集合
     */
    public List<CartItemVO> queryCart(Long userId) {
        if (userId == null || userId <= 0) {
            throw new IllegalArgumentException("用户ID无效");
        }
        List<CartItemVO> items = cartMapper.selectCartWithProduct(userId);
        return items != null ? items : Collections.emptyList();
    }
}
