package com.cbec.mcp.server.config;

import com.cbec.mcp.server.tool.CartTool;
import com.cbec.mcp.server.tool.EmailTool;
import com.cbec.mcp.server.tool.OrderTool;
import com.cbec.mcp.server.tool.ShippingTool;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 将 tool 包中所有 @Tool 方法统一注册到 MCP Server，
 * 使其可通过 SSE 端点被 MCP Client 发现和调用。
 */
@Configuration
public class McpConfig {

    @Bean
    public ToolCallbackProvider toolCallbackProvider(CartTool cartTool,
                                                     OrderTool orderTool,
                                                     ShippingTool shippingTool,
                                                     EmailTool emailTool) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(cartTool, orderTool, shippingTool, emailTool)
                .build();
    }
}
