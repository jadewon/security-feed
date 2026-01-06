"""
필터링 파이프라인
기술 스택 필터 + 점수 계산을 통합
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem
from .tech_filter import TechStackFilter, FilterResult
from .score_calculator import ScoreCalculator, ScoreResult


@dataclass
class PipelineResult:
    """파이프라인 처리 결과"""
    item: FeedItem
    tech_filter_result: FilterResult
    score_result: ScoreResult

    @property
    def passed_tech_filter(self) -> bool:
        return self.tech_filter_result.matched

    @property
    def score(self) -> int:
        return self.score_result.score

    @property
    def severity(self) -> str:
        return ScoreCalculator().get_severity_level(self.score)

    @property
    def should_analyze_with_llm(self) -> bool:
        """LLM 분석 대상인지 (점수 3 이상)"""
        return self.passed_tech_filter and self.score >= 3


class FilterPipeline:
    """필터링 파이프라인"""

    def __init__(
        self,
        tech_keywords: Dict[str, List[str]],
        security_keywords: Dict[str, List[str]] = None,
        min_score_for_llm: int = 3,
    ):
        self.tech_filter = TechStackFilter(tech_keywords)
        self.score_calculator = ScoreCalculator(security_keywords)
        self.min_score_for_llm = min_score_for_llm

    def process(self, items: List[FeedItem]) -> List[PipelineResult]:
        """전체 항목 처리"""
        results = []
        for item in items:
            result = self.process_single(item)
            results.append(result)
        return results

    def process_single(self, item: FeedItem) -> PipelineResult:
        """단일 항목 처리"""
        tech_result = self.tech_filter.filter(item)
        score_result = self.score_calculator.calculate(item)

        return PipelineResult(
            item=item,
            tech_filter_result=tech_result,
            score_result=score_result,
        )

    def filter_for_llm(self, items: List[FeedItem]) -> Tuple[List[PipelineResult], List[PipelineResult]]:
        """
        LLM 분석 대상과 비대상으로 분리

        Returns:
            (llm_candidates, filtered_out)
        """
        results = self.process(items)

        llm_candidates = []
        filtered_out = []

        for result in results:
            if result.should_analyze_with_llm:
                llm_candidates.append(result)
            else:
                filtered_out.append(result)

        return llm_candidates, filtered_out

    def get_stats(self, results: List[PipelineResult]) -> Dict:
        """처리 결과 통계"""
        total = len(results)
        passed_tech = sum(1 for r in results if r.passed_tech_filter)
        llm_candidates = sum(1 for r in results if r.should_analyze_with_llm)

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in results:
            if r.passed_tech_filter:
                severity_counts[r.severity] += 1

        return {
            "total": total,
            "passed_tech_filter": passed_tech,
            "llm_candidates": llm_candidates,
            "filtered_out": total - passed_tech,
            "severity_distribution": severity_counts,
        }
