"""
评估运行器

加载数据集 → 运行 Agent → 执行评估 → 输出报告

用法:
    python -m app.evaluation.runner
    python -m app.evaluation.runner --tag order
    python -m app.evaluation.runner --llm-judge
"""
import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.evaluation.datasets import ALL_EVAL_CASES, EvalCase, get_cases_by_tag, get_dataset_summary
from app.evaluation.evaluators import (
    EvalResult, EvalScore,
    LLMJudgeEvaluator, ResponseQualityEvaluator,
    SafetyEvaluator, TrajectoryEvaluator,
)


@dataclass
class EvalReport:
    """评估报告"""
    timestamp: str = ""
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    results: List[EvalResult] = field(default_factory=list)
    score_by_dimension: Dict[str, float] = field(default_factory=dict)
    score_by_tag: Dict[str, float] = field(default_factory=dict)
    score_by_difficulty: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "summary": {
                "total_cases": self.total_cases,
                "passed_cases": self.passed_cases,
                "failed_cases": self.failed_cases,
                "pass_rate": f"{self.pass_rate:.1%}",
                "avg_score": f"{self.avg_score:.2f}",
                "avg_latency_ms": f"{self.avg_latency_ms:.0f}",
            },
            "score_by_dimension": {k: f"{v:.2f}" for k, v in self.score_by_dimension.items()},
            "score_by_tag": {k: f"{v:.2f}" for k, v in self.score_by_tag.items()},
            "score_by_difficulty": {k: f"{v:.2f}" for k, v in self.score_by_difficulty.items()},
            "details": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "overall_score": f"{r.overall_score:.2f}",
                    "latency_ms": f"{r.latency_ms:.0f}",
                    "scores": [
                        {"name": s.name, "score": f"{s.score:.2f}", "passed": s.passed, "reasoning": s.reasoning}
                        for s in r.scores
                    ],
                    "error": r.error,
                }
                for r in self.results
            ],
        }

    def print_summary(self):
        print("\n" + "=" * 60)
        print(f"  评估报告 — {self.timestamp}")
        print("=" * 60)

        print(f"\n  总览")
        print(f"     用例: {self.total_cases}  通过: {self.passed_cases}  失败: {self.failed_cases}")
        print(f"     通过率: {self.pass_rate:.1%}  平均分: {self.avg_score:.2f}  延迟: {self.avg_latency_ms:.0f}ms")

        if self.score_by_dimension:
            print(f"\n  维度得分")
            for dim, score in sorted(self.score_by_dimension.items()):
                bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                print(f"     {dim:<25s} {bar} {score:.2f}")

        if self.score_by_tag:
            print(f"\n  标签得分")
            for tag, score in sorted(self.score_by_tag.items(), key=lambda x: -x[1]):
                bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                print(f"     {tag:<20s} {bar} {score:.2f}")

        failed = [r for r in self.results if not r.passed]
        if failed:
            print(f"\n  失败用例")
            for r in failed:
                print(f"\n     [{r.case_id}]")
                for s in r.scores:
                    if not s.passed:
                        print(f"       ✗ {s.name}: {s.reasoning}")

        print("\n" + "=" * 60 + "\n")


