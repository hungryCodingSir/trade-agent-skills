package com.cbec.mcp.server.tool;

import com.cbec.mcp.common.result.McpResult;
import com.cbec.mcp.common.util.JsonUtil;
import com.cbec.mcp.server.dto.CartItemVO;
import com.cbec.mcp.server.service.CartService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 购物车 MCP 工具，向 LLM 暴露购物车查询能力。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class CartTool {

    private final CartService cartService;

    @Tool(name = "queryShoppingCart",
          description = "查询指定用户的购物车信息，返回购物车中所有商品的详细信息，包括商品名称、SKU、单价、数量、"
                      + "小计金额、库存、起订量、原产国等。适用于用户询问购物车内容、想要下单前确认商品等场景。")
    public String queryShoppingCart(
            @ToolParam(description = "用户ID，必填，用于查询该用户的购物车") Long userId) {
        log.info("queryShoppingCart called, userId={}", userId);
        try {
            List<CartItemVO> items = cartService.queryCart(userId);
            if (items.isEmpty()) {
                return JsonUtil.toJson(McpResult.ok("购物车为空", List.of()));
            }
            return JsonUtil.toJson(McpResult.ok("查询成功，共" + items.size() + "件商品", items));
        } catch (IllegalArgumentException e) {
            return JsonUtil.toJson(McpResult.fail(e.getMessage()));
        } catch (Exception e) {
            log.error("查询购物车异常", e);
            return JsonUtil.toJson(McpResult.fail("查询购物车失败: " + e.getMessage()));
        }
    }
}
