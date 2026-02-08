"""
响应质量守卫中间件

通过 wrap_model_call 拦截模型的每次输出，进行快速质量评估。
不合格的响应会注入改进提示后自动重试（最多 N 次）。

评估维度: 空响应 / 套话检测 / 隐私泄露 / 语言一致性 / 响应长度
"""
import re
from typing import Any, Callable, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger


class ResponseQualityGuardMiddleware(AgentMiddleware):
    """拦截低质量响应并自动重试，在线质量兜底。"""

    # 无意义套话（检测到扣分）
    HALLUCINATION_PHRASES = [
        "作为一个AI", "作为AI模型", "作为人工智能",
        "我无法确定", "我没有能力",
        "As an AI", "I cannot determine",
    ]

    # 隐私信息（检测到强制重试）
    PRIVACY_PATTERNS = [
        re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),  # 银行卡号
        re.compile(r'\b1[3-9]\d{9}\b'),                                # 手机号
    ]

    def __init__(
        self,
        max_retries: int = 2,
        min_score: float = 0.6,
        enable_llm_judge: bool = False,
        judge_model=None,
    ):
        super().__init__()
        self.max_retries = max_retries
        self.min_score = min_score
        self.enable_llm_judge = enable_llm_judge
        self.judge_model = judge_model

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """拦截模型调用，评估质量，不合格则重试。"""
        best_response = None
        best_score = 0.0

        for attempt in range(1 + self.max_retries):
            if attempt == 0:
                response = handler(request)
            else:
                enhanced_request = self._enhance_request(request, best_response, best_score, attempt)
                response = handler(enhanced_request)

            ai_content = self._extract_content(response)
            if ai_content is None:
                # 工具调用等非文本响应，直接放行
                return response

            score, issues = self._evaluate_response(ai_content)

            logger.info(
                f"[QualityGuard] attempt={attempt + 1}/{1 + self.max_retries}, "
                f"score={score:.2f}, issues={issues or 'none'}"
            )

            if score > best_score:
                best_score = score
                best_response = response

            if score >= self.min_score:
                if attempt > 0:
                    logger.info(f"[QualityGuard] 第 {attempt + 1} 次尝试通过")
                return response

            if "privacy_leak" in issues:
                logger.warning("[QualityGuard] 检测到隐私泄露，强制重试")
                continue

            logger.info(f"[QualityGuard] 质量不达标 ({score:.2f} < {self.min_score})，重试")

        logger.warning(f"[QualityGuard] 重试用尽，返回最佳响应 (score={best_score:.2f})")
        return best_response

    def _evaluate_response(self, content: str) -> tuple[float, list[str]]:
        """快速规则评估（无 LLM 调用，< 1ms）"""
        score = 1.0
        issues = []

        if not content or len(content.strip()) < 10:
            return 0.0, ["empty_response"]

        # 套话检测
        hallucination_count = sum(
            1 for phrase in self.HALLUCINATION_PHRASES if phrase in content
        )
        if hallucination_count > 0:
            score -= min(hallucination_count * 0.15, 0.4)
            issues.append(f"hallucination_phrases({hallucination_count})")

        # 隐私泄露
        for pattern in self.PRIVACY_PATTERNS:
            if pattern.search(content):
                score -= 0.5
                issues.append("privacy_leak")
                break

        # 语言一致性（中文场景）
        chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
        if len(content) > 50 and chinese_chars / len(content) < 0.15:
            score -= 0.2
            issues.append("language_mismatch")

        # 过短响应
        if 10 < len(content.strip()) < 30:
            score -= 0.1
            issues.append("too_short")

        return max(0.0, score), issues

    def _enhance_request(
        self,
        original_request: ModelRequest,
        prev_response: ModelResponse,
        prev_score: float,
        attempt: int,
    ) -> ModelRequest:
        """重试时追加质量改进提示"""
        quality_hint = (
            f"\n\n[质量改进提示 — 第 {attempt + 1} 次尝试]\n"
            f"上次回答评分 {prev_score:.1f}/1.0，未达标。请注意：\n"
            f"1. 直接回答问题，避免套话\n"
            f"2. 使用中文，保持专业简洁\n"
            f"3. 不要暴露手机号、银行卡号等隐私信息\n"
            f"4. 确保回答完整"
        )

        enhanced_prompt = (original_request.system_prompt or "") + quality_hint
        return original_request.override(system_prompt=enhanced_prompt)

    @staticmethod
    def _extract_content(response: ModelResponse) -> Optional[str]:
        """提取 AI 文本内容，工具调用返回 None（跳过评估）"""
        if not response or not response.result:
            return None

        ai_msg = response.result[0]
        if isinstance(ai_msg, AIMessage):
            if ai_msg.tool_calls and not ai_msg.content:
                return None
            return ai_msg.content if isinstance(ai_msg.content, str) else None

        return None