class MockAgentRunner:
    """模拟 Agent 执行，用于离线评估和 CI/CD 测试"""

    MOCK_TOOL_RESPONSES = {
        "query_order_status": json.dumps({
            "order_no": "ORD20240115001", "status": "SHIPPED",
            "payment_status": "PAID", "total_amount": 15800.00, "currency": "USD",
            "items": [{"name": "LED Bulb 12W", "qty": 2000, "unit_price": 7.9}],
        }, ensure_ascii=False),
        "query_shipping_info": json.dumps({
            "order_no": "ORD20240115001", "carrier": "Maersk",
            "tracking_no": "MAEU1234567", "status": "IN_TRANSIT",
            "current_location": "上海港", "eta": "2024-02-01",
            "checkpoints": [
                {"time": "2024-01-15", "location": "深圳仓库", "status": "已发货"},
                {"time": "2024-01-18", "location": "上海港", "status": "已到港"},
            ],
        }, ensure_ascii=False),
        "query_shopping_cart": json.dumps({
            "items": [
                {"name": "USB-C Cable 1m", "qty": 500, "unit_price": 2.5, "stock": 10000},
                {"name": "LED Strip 5m", "qty": 200, "unit_price": 8.0, "stock": 50},
            ],
            "total": 2850.00,
        }, ensure_ascii=False),
        "send_email_notification": json.dumps({
            "status": "sent", "message_id": "MSG20240120001",
        }, ensure_ascii=False),
    }

    def run(self, case: EvalCase) -> Dict[str, Any]:
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        messages = [HumanMessage(content=case.input)]
        tool_calls_made = []

        for tool_name in case.expected_tools:
            ai_msg = AIMessage(
                content="",
                tool_calls=[{"id": f"call_{tool_name}", "name": tool_name, "args": {}}],
            )
            messages.append(ai_msg)
            tool_calls_made.append(tool_name)

            mock_response = self.MOCK_TOOL_RESPONSES.get(tool_name, '{"status": "ok"}')
            messages.append(ToolMessage(content=mock_response, tool_call_id=f"call_{tool_name}"))

        final = self._generate_mock_response(case)
        messages.append(AIMessage(content=final))

        return {
            "messages": messages,
            "final_response": final,
            "tool_calls": tool_calls_made,
            "latency_ms": 500 + len(case.expected_tools) * 200,
            "token_usage": {"input": 800, "output": 300},
        }

    def _generate_mock_response(self, case: EvalCase) -> str:
        if "order" in case.tags and "query" in case.tags:
            return "订单 ORD20240115001 当前状态为**已发货**。\n支付状态: 已支付\n商品明细: LED Bulb 12W × 2000，单价 $7.9\n总金额: $15,800.00"
        if "logistics" in case.tags:
            return "订单 ORD20240115001 的物流信息：\n承运商: Maersk (MAEU1234567)\n当前状态: 运输中，目前在上海港\n预计到达: 2024-02-01\n目前未显示清关异常，建议继续关注海关放行状态。"
        if "cart" in case.tags:
            return "您的购物车中有 2 件商品: USB-C Cable 1m × 500、LED Strip 5m × 200，合计 $2,850.00。"
        if "email" in case.tags:
            return "我为您起草了以下邮件内容：\n\n...\n\n请确认是否发送？"
        if "safety" in case.tags and "permission" in case.tags:
            return "抱歉，您当前的权限无法查看所有用户的订单数据。如需平台级数据访问，请联系管理员。"
        if "clarification" in case.tags:
            return "请提供完整的订单号，以便我为您查询。您可以在购买记录中找到以 ORD 开头的订单编号。"
        return "已为您处理完毕。"


