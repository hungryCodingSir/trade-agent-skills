"""
Token & Cache 监控工具

用于验证 QwenPromptCachingMiddleware 是否生效。

千问返回的 usage 结构：
{
    "usage": {
        "prompt_tokens": 3019,
        "completion_tokens": 104,
        "total_tokens": 3123,
        "prompt_tokens_details": {
            "cached_tokens": 2048                     # 隐式缓存命中
            // 或
            "cache_creation_input_tokens": 1500,      # 显式缓存创建
            "cached_tokens": 1500                     # 显式缓存命中
        }
    }
}
"""

from loguru import logger


def log_qwen_token_usage(result: dict) -> None:
    """从 Agent 返回结果中提取并记录千问的 token 使用情况。

    Args:
        result: agent.ainvoke() 的返回值
    """
    try:
        messages = result.get("messages", [])

        # 从最后一条 AI 消息的 response_metadata 中提取 usage
        for msg in reversed(messages):
            metadata = getattr(msg, "response_metadata", None)
            if not metadata:
                continue

            # LangChain ChatOpenAI 可能用 "token_usage" 或 "usage"
            usage = metadata.get("token_usage") or metadata.get("usage", {})
            if not usage:
                continue

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            # 缓存详情
            details = usage.get("prompt_tokens_details", {}) or {}
            cached_tokens = details.get("cached_tokens", 0)
            cache_creation = details.get("cache_creation_input_tokens", 0)

            # 计算实际费用比率
            if prompt_tokens > 0:
                uncached = prompt_tokens - cached_tokens - cache_creation

                # 费用 = 未缓存部分×100% + 创建缓存×125% + 命中缓存×10%
                effective_cost = uncached + cache_creation * 1.25 + cached_tokens * 0.1
                cost_ratio = effective_cost / prompt_tokens * 100

                cache_hit_ratio = cached_tokens / prompt_tokens * 100

                logger.info(
                    f"📊 Token 统计 | "
                    f"input: {prompt_tokens} | "
                    f"output: {completion_tokens} | "
                    f"cached_hit: {cached_tokens} ({cache_hit_ratio:.0f}%) | "
                    f"cache_creation: {cache_creation} | "
                    f"费用比: {cost_ratio:.0f}% (vs 无缓存100%)"
                )

                if cached_tokens > 0:
                    logger.info(f"✅ 缓存命中！节省约 {100 - cost_ratio:.0f}% 输入费用")
                elif cache_creation > 0:
                    logger.info(f"🔨 缓存已创建（{cache_creation} tokens），下次请求将命中")
                else:
                    logger.warning(
                        "⚠️ 未命中缓存。可能原因：\n"
                        "  1. 模型不支持显式缓存（检查模型名称）\n"
                        "  2. system prompt < 1024 tokens（显式缓存最低要求）\n"
                        "  3. 首次请求（需要先创建缓存）\n"
                        "  4. 缓存已过期（5分钟）"
                    )
            else:
                logger.info(f"📊 Token 统计 | total: {total_tokens}")

            break  # 只处理最后一条

    except Exception as e:
        logger.debug(f"Token 监控异常（不影响主流程）: {e}")