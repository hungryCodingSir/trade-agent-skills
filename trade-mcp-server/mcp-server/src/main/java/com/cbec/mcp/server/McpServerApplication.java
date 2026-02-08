package com.cbec.mcp.server;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 跨境电商 MCP Server 启动入口。
 * <p>
 * 通过 SSE 协议对外暴露购物车、订单、物流、邮件四类工具，
 * 供上游 MCP Client（如 trade-agent-brain）按需调用。
 */
@SpringBootApplication
@MapperScan("com.cbec.mcp.server.mapper")
public class McpServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(McpServerApplication.class, args);
    }
}
