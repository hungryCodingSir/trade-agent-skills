"""评估 API 路由"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from app.evaluation.datasets import get_dataset_summary, get_cases_by_tag, ALL_EVAL_CASES
from app.evaluation.runner import EvalRunner

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


class RunEvalRequest(BaseModel):
    tags: Optional[List[str]] = None
    difficulty: Optional[str] = None
    enable_llm_judge: bool = False


@router.get("/dataset")
async def dataset_summary():
    """查看评估数据集统计"""
    return get_dataset_summary()


@router.post("/run")
async def run_offline_eval(req: RunEvalRequest):
    """运行离线评估（MockAgent）"""
    cases = ALL_EVAL_CASES

    if req.tags:
        filtered = []
        for tag in req.tags:
            filtered.extend(get_cases_by_tag(tag))
        seen = set()
        cases = []
        for c in filtered:
            if c.id not in seen:
                seen.add(c.id)
                cases.append(c)

    runner = EvalRunner(cases=cases, enable_llm_judge=req.enable_llm_judge)
    report = runner.run_offline()

    return report.to_dict()
