package com.cbec.mcp.server.tool;

import com.cbec.mcp.common.result.McpResult;
import com.cbec.mcp.common.util.JsonUtil;
import com.cbec.mcp.server.dto.OrderDetailVO;
import com.cbec.mcp.server.service.OrderService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * 订单 MCP 工具，向 LLM 暴露订单详情查询能力。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OrderTool {

    private final OrderService orderService;

    @Tool(name = "queryOrderStatus",
          description = "根据订单编号查询订单详情，包括订单状态、支付状态、买家/卖家信息、商品明细、金额、运费、"
                      + "税费等完整信息。适用于用户查询订单进度、确认订单内容、核对金额等场景。")
    public String queryOrderStatus(
            @ToolParam(description = "订单编号，如 ORD20240101001，必填") String orderNo) {
        log.info("queryOrderStatus called, orderNo={}", orderNo);
        try {
            OrderDetailVO detail = orderService.queryByOrderNo(orderNo);
            if (detail == null) {
                return JsonUtil.toJson(McpResult.fail("未找到订单: " + orderNo));
            }
            return JsonUtil.toJson(McpResult.ok("订单查询成功", detail));
        } catch (IllegalArgumentException e) {
            return JsonUtil.toJson(McpResult.fail(e.getMessage()));
        } catch (Exception e) {
            log.error("查询订单异常", e);
            return JsonUtil.toJson(McpResult.fail("查询订单失败: " + e.getMessage()));
        }
    }
}
