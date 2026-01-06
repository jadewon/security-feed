"""
중복 제거 저장소
JSON 파일 기반으로 처리된 항목을 추적
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from models import FeedItem, ProcessedItem


class DeduplicationStore:
    """JSON 파일 기반 중복 제거 저장소"""

    def __init__(self, storage_path: str, retention_days: int = 90):
        self.storage_path = Path(storage_path)
        self.retention_days = retention_days
        self._data: dict = {"processed_items": {}, "last_updated": None}
        self._load()

    def _load(self) -> None:
        """저장소 파일 로드"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARN] 저장소 파일 로드 실패, 새로 생성: {e}")
                self._data = {"processed_items": {}, "last_updated": None}
        else:
            # 디렉토리가 없으면 생성
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        """저장소 파일 저장"""
        self._data["last_updated"] = datetime.now().isoformat()
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def is_processed(self, item: FeedItem) -> bool:
        """이미 처리된 항목인지 확인"""
        return item.id in self._data["processed_items"]

    def mark_processed(self, item: FeedItem) -> None:
        """항목을 처리 완료로 표시"""
        self._data["processed_items"][item.id] = {
            "first_seen": datetime.now().isoformat(),
            "source": item.source,
            "title": item.title,
        }
        self._save()

    def get_processed_item(self, item_id: str) -> Optional[ProcessedItem]:
        """처리된 항목 조회"""
        if item_id not in self._data["processed_items"]:
            return None

        data = self._data["processed_items"][item_id]
        return ProcessedItem(
            id=item_id,
            first_seen=datetime.fromisoformat(data["first_seen"]),
            source=data["source"],
            title=data["title"],
        )

    def cleanup_old_entries(self) -> int:
        """retention_days 이상 된 항목 삭제, 삭제된 항목 수 반환"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        items_to_remove = []

        for item_id, data in self._data["processed_items"].items():
            first_seen = datetime.fromisoformat(data["first_seen"])
            if first_seen < cutoff:
                items_to_remove.append(item_id)

        for item_id in items_to_remove:
            del self._data["processed_items"][item_id]

        if items_to_remove:
            self._save()
            print(f"[INFO] {len(items_to_remove)}개의 오래된 항목 삭제됨")

        return len(items_to_remove)

    def get_stats(self) -> dict:
        """저장소 통계 반환"""
        return {
            "total_items": len(self._data["processed_items"]),
            "last_updated": self._data["last_updated"],
            "storage_path": str(self.storage_path),
        }

    def filter_new_items(self, items: list[FeedItem]) -> list[FeedItem]:
        """새 항목만 필터링하여 반환"""
        return [item for item in items if not self.is_processed(item)]

    def mark_all_processed(self, items: list[FeedItem]) -> None:
        """여러 항목을 한 번에 처리 완료로 표시 (배치 저장)"""
        for item in items:
            self._data["processed_items"][item.id] = {
                "first_seen": datetime.now().isoformat(),
                "source": item.source,
                "title": item.title,
            }
        if items:
            self._save()
