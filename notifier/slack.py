"""
Slack 알림 발송
"""

import os
from typing import List, Optional

import requests

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem, AnalysisResult


class SlackNotifier:
    """Slack 알림 발송기"""

    SEVERITY_EMOJI = {
        "critical": ":rotating_light:",  # 🚨
        "high": ":warning:",              # ⚠️
        "medium": ":large_blue_circle:",  # 🔵
        "low": ":white_circle:",          # ⚪
    }

    def __init__(
        self,
        webhook_url: str = None,
        mention_users: List[str] = None,
    ):
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            print("[WARN] SLACK_WEBHOOK_URL이 설정되지 않음")

        self.mention_users = mention_users or []

    def send_alert(
        self,
        item: FeedItem,
        analysis: AnalysisResult,
        dry_run: bool = False,
    ) -> bool:
        """즉시 알림 발송 (Critical/High)"""
        if not self.webhook_url:
            print("[WARN] Webhook URL 없음, 알림 스킵")
            return False

        emoji = self.SEVERITY_EMOJI.get(analysis.severity, ":question:")
        severity_upper = analysis.severity.upper()

        # 멘션 생성 (critical/high일 때만)
        mentions = ""
        if analysis.severity in ["critical", "high"] and self.mention_users:
            mentions = " ".join(f"@{user}" for user in self.mention_users)

        # CVE ID 추출
        import re
        cve_match = re.search(r"CVE-\d{4}-\d+", item.title, re.IGNORECASE)
        cve_id = cve_match.group(0) if cve_match else "N/A"

        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} [{severity_upper}] {item.title[:100]}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*CVE*\n{cve_id}"},
                        {"type": "mrkdwn", "text": f"*영향 기술*\n{analysis.tech}"},
                        {"type": "mrkdwn", "text": f"*심각도*\n{severity_upper}"},
                        {"type": "mrkdwn", "text": f"*조치 필요*\n{'예' if analysis.action_required else '아니오'}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*요약*\n{analysis.summary}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":link: <{item.url}|상세 보기>",
                    },
                },
            ],
        }

        if mentions:
            message["blocks"].append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": mentions}],
            })

        if dry_run:
            print(f"[DRY-RUN] 알림 발송: {item.title[:50]}...")
            return True

        return self._send(message)

    def send_batch_alerts(
        self,
        items: List[tuple[FeedItem, AnalysisResult]],
        dry_run: bool = False,
    ) -> bool:
        """여러 알림을 한 번에 모아서 발송"""
        if not self.webhook_url:
            print("[WARN] Webhook URL 없음, 알림 스킵")
            return False

        if not items:
            return True

        import re

        # 심각도별 그룹화 (critical 먼저, 그 다음 high)
        critical_items = [(i, a) for i, a in items if a.severity == "critical"]
        high_items = [(i, a) for i, a in items if a.severity == "high"]
        sorted_items = critical_items + high_items

        if not sorted_items:
            return True

        # 멘션 생성
        mentions = ""
        if self.mention_users:
            mentions = " ".join(f"@{user}" for user in self.mention_users)

        # 헤더 블록
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":rotating_light: 보안 알림 ({len(sorted_items)}건)",
                },
            },
        ]

        # 멘션 추가
        if mentions:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": mentions},
            })

        blocks.append({"type": "divider"})

        # 각 항목 추가
        for item, analysis in sorted_items:
            emoji = self.SEVERITY_EMOJI.get(analysis.severity, ":question:")
            severity_upper = analysis.severity.upper()

            # CVE ID 추출
            cve_match = re.search(r"CVE-\d{4}-\d+", item.title, re.IGNORECASE)
            cve_id = cve_match.group(0) if cve_match else ""

            title = f"{emoji} [{severity_upper}] {item.title[:80]}"
            if len(item.title) > 80:
                title += "..."

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{item.url}|{title}>*\n"
                           f"• 영향 기술: `{analysis.tech}`\n"
                           f"• {analysis.summary}",
                },
            })

        # Slack 블록 제한 (50개) 처리
        if len(blocks) > 50:
            blocks = blocks[:49]
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"... 외 {len(sorted_items) - 45}건"}],
            })

        message = {"blocks": blocks}

        if dry_run:
            print(f"[DRY-RUN] 일괄 알림 발송: {len(sorted_items)}건")
            return True

        return self._send(message)

    def send_daily_summary(
        self,
        items: List[tuple[FeedItem, AnalysisResult]],
        date_str: str,
        dry_run: bool = False,
    ) -> bool:
        """일일 요약 발송"""
        if not self.webhook_url:
            print("[WARN] Webhook URL 없음, 알림 스킵")
            return False

        if not items:
            print("[INFO] 요약할 항목 없음")
            return True

        # 심각도별 그룹화
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for item, analysis in items:
            by_severity[analysis.severity].append((item, analysis))

        # 메시지 구성
        summary_lines = []
        total = len(items)

        for severity in ["critical", "high", "medium", "low"]:
            count = len(by_severity[severity])
            if count > 0:
                emoji = self.SEVERITY_EMOJI[severity]
                summary_lines.append(f"{emoji} {severity.upper()}: {count}건")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":clipboard: [일일 보안 요약] {date_str}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"총 *{total}건*의 관련 보안 정보가 수집되었습니다.\n" + "\n".join(summary_lines),
                },
            },
            {"type": "divider"},
        ]

        # 상위 5개 항목 표시
        for item, analysis in items[:5]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{item.url}|{item.title[:60]}>*\n{analysis.summary}",
                },
            })

        if len(items) > 5:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"... 외 {len(items) - 5}건"}],
            })

        message = {"blocks": blocks}

        if dry_run:
            print(f"[DRY-RUN] 일일 요약 발송: {total}건")
            return True

        return self._send(message)

    def _send(self, message: dict) -> bool:
        """Slack webhook으로 메시지 발송"""
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10,
            )

            if response.status_code == 200:
                print("[INFO] Slack 알림 발송 성공")
                return True
            else:
                print(f"[ERROR] Slack 알림 실패: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"[ERROR] Slack 알림 발송 오류: {e}")
            return False
