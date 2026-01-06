"""
The Hacker News RSS 피드 수집기
"""

import hashlib
from datetime import datetime
from time import mktime
from typing import List

import feedparser

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem
from .base import BaseCollector


class THNCollector(BaseCollector):
    """The Hacker News RSS 피드 수집기"""

    DEFAULT_URL = "https://feeds.feedburner.com/TheHackersNews"

    def __init__(self, feed_url: str = None):
        self.feed_url = feed_url or self.DEFAULT_URL

    @property
    def source_name(self) -> str:
        return "thehackernews"

    def fetch(self) -> List[FeedItem]:
        """THN RSS 피드를 가져와 FeedItem 리스트로 변환"""
        feed = feedparser.parse(self.feed_url)

        if feed.bozo:
            print(f"[WARN] THN 피드 파싱 경고: {feed.bozo_exception}")

        items = []
        for entry in feed.entries:
            try:
                item = self._parse_entry(entry)
                if item:
                    items.append(item)
            except Exception as e:
                print(f"[ERROR] THN 항목 파싱 실패: {e}")
                continue

        print(f"[INFO] The Hacker News에서 {len(items)}개 항목 수집")
        return items

    def _parse_entry(self, entry) -> FeedItem:
        """RSS 항목을 FeedItem으로 변환"""
        # guid 또는 link로 고유 ID 생성
        identifier = entry.get("id", entry.get("guid", ""))
        if not identifier:
            # fallback: URL 해시
            identifier = hashlib.md5(entry.get("link", "").encode()).hexdigest()[:12]

        # 발행 시간 파싱
        published_at = self._parse_date(entry)

        # 설명에서 HTML 태그 제거
        description = self._clean_html(entry.get("description", entry.get("summary", "")))

        return FeedItem(
            id=self._make_id(identifier),
            source=self.source_name,
            title=entry.get("title", ""),
            description=description,
            url=entry.get("link", ""),
            published_at=published_at,
            raw_data=dict(entry),
        )

    def _parse_date(self, entry) -> datetime:
        """발행 시간 파싱"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))

        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime.fromtimestamp(mktime(entry.updated_parsed))

        return datetime.now()

    def _clean_html(self, text: str) -> str:
        """HTML 태그 제거"""
        import re
        # HTML 태그 제거
        clean = re.sub(r"<[^>]+>", "", text)
        # 연속 공백 정리
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
