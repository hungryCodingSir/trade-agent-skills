package com.cbec.mcp.common.result;

import lombok.Data;
import java.io.Serializable;

/**
 * MCP 工具统一返回结构，LLM 通过解析 JSON 来理解操作结果。
 */
@Data
public class McpResult implements Serializable {

    private static final long serialVersionUID = 1L;

    private boolean success;
    private String message;
    private Object data;

    public static McpResult ok(Object data) {
        McpResult r = new McpResult();
        r.setSuccess(true);
        r.setMessage("操作成功");
        r.setData(data);
        return r;
    }

    public static McpResult ok(String msg, Object data) {
        McpResult r = new McpResult();
        r.setSuccess(true);
        r.setMessage(msg);
        r.setData(data);
        return r;
    }

    public static McpResult fail(String msg) {
        McpResult r = new McpResult();
        r.setSuccess(false);
        r.setMessage(msg);
        return r;
    }
}
