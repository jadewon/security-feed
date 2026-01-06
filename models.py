"""
공통 데이터 모델 정의
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FeedItem:
    """모든 피드 소스의 공통 인터페이스"""
    id: str                      # 고유 ID (source:identifier)
    source: str                  # nvd | thehackernews | github
    title: str                   # 제목
    description: str             # 설명
    url: str                     # 원본 링크
    published_at: datetime       # 발행 시간
    raw_data: dict = field(default_factory=dict)  # 원본 데이터 (디버깅용)

    def matches_keywords(self, keywords: list[str]) -> list[str]:
        """키워드 매칭 검사, 매칭된 키워드 리스트 반환"""
        text = f"{self.title} {self.description}".lower()
        matched = []
        for keyword in keywords:
            if keyword.lower() in text:
                matched.append(keyword)
        return matched


@dataclass
class AnalysisResult:
    """LLM 분석 결과"""
    is_relevant: bool            # 관련성 여부
    tech: str                    # 관련 기술
    severity: str                # critical | high | medium | low
    action_required: bool        # 즉각 조치 필요 여부
    summary: str                 # 한줄 요약
    raw_response: Optional[str] = None  # LLM 원본 응답 (디버깅용)


@dataclass
class ProcessedItem:
    """처리 완료된 항목 (중복 제거용)"""
    id: str                      # FeedItem.id
    first_seen: datetime         # 최초 발견 시간
    source: str                  # 피드 소스
    title: str                   # 제목 (로깅용)
