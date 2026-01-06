"""
피드 수집기 베이스 클래스
"""

from abc import ABC, abstractmethod
from typing import List

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem


class BaseCollector(ABC):
    """피드 수집기 추상 베이스 클래스"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """소스 이름 (nvd, thehackernews, github)"""
        pass

    @abstractmethod
    def fetch(self) -> List[FeedItem]:
        """피드를 가져와 FeedItem 리스트로 변환"""
        pass

    def _make_id(self, identifier: str) -> str:
        """고유 ID 생성 (source:identifier)"""
        return f"{self.source_name}:{identifier}"