class EvalRunner:
    """评估运行器 — 协调数据集、Agent、评估器"""

    def __init__(self, cases: Optional[List[EvalCase]] = None, enable_llm_judge: bool = False):
        self.cases = cases or ALL_EVAL_CASES
        self.enable_llm_judge = enable_llm_judge
        self.trajectory_eval = TrajectoryEvaluator()
        self.quality_eval = ResponseQualityEvaluator()
        self.safety_eval = SafetyEvaluator()
        self.llm_judge = LLMJudgeEvaluator() if enable_llm_judge else None

    def evaluate_single(self, case: EvalCase, agent_output: Dict[str, Any]) -> EvalResult:
        scores: List[EvalScore] = []

        final_response = agent_output.get("final_response", "")
        actual_tools = agent_output.get("tool_calls", [])
        messages = agent_output.get("messages", [])

        # 轨迹
        scores.append(self.trajectory_eval.tool_subset_match(actual_tools, case.expected_tools))
        scores.append(self.trajectory_eval.tool_no_extra_calls(actual_tools, case.expected_tools))

        # 质量
        scores.append(self.quality_eval.keyword_coverage(final_response, case.expected_output_keywords))
        scores.append(self.quality_eval.response_not_empty(final_response))
        scores.append(self.quality_eval.language_consistency(final_response))

        # 安全
        scores.append(self.safety_eval.check_email_confirmation(messages, actual_tools))
        scores.append(self.safety_eval.check_privacy_protection(final_response))
        scores.append(self.safety_eval.check_permission_boundary(final_response, actual_tools, case.user_type))

        # LLM Judge
        if self.llm_judge:
            scores.append(self.llm_judge.evaluate(
                user_input=case.input, agent_response=final_response, tool_calls=actual_tools,
            ))

        return EvalResult(
            case_id=case.id, scores=scores,
            latency_ms=agent_output.get("latency_ms", 0),
            token_usage=agent_output.get("token_usage", {}),
        )

    def run_offline(self) -> EvalReport:
        """离线评估（MockAgent）"""
        logger.info(f"开始离线评估，{len(self.cases)} 条用例")
        mock = MockAgentRunner()
        results = []

        for case in self.cases:
            try:
                output = mock.run(case)
                result = self.evaluate_single(case, output)
                results.append(result)
                status = "PASS" if result.passed else "FAIL"
                logger.info(f"  {status} [{case.id}] score={result.overall_score:.2f}")
            except Exception as e:
                logger.error(f"  ERROR [{case.id}]: {e}")
                results.append(EvalResult(case_id=case.id, scores=[], error=str(e)))

        return self._build_report(results)

    def run_online(self, agent_fn: Callable[[str, str], Dict[str, Any]]) -> EvalReport:
        """在线评估（真实 Agent）"""
        logger.info(f"开始在线评估，{len(self.cases)} 条用例")
        results = []

        for case in self.cases:
            try:
                start = time.time()
                output = agent_fn(case.input, case.user_type)
                output["latency_ms"] = (time.time() - start) * 1000
                result = self.evaluate_single(case, output)
                results.append(result)
                status = "PASS" if result.passed else "FAIL"
                logger.info(f"  {status} [{case.id}] score={result.overall_score:.2f} latency={result.latency_ms:.0f}ms")
            except Exception as e:
                logger.error(f"  ERROR [{case.id}]: {e}")
                results.append(EvalResult(case_id=case.id, scores=[], error=str(e)))

        return self._build_report(results)

    def _build_report(self, results: List[EvalResult]) -> EvalReport:
        report = EvalReport(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_cases=len(results),
            passed_cases=sum(1 for r in results if r.passed),
            failed_cases=sum(1 for r in results if not r.passed),
            results=results,
        )

        valid = [r for r in results if r.scores]
        if valid:
            report.pass_rate = report.passed_cases / report.total_cases
            report.avg_score = sum(r.overall_score for r in valid) / len(valid)
            report.avg_latency_ms = sum(r.latency_ms for r in valid) / len(valid)

            dim_scores = defaultdict(list)
            for r in valid:
                for s in r.scores:
                    dim_scores[s.name].append(s.score)
            report.score_by_dimension = {k: sum(v) / len(v) for k, v in dim_scores.items()}

            tag_scores = defaultdict(list)
            for r, case in zip(results, self.cases):
                if r.scores:
                    for tag in case.tags:
                        tag_scores[tag].append(r.overall_score)
            report.score_by_tag = {k: sum(v) / len(v) for k, v in tag_scores.items()}

            diff_scores = defaultdict(list)
            for r, case in zip(results, self.cases):
                if r.scores:
                    diff_scores[case.difficulty].append(r.overall_score)
            report.score_by_difficulty = {k: sum(v) / len(v) for k, v in diff_scores.items()}

        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="评估器")
    parser.add_argument("--tag", type=str, help="按标签筛选")
    parser.add_argument("--difficulty", type=str, choices=["easy", "normal", "hard"])
    parser.add_argument("--llm-judge", action="store_true")
    parser.add_argument("--output", type=str, default="eval_report.json")
    parser.add_argument("--summary", action="store_true", default=True)

    args = parser.parse_args()

    if args.summary:
        summary = get_dataset_summary()
        print(f"\n数据集: {summary['total']} 条用例")
        print(f"   难度: easy={summary['easy']}, normal={summary['normal']}, hard={summary['hard']}")
        print(f"   标签: {summary['tags']}\n")

    cases = ALL_EVAL_CASES
    if args.tag:
        cases = get_cases_by_tag(args.tag)
        print(f"筛选标签: {args.tag}, {len(cases)} 条用例")

    if not cases:
        print("无匹配用例")
        return

    runner = EvalRunner(cases=cases, enable_llm_judge=args.llm_judge)
    report = runner.run_offline()
    report.print_summary()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"报告已保存: {args.output}")


if __name__ == "__main__":
    main()
