"""
KISA 보호나라 RSS 피드 수집기
- 보안공지: https://www.boho.or.kr/kr/rss.do?bbsId=B0000133
- 취약점 정보: https://www.boho.or.kr/kr/rss.do?bbsId=B0000302
"""

import re
from datetime import datetime
from typing import List
from urllib.parse import parse_qs, urlparse

import feedparser

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem
from .base import BaseCollector


class KISACollector(BaseCollector):
    """KISA 보호나라 RSS 피드 수집기"""

    FEEDS = {
        "advisory": "https://www.boho.or.kr/kr/rss.do?bbsId=B0000133",
        "vulnerability": "https://www.boho.or.kr/kr/rss.do?bbsId=B0000302",
    }

    def __init__(self, feed_urls: dict = None):
        self.feed_urls = feed_urls or self.FEEDS

    @property
    def source_name(self) -> str:
        return "kisa"

    def fetch(self) -> List[FeedItem]:
        """KISA RSS 피드를 가져와 FeedItem 리스트로 변환"""
        items = []

        for feed_type, url in self.feed_urls.items():
            feed = feedparser.parse(url)

            if feed.bozo:
                print(f"[WARN] KISA {feed_type} 피드 파싱 경고: {feed.bozo_exception}")

            for entry in feed.entries:
                try:
                    item = self._parse_entry(entry, feed_type)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[ERROR] KISA {feed_type} 항목 파싱 실패: {e}")
                    continue

        print(f"[INFO] KISA 보호나라에서 {len(items)}개 항목 수집")
        return items

    def _parse_entry(self, entry, feed_type: str) -> FeedItem:
        """RSS 항목을 FeedItem으로 변환"""
        title = entry.get("title", "").strip()
        link = entry.get("link", "")

        # nttId를 링크에서 추출하여 고유 식별자로 사용
        identifier = self._extract_ntt_id(link)
        if not identifier:
            identifier = title[:50]

        published_at = self._parse_date(entry)

        # KISA RSS는 description이 없으므로 title에서 정보 보강
        description = self._build_description(title, feed_type)

        return FeedItem(
            id=self._make_id(identifier),
            source=self.source_name,
            title=title,
            description=description,
            url=link,
            published_at=published_at,
            raw_data=dict(entry),
        )

    def _extract_ntt_id(self, url: str) -> str:
        """URL에서 nttId 파라미터 추출"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            ntt_ids = params.get("nttId", [])
            if ntt_ids:
                return ntt_ids[0]
        except Exception:
            pass
        return None

    def _parse_date(self, entry) -> datetime:
        """발행 시간 파싱 (KISA는 YYYY-MM-DD 형식)"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.published_parsed))

        # pubDate 텍스트에서 직접 파싱
        date_str = entry.get("published", entry.get("pubDate", ""))
        if date_str:
            try:
                return datetime.strptime(date_str.strip(), "%Y-%m-%d")
            except ValueError:
                pass

        return datetime.now()

    def _build_description(self, title: str, feed_type: str) -> str:
        """title 기반으로 description 보강"""
        parts = []

        if feed_type == "advisory":
            parts.append("[KISA 보안공지]")
        elif feed_type == "vulnerability":
            parts.append("[KISA 취약점 정보]")

        # CVE ID 추출
        cve_match = re.search(r"CVE-\d{4}-\d+", title, re.IGNORECASE)
        if cve_match:
            parts.append(f"CVE: {cve_match.group(0).upper()}")

        parts.append(title)
        return " ".join(parts)
