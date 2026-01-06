"""
GitHub Security Advisory GraphQL API 수집기
"""

import os
from datetime import datetime
from typing import List, Optional

import requests

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem
from .base import BaseCollector


class GitHubCollector(BaseCollector):
    """GitHub Security Advisory 수집기"""

    API_URL = "https://api.github.com/graphql"

    QUERY = """
    query($first: Int!) {
      securityAdvisories(first: $first, orderBy: {field: PUBLISHED_AT, direction: DESC}) {
        nodes {
          ghsaId
          summary
          description
          severity
          publishedAt
          updatedAt
          permalink
          vulnerabilities(first: 10) {
            nodes {
              package {
                name
                ecosystem
              }
              severity
              vulnerableVersionRange
            }
          }
          identifiers {
            type
            value
          }
        }
      }
    }
    """

    def __init__(self, token: str = None, limit: int = 20):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("ONDABOT_TOKEN")
        self.limit = limit

    @property
    def source_name(self) -> str:
        return "github"

    def fetch(self) -> List[FeedItem]:
        """GitHub Advisory를 가져와 FeedItem 리스트로 변환"""
        if not self.token:
            print("[WARN] GITHUB_TOKEN 또는 ONDABOT_TOKEN이 설정되지 않음, GitHub Advisory 스킵")
            return []

        try:
            data = self._query_api()
            if not data:
                return []

            advisories = data.get("data", {}).get("securityAdvisories", {}).get("nodes", [])

            items = []
            for advisory in advisories:
                try:
                    item = self._parse_advisory(advisory)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[ERROR] GitHub Advisory 파싱 실패: {e}")
                    continue

            print(f"[INFO] GitHub Advisory에서 {len(items)}개 항목 수집")
            return items

        except Exception as e:
            print(f"[ERROR] GitHub API 호출 실패: {e}")
            return []

    def _query_api(self) -> Optional[dict]:
        """GraphQL API 호출"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            self.API_URL,
            json={"query": self.QUERY, "variables": {"first": self.limit}},
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"[ERROR] GitHub API 응답 오류: {response.status_code}")
            return None

        return response.json()

    def _parse_advisory(self, advisory: dict) -> FeedItem:
        """Advisory를 FeedItem으로 변환"""
        ghsa_id = advisory.get("ghsaId", "")

        # CVE ID 추출 (있는 경우)
        cve_id = None
        for identifier in advisory.get("identifiers", []):
            if identifier.get("type") == "CVE":
                cve_id = identifier.get("value")
                break

        # 제목 생성 (CVE 포함)
        title = advisory.get("summary", "")
        if cve_id and cve_id not in title:
            title = f"{cve_id}: {title}"

        # 영향받는 패키지 정보 추가
        packages = self._get_affected_packages(advisory)
        description = advisory.get("description", advisory.get("summary", ""))
        if packages:
            description = f"{description}\n\nAffected packages: {', '.join(packages)}"

        # 발행 시간 파싱
        published_at = self._parse_date(advisory.get("publishedAt"))

        return FeedItem(
            id=self._make_id(ghsa_id),
            source=self.source_name,
            title=title,
            description=description,
            url=advisory.get("permalink", f"https://github.com/advisories/{ghsa_id}"),
            published_at=published_at,
            raw_data=advisory,
        )

    def _get_affected_packages(self, advisory: dict) -> List[str]:
        """영향받는 패키지 목록 추출"""
        packages = []
        for vuln in advisory.get("vulnerabilities", {}).get("nodes", []):
            pkg = vuln.get("package", {})
            name = pkg.get("name", "")
            ecosystem = pkg.get("ecosystem", "")
            if name:
                packages.append(f"{ecosystem}/{name}" if ecosystem else name)
        return packages

    def _parse_date(self, date_str: str) -> datetime:
        """ISO 8601 날짜 파싱"""
        if not date_str:
            return datetime.now()

        try:
            # 2024-01-01T00:00:00Z 형식
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now()
