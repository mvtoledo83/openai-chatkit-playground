"""
Simple in-memory store compatible with the ChatKit Store interface.
A production app would implement this using a persistant database.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from pydantic import TypeAdapter
from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata


class MemoryStore(Store[dict]):
    def __init__(self):
        self.threads: dict[str, ThreadMetadata] = {}
        self.items: dict[str, list[ThreadItem]] = defaultdict(list)
        self._thread_item_adapter = TypeAdapter(ThreadItem)
        self._storage_path = self._resolve_storage_path()
        self._load_from_disk()

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self.threads[thread_id]

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        self.threads[thread.id] = thread
        self._save_to_disk()

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict
    ) -> Page[ThreadMetadata]:
        threads = list(self.threads.values())
        return self._paginate(
            threads,
            after,
            limit,
            order,
            sort_key=lambda t: t.created_at,
            cursor_key=lambda t: t.id,
        )

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict
    ) -> Page[ThreadItem]:
        items = self.items.get(thread_id, [])
        return self._paginate(
            items,
            after,
            limit,
            order,
            sort_key=lambda i: i.created_at,
            cursor_key=lambda i: i.id,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict
    ) -> None:
        self.items[thread_id].append(item)
        self._save_to_disk()

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        items = self.items[thread_id]
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                self._save_to_disk()
                return
        items.append(item)
        self._save_to_disk()

    async def load_item(
        self, thread_id: str, item_id: str, context: dict
    ) -> ThreadItem:
        for item in self.items.get(thread_id, []):
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        self.threads.pop(thread_id, None)
        self.items.pop(thread_id, None)
        self._save_to_disk()

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict
    ) -> None:
        self.items[thread_id] = [
            item for item in self.items.get(thread_id, []) if item.id != item_id
        ]
        self._save_to_disk()

    def _resolve_storage_path(self) -> Path:
        env_value = os.getenv("CHATKIT_STORE_FILE")
        if env_value:
            return Path(env_value)
        return Path(__file__).resolve().parent.parent / ".chatkit_store.json"

    def _load_from_disk(self) -> None:
        if not self._storage_path.exists():
            return

        raw_data = self._storage_path.read_text(encoding="utf-8")
        if not raw_data.strip():
            return

        payload = json.loads(raw_data)
        raw_threads = payload.get("threads")
        raw_items = payload.get("items")

        if isinstance(raw_threads, dict):
            for thread_id, thread_data in raw_threads.items():
                if not isinstance(thread_id, str) or not isinstance(thread_data, dict):
                    continue
                try:
                    self.threads[thread_id] = ThreadMetadata.model_validate(thread_data)
                except Exception:
                    continue

        if isinstance(raw_items, dict):
            for thread_id, items_data in raw_items.items():
                if not isinstance(thread_id, str) or not isinstance(items_data, list):
                    continue
                parsed_items: list[ThreadItem] = []
                for item_data in items_data:
                    if not isinstance(item_data, dict):
                        continue
                    try:
                        parsed_items.append(
                            self._thread_item_adapter.validate_python(item_data)
                        )
                    except Exception:
                        continue
                if parsed_items:
                    self.items[thread_id] = parsed_items

    def _save_to_disk(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "threads": {
                thread_id: thread.model_dump(mode="json", exclude_none=True)
                for thread_id, thread in self.threads.items()
            },
            "items": {
                thread_id: [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in thread_items
                ]
                for thread_id, thread_items in self.items.items()
            },
        }
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _paginate(
        self,
        rows: list,
        after: str | None,
        limit: int,
        order: str,
        sort_key,
        cursor_key,
    ):
        sorted_rows = sorted(rows, key=sort_key, reverse=order == "desc")
        start = 0
        if after:
            for idx, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = idx + 1
                    break
        data = sorted_rows[start : start + limit]
        has_more = start + limit < len(sorted_rows)
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)

    # Attachments are not implemented in the quickstart store

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        raise NotImplementedError()

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        raise NotImplementedError()
