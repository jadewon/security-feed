"""
보안 점수 계산기
"""

import re
from dataclasses import dataclass
from typing import List, Dict

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem


@dataclass
class ScoreResult:
    """점수 계산 결과"""
    score: int
    breakdown: Dict[str, int]  # 점수 상세 내역
    matched_keywords: List[str]  # 매칭된 보안 키워드


class ScoreCalculator:
    """보안 점수 계산기"""

    # 기본 점수 가중치
    DEFAULT_WEIGHTS = {
        "cve_pattern": 3,      # CVE-XXXX-XXXXX 패턴
        "critical_keyword": 2,  # critical 키워드
        "high_keyword": 2,      # high 키워드
        "urgent_keyword": 1,    # urgent 키워드
    }

    def __init__(
        self,
        security_keywords: Dict[str, List[str]] = None,
        weights: Dict[str, int] = None,
    ):
        """
        Args:
            security_keywords: 심각도별 키워드
                {"critical": [...], "high": [...], "urgent": [...]}
            weights: 점수 가중치
        """
        self.security_keywords = security_keywords or self._default_keywords()
        self.weights = weights or self.DEFAULT_WEIGHTS

    def _default_keywords(self) -> Dict[str, List[str]]:
        """기본 보안 키워드"""
        return {
            "critical": [
                "remote code execution",
                "rce",
                "zero-day",
                "0-day",
                "critical vulnerability",
                "authentication bypass",
                "privilege escalation",
            ],
            "high": [
                "vulnerability",
                "exploit",
                "sql injection",
                "xss",
                "cross-site scripting",
                "command injection",
                "path traversal",
                "ssrf",
                "csrf",
            ],
            "urgent": [
                "urgent",
                "patch now",
                "immediately",
                "actively exploited",
                "in the wild",
            ],
        }

    def calculate(self, item: FeedItem) -> ScoreResult:
        """항목의 보안 점수 계산"""
        text = f"{item.title} {item.description}".lower()

        score = 0
        breakdown = {}
        matched_keywords = []

        # CVE 패턴 체크
        if re.search(r"cve-\d{4}-\d+", text, re.IGNORECASE):
            points = self.weights["cve_pattern"]
            score += points
            breakdown["cve_pattern"] = points
            matched_keywords.append("CVE")

        # Critical 키워드 체크 (하나라도 있으면 점수 부여)
        for keyword in self.security_keywords.get("critical", []):
            if keyword.lower() in text:
                points = self.weights["critical_keyword"]
                score += points
                breakdown["critical_keyword"] = points
                matched_keywords.append(keyword)
                break  # 한 번만 점수 부여

        # High 키워드 체크
        for keyword in self.security_keywords.get("high", []):
            if keyword.lower() in text:
                points = self.weights["high_keyword"]
                score += points
                breakdown["high_keyword"] = points
                matched_keywords.append(keyword)
                break

        # Urgent 키워드 체크
        for keyword in self.security_keywords.get("urgent", []):
            if keyword.lower() in text:
                points = self.weights["urgent_keyword"]
                score += points
                breakdown["urgent_keyword"] = points
                matched_keywords.append(keyword)
                break

        return ScoreResult(
            score=score,
            breakdown=breakdown,
            matched_keywords=matched_keywords,
        )

    def get_severity_level(self, score: int) -> str:
        """점수에 따른 심각도 레벨 반환"""
        if score >= 5:
            return "critical"
        elif score >= 3:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "low"
