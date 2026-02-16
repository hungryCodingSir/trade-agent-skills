"""
千问（Qwen）Prompt Caching 中间件

对标 deepagents 框架内置的 AnthropicPromptCachingMiddleware，
为千问模型实现显式缓存标记，使 skills 渐进式披露真正发挥 token 节省效果。

原理：
  deepagents 的 SkillsMiddleware 将 skill metadata 注入 system prompt，
  这部分内容在同一会话的多轮请求中是稳定的。
  本中间件在 system message 上标记 cache_control，
  让千问 API 将这段稳定前缀缓存起来——命中后仅按 10% 计费。

用法：
  在 create_deep_agent 的 middleware 参数中添加本中间件，
  替代框架默认的 AnthropicPromptCachingMiddleware（对千问无效）。

  from app.middleware.qwen_prompt_caching import QwenPromptCachingMiddleware

  agent = create_deep_agent(
      model=main_model,
      middleware=[
          ...,
          QwenPromptCachingMiddleware(),
      ],
      skills=[settings.skills_dir],  # ← 保留 skills 参数
      ...
  )

千问显式缓存要求：
  - 支持模型：qwen3-max, qwen-plus, qwen-flash, qwen3-coder-plus/flash 等
  - 最低缓存 token 数：1024
  - 缓存有效期：5分钟（命中后重置）
  - 创建缓存费用：输入 token 单价 × 125%
  - 命中缓存费用：输入 token 单价 × 10%
  - cache_control 格式：{"type": "ephemeral"}（与 Anthropic 一致）
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_core.messages import SystemMessage

try:
    from langchain.agents.middleware.types import (
        AgentMiddleware,
        ModelCallResult,
        ModelRequest,
        ModelResponse,
    )
except ImportError as e:
    msg = (
        "QwenPromptCachingMiddleware requires 'langchain' to be installed. "
        "Install it with: pip install langchain"
    )
    raise ImportError(msg) from e

logger = logging.getLogger(__name__)

# 千问显式缓存支持的模型列表
QWEN_CACHE_SUPPORTED_MODELS = {
    "qwen3-max",
    "qwen-max",
    "qwen-plus",
    "qwen-flash",
    "qwen-turbo",
    "qwen3-coder-plus",
    "qwen3-coder-flash",
    "qwen3-vl-plus",
    "qwen3-vl-flash",
    "qwen-vl-max",
    "qwen-vl-plus",
}

# 千问显式缓存最低 token 要求
MIN_CACHE_TOKENS = 1024


class QwenPromptCachingMiddleware(AgentMiddleware):
    """千问 Prompt Caching 中间件。

    在每次模型调用前，将 system message 转换为 content blocks 格式，
    并在末尾标记 cache_control，让千问 API 缓存 system prompt 前缀。

    这样 skills metadata、角色设定等稳定内容只需计算一次，
    后续请求命中缓存后按 10% 费率计费。

    与 deepagents 的 SkillsMiddleware 配合使用效果最佳：
    - SkillsMiddleware: 只注入 frontmatter，全文按需读取 → 减少 token 数量
    - QwenPromptCachingMiddleware: 标记缓存 → 减少 token 费用

    Args:
        cache_system_prompt: 是否缓存 system prompt。默认 True。
        cache_last_user_message: 是否在最后一条 user message 上也标记缓存。
            适用于多轮对话场景，可以让历史消息也被缓存。默认 True。
        min_messages_to_cache: 至少有多少条消息时才启用缓存。默认 0。
        model_allowlist: 允许缓存的模型名称集合。
            默认为 QWEN_CACHE_SUPPORTED_MODELS。
            传 None 则对所有模型生效（适用于未来新模型）。

    Example:
        ```python
        from app.middleware.qwen_prompt_caching import QwenPromptCachingMiddleware

        middleware = QwenPromptCachingMiddleware(
            cache_system_prompt=True,
            cache_last_user_message=True,
        )
        ```
    """

    def __init__(
        self,
        *,
        cache_system_prompt: bool = True,
        cache_last_user_message: bool = True,
        min_messages_to_cache: int = 0,
        model_allowlist: set[str] | None = QWEN_CACHE_SUPPORTED_MODELS,
    ) -> None:
        self.cache_system_prompt = cache_system_prompt
        self.cache_last_user_message = cache_last_user_message
        self.min_messages_to_cache = min_messages_to_cache
        self.model_allowlist = model_allowlist

    def _should_apply_caching(self, request: ModelRequest) -> bool:
        """判断是否应该对本次请求应用缓存标记。"""
        # 1. 检查消息数量门槛
        messages_count = (
            len(request.messages) + 1
            if request.system_message
            else len(request.messages)
        )
        if messages_count < self.min_messages_to_cache:
            return False

        # 2. 检查模型是否在允许列表中
        if self.model_allowlist is not None:
            model_name = self._get_model_name(request.model)
            if model_name and model_name not in self.model_allowlist:
                logger.debug(
                    "QwenPromptCachingMiddleware: model '%s' not in allowlist, skipping",
                    model_name,
                )
                return False

        return True

    @staticmethod
    def _get_model_name(model) -> str | None:
        """从 LangChain 模型对象中提取模型名称。"""
        # ChatOpenAI 的 model_name 属性
        for attr in ("model_name", "model"):
            val = getattr(model, attr, None)
            if isinstance(val, str):
                return val
        return None

    def _add_cache_control_to_system_message(
        self, system_message: SystemMessage | str | None,
    ) -> SystemMessage | str | None:
        """在 system message 上添加 cache_control 标记。

        千问的显式缓存要求 content 使用 content blocks 格式：
        [{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]

        LangChain 的 ChatOpenAI 在发送请求时会保留 content blocks 格式。
        """
        if system_message is None or not self.cache_system_prompt:
            return system_message

        if isinstance(system_message, str):
            # 字符串格式 → 转为 SystemMessage + content blocks
            return SystemMessage(
                content=[
                    {
                        "type": "text",
                        "text": system_message,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            )

        if isinstance(system_message, SystemMessage):
            content = system_message.content

            if isinstance(content, str):
                # SystemMessage(content="string") → 转为 content blocks
                return SystemMessage(
                    content=[
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                )

            if isinstance(content, list):
                # 已经是 content blocks 格式
                # 在最后一个 text block 上添加 cache_control
                new_content = []
                last_text_idx = -1
                for i, block in enumerate(content):
                    if isinstance(block, dict) and block.get("type") == "text":
                        last_text_idx = i

                for i, block in enumerate(content):
                    if i == last_text_idx and isinstance(block, dict):
                        new_content.append({
                            **block,
                            "cache_control": {"type": "ephemeral"},
                        })
                    else:
                        new_content.append(block)

                return SystemMessage(content=new_content)

        return system_message

    def _add_cache_control_to_last_user_message(
        self, messages: list,
    ) -> list:
        """在最后一条 user message 上添加 cache_control 标记。

        这样对话历史也可以被缓存，多轮对话中效果显著。
        """
        if not self.cache_last_user_message or not messages:
            return messages

        # 从后往前找到最后一条 user/human message
        new_messages = list(messages)
        for i in range(len(new_messages) - 1, -1, -1):
            msg = new_messages[i]
            msg_type = getattr(msg, "type", None)
            if msg_type == "human":
                content = msg.content
                if isinstance(content, str):
                    # 转为 content blocks 格式
                    from langchain_core.messages import HumanMessage
                    new_messages[i] = HumanMessage(
                        content=[
                            {
                                "type": "text",
                                "text": content,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                        id=getattr(msg, "id", None),
                    )
                elif isinstance(content, list):
                    # 在最后一个 text block 上加 cache_control
                    new_content = list(content)
                    for j in range(len(new_content) - 1, -1, -1):
                        if isinstance(new_content[j], dict) and new_content[j].get("type") == "text":
                            new_content[j] = {
                                **new_content[j],
                                "cache_control": {"type": "ephemeral"},
                            }
                            break
                    from langchain_core.messages import HumanMessage
                    new_messages[i] = HumanMessage(
                        content=new_content,
                        id=getattr(msg, "id", None),
                    )
                break

        return new_messages

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """修改请求，添加缓存标记。"""
        # 1. 标记 system message
        new_system = self._add_cache_control_to_system_message(request.system_message)

        # 2. 标记最后一条 user message
        new_messages = self._add_cache_control_to_last_user_message(request.messages)

        return request.override(
            system_message=new_system,
            messages=new_messages,
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        """同步版本：在模型调用前注入缓存标记。"""
        if not self._should_apply_caching(request):
            return handler(request)

        modified = self._modify_request(request)
        return handler(modified)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """异步版本：在模型调用前注入缓存标记。"""
        if not self._should_apply_caching(request):
            return await handler(request)

        modified = self._modify_request(request)
        return await handler(modified)


__all__ = ["QwenPromptCachingMiddleware"]