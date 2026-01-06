"""
NVD (National Vulnerability Database) RSS 피드 수집기
"""

import re
from datetime import datetime
from typing import List

import feedparser

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem
from .base import BaseCollector


class NVDCollector(BaseCollector):
    """NVD RSS 피드 수집기"""

    DEFAULT_URL = "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml"

    def __init__(self, feed_url: str = None):
        self.feed_url = feed_url or self.DEFAULT_URL

    @property
    def source_name(self) -> str:
        return "nvd"

    def fetch(self) -> List[FeedItem]:
        """NVD RSS 피드를 가져와 FeedItem 리스트로 변환"""
        feed = feedparser.parse(self.feed_url)

        if feed.bozo:
            print(f"[WARN] NVD 피드 파싱 경고: {feed.bozo_exception}")

        items = []
        for entry in feed.entries:
            try:
                item = self._parse_entry(entry)
                if item:
                    items.append(item)
            except Exception as e:
                print(f"[ERROR] NVD 항목 파싱 실패: {e}")
                continue

        print(f"[INFO] NVD에서 {len(items)}개 항목 수집")
        return items

    def _parse_entry(self, entry) -> FeedItem:
        """RSS 항목을 FeedItem으로 변환"""
        # CVE ID 추출 (제목에서)
        cve_id = self._extract_cve_id(entry.get("title", ""))
        if not cve_id:
            cve_id = entry.get("id", "unknown")

        # 발행 시간 파싱
        published_at = self._parse_date(entry)

        return FeedItem(
            id=self._make_id(cve_id),
            source=self.source_name,
            title=entry.get("title", ""),
            description=entry.get("description", entry.get("summary", "")),
            url=entry.get("link", ""),
            published_at=published_at,
            raw_data=dict(entry),
        )

    def _extract_cve_id(self, title: str) -> str:
        """제목에서 CVE ID 추출"""
        match = re.search(r"CVE-\d{4}-\d+", title, re.IGNORECASE)
        return match.group(0).upper() if match else None

    def _parse_date(self, entry) -> datetime:
        """발행 시간 파싱"""
        # dc:date 또는 published 필드 확인
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.published_parsed))

        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.updated_parsed))

        # dc:date 형식 (ISO 8601)
        date_str = entry.get("dc_date", entry.get("date", ""))
        if date_str:
            try:
                # 2024-01-01T00:00:00Z 형식
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return datetime.now()
