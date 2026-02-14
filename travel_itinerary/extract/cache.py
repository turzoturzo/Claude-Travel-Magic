"""Hash-based extraction cache to avoid re-calling the LLM API."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from travel_itinerary.config import EXTRACTION_CACHE_PATH


class ExtractionCache:
    def __init__(self, path: Path = EXTRACTION_CACHE_PATH):
        self.path = path
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, email_hash: str) -> Optional[Dict[str, Any]]:
        return self._data.get(email_hash)

    def put(self, email_hash: str, extraction: Dict[str, Any]):
        self._data[email_hash] = extraction
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def __len__(self):
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data
