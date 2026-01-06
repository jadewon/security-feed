"""
기술 스택 키워드 필터
"""

from dataclasses import dataclass
from typing import List, Dict

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem


@dataclass
class FilterResult:
    """필터링 결과"""
    matched: bool
    matched_keywords: List[str]
    matched_categories: List[str]


class TechStackFilter:
    """기술 스택 키워드 기반 필터"""

    def __init__(self, tech_keywords: Dict[str, List[str]]):
        """
        Args:
            tech_keywords: 카테고리별 키워드 딕셔너리
                예: {"frontend": ["react", "vue"], "backend": ["nestjs", "spring"]}
        """
        self.tech_keywords = tech_keywords
        # 전체 키워드를 소문자로 평탄화
        self._all_keywords = self._flatten_keywords()

    def _flatten_keywords(self) -> Dict[str, str]:
        """키워드 → 카테고리 매핑 생성"""
        keyword_to_category = {}
        for category, keywords in self.tech_keywords.items():
            for keyword in keywords:
                keyword_to_category[keyword.lower()] = category
        return keyword_to_category

    def filter(self, item: FeedItem) -> FilterResult:
        """항목이 기술 스택과 매칭되는지 확인"""
        text = f"{item.title} {item.description}".lower()

        matched_keywords = []
        matched_categories = set()

        for keyword, category in self._all_keywords.items():
            # 단어 경계를 고려한 매칭 (예: "go"가 "google"에 매칭되지 않도록)
            if self._keyword_matches(keyword, text):
                matched_keywords.append(keyword)
                matched_categories.add(category)

        return FilterResult(
            matched=len(matched_keywords) > 0,
            matched_keywords=matched_keywords,
            matched_categories=list(matched_categories),
        )

    def _keyword_matches(self, keyword: str, text: str) -> bool:
        """키워드가 텍스트에 매칭되는지 확인 (단어 경계 고려)"""
        import re

        # 특수문자가 포함된 키워드는 그대로 검색 (예: "next.js", "vue.js")
        if "." in keyword or "-" in keyword:
            return keyword in text

        # 일반 키워드는 단어 경계 확인
        # "go"가 "google"에 매칭되지 않도록
        pattern = rf"\b{re.escape(keyword)}\b"
        return bool(re.search(pattern, text))

    def get_all_keywords(self) -> List[str]:
        """전체 키워드 목록 반환"""
        return list(self._all_keywords.keys())
