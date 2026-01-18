#!/usr/bin/env python3
"""
Security Feed Automation
보안 피드를 수집, 필터링, 분석하여 Slack으로 알림 발송
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 모듈 경로 설정
sys.path.insert(0, str(Path(__file__).parent))

from models import FeedItem, AnalysisResult
from collectors import NVDCollector, THNCollector, GitHubCollector
from filters import FilterPipeline
from llm import GemmaAnalyzer
from storage import DeduplicationStore
from notifier import SlackNotifier


def load_config(config_path: str = None) -> dict:
    """설정 파일 로드"""
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_feeds(config: dict) -> list[FeedItem]:
    """모든 소스에서 피드 수집"""
    items = []

    feed_config = config.get("feeds", {})

    # NVD
    if feed_config.get("nvd", {}).get("enabled", True):
        collector = NVDCollector(feed_config.get("nvd", {}).get("url"))
        items.extend(collector.fetch())

    # The Hacker News
    if feed_config.get("thehackernews", {}).get("enabled", True):
        collector = THNCollector(feed_config.get("thehackernews", {}).get("url"))
        items.extend(collector.fetch())

    # GitHub Advisory
    if feed_config.get("github", {}).get("enabled", True):
        collector = GitHubCollector()
        items.extend(collector.fetch())

    return items


def run_pipeline(
    config: dict,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """메인 파이프라인 실행"""
    stats = {
        "collected": 0,
        "new_items": 0,
        "passed_filter": 0,
        "llm_analyzed": 0,
        "alerts_sent": 0,
    }

    # 1. 피드 수집
    logger.info("=" * 50)
    logger.info("[1/5] 피드 수집 중...")
    items = collect_feeds(config)
    stats["collected"] = len(items)
    logger.info(f"      수집 완료: {len(items)}개")

    if not items:
        logger.info("수집된 항목 없음")
        return stats

    # 2. 중복 제거
    logger.info("[2/5] 중복 제거 중...")
    dedup_config = config.get("deduplication", {})
    storage_path = Path(__file__).parent / dedup_config.get("storage_file", "data/processed.json")
    dedup = DeduplicationStore(str(storage_path), dedup_config.get("retention_days", 90))

    # 오래된 항목 자동 정리
    dedup.cleanup_old_entries()

    new_items = dedup.filter_new_items(items)
    stats["new_items"] = len(new_items)
    logger.info(f"      신규 항목: {len(new_items)}개 (기존 {len(items) - len(new_items)}개 스킵)")

    if not new_items:
        logger.info("신규 항목 없음")
        return stats

    # 3. 필터링
    logger.info("[3/5] 필터링 중...")
    # whitelist를 1차 필터링 키워드로도 사용
    whitelist = config.get("whitelist", {})
    security_keywords = config.get("security_keywords", {})
    min_score = config.get("filtering", {}).get("min_score_for_llm", 3)

    pipeline = FilterPipeline(whitelist, security_keywords, min_score)
    llm_candidates, filtered_out = pipeline.filter_for_llm(new_items)
    stats["passed_filter"] = len(llm_candidates)

    logger.info(f"      LLM 분석 대상: {len(llm_candidates)}개")
    logger.info(f"      필터링 제외: {len(filtered_out)}개")

    if verbose:
        for result in llm_candidates:
            logger.info(f"        - [{result.score}점] {result.item.title[:50]}...")

    if not llm_candidates:
        # 신규 항목은 처리됨으로 표시
        dedup.mark_all_processed(new_items)
        logger.info("LLM 분석 대상 없음")
        return stats

    # 4. LLM 분석
    logger.info("[4/5] LLM 분석 중...")
    llm_config = config.get("llm", {})
    whitelist = config.get("whitelist", {})

    try:
        analyzer = GemmaAnalyzer(
            model=llm_config.get("model", "gemma-3-12b-it"),
            whitelist=_flatten_whitelist(whitelist),
        )

        analyzed = []
        for result in llm_candidates:
            analysis = analyzer.analyze(result.item)
            if analysis and analysis.is_relevant:
                analyzed.append((result.item, analysis))
                stats["llm_analyzed"] += 1

        logger.info(f"      관련 항목: {len(analyzed)}개")

    except Exception as e:
        logger.error(f"LLM 분석 실패: {e}")
        dedup.mark_all_processed(new_items)
        return stats

    # 5. 알림 발송
    logger.info("[5/5] 알림 발송 중...")
    slack_config = config.get("slack", {})
    notifier = SlackNotifier(
        mention_users=slack_config.get("mention_users", []),
    )

    # critical/high 항목만 필터링
    alert_items = [(item, analysis) for item, analysis in analyzed
                   if analysis.severity in ["critical", "high"]]

    if alert_items:
        if notifier.send_batch_alerts(alert_items, dry_run=dry_run):
            stats["alerts_sent"] = len(alert_items)

    logger.info(f"      알림 발송: {stats['alerts_sent']}건")

    # 처리 완료 표시
    dedup.mark_all_processed(new_items)

    logger.info("=" * 50)
    logger.info("[완료] 파이프라인 실행 완료")
    logger.info(f"       수집: {stats['collected']} → 신규: {stats['new_items']} → 필터: {stats['passed_filter']} → LLM: {stats['llm_analyzed']} → 알림: {stats['alerts_sent']}")

    return stats


def run_cleanup(config: dict) -> None:
    """오래된 데이터 정리"""
    logger.info("[정리] 오래된 항목 삭제 중...")
    dedup_config = config.get("deduplication", {})
    storage_path = Path(__file__).parent / dedup_config.get("storage_file", "data/processed.json")
    dedup = DeduplicationStore(str(storage_path), dedup_config.get("retention_days", 90))
    deleted = dedup.cleanup_old_entries()
    logger.info(f"[정리] {deleted}개 항목 삭제됨")


def run_daily_summary(config: dict, dry_run: bool = False) -> None:
    """일일 요약 발송 (구현 예정)"""
    logger.info("일일 요약 기능은 아직 구현되지 않았습니다")
    # TODO: 오늘 처리된 항목들을 모아서 요약 발송


def _flatten_whitelist(whitelist: dict) -> list[str]:
    """화이트리스트를 평탄화"""
    result = []
    for category, items in whitelist.items():
        if isinstance(items, list):
            result.extend(items)
    return result


def main():
    parser = argparse.ArgumentParser(description="Security Feed Automation")
    parser.add_argument("--config", "-c", help="설정 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="알림 발송 없이 테스트")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--cleanup", action="store_true", help="오래된 데이터 정리")
    parser.add_argument("--daily-summary", action="store_true", help="일일 요약 발송")

    args = parser.parse_args()

    config = load_config(args.config)

    if args.cleanup:
        run_cleanup(config)
    elif args.daily_summary:
        run_daily_summary(config, args.dry_run)
    else:
        run_pipeline(config, args.dry_run, args.verbose)


if __name__ == "__main__":
    main()
