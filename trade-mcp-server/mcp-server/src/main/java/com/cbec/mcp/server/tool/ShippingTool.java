package com.cbec.mcp.server.tool;

import com.cbec.mcp.common.result.McpResult;
import com.cbec.mcp.common.util.JsonUtil;
import com.cbec.mcp.server.dto.ShippingDetailVO;
import com.cbec.mcp.server.service.ShippingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * 物流 MCP 工具，向 LLM 暴露物流轨迹查询能力。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ShippingTool {

    private final ShippingService shippingService;

    @Tool(name = "queryShippingInfo",
          description = "根据订单编号查询物流信息，包括运单号、承运商、运输方式、起运港/目的港、预计/实际出发到达时间、"
                      + "海关清关状态、物流状态以及完整物流轨迹。适用于用户查询包裹位置、预计到达时间、清关进度等场景。")
    public String queryShippingInfo(
            @ToolParam(description = "订单编号，如 ORD20240101001，必填，用于关联查询物流信息") String orderNo) {
        log.info("queryShippingInfo called, orderNo={}", orderNo);
        try {
            ShippingDetailVO detail = shippingService.queryByOrderNo(orderNo);
            if (detail == null) {
                return JsonUtil.toJson(McpResult.fail("未找到该订单的物流信息: " + orderNo));
            }
            return JsonUtil.toJson(McpResult.ok("物流查询成功", detail));
        } catch (IllegalArgumentException e) {
            return JsonUtil.toJson(McpResult.fail(e.getMessage()));
        } catch (Exception e) {
            log.error("查询物流异常", e);
            return JsonUtil.toJson(McpResult.fail("查询物流失败: " + e.getMessage()));
        }
    }
}
