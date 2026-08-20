"""Gedaechtnis ueber Laeufe hinweg: welches Angebot wurde wann zuerst gesehen.

Ohne das laesst sich "neu" nicht bestimmen - die Portale liefern zwar teils
eigene Zeitstempel, aber nur diese Datei weiss, was seit *deinem* letzten Lauf
dazugekommen ist.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Dict, Optional

DEFAULT_PATH = "seen.json"


class Seen:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.entries: Dict[str, str] = {}
        self.runs: int = 0
        self.last_run: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (ValueError, OSError):
            return
        self.entries = data.get("entries") or {}
        self.runs = data.get("runs") or 0
        self.last_run = data.get("last_run")

    @property
    def is_first_run(self) -> bool:
        """Beim allerersten Lauf waere sonst der ganze Bestand "neu"."""
        return not self.entries

    @staticmethod
    def key(source: str, listing_id: str) -> str:
        return "%s:%s" % (source, listing_id)

    def first_seen(self, source: str, listing_id: str) -> Optional[str]:
        return self.entries.get(self.key(source, listing_id))

    def mark(self, source: str, listing_id: str, when: Optional[str] = None) -> bool:
        """Traegt ein Angebot ein. True, wenn es vorher unbekannt war."""
        key = self.key(source, listing_id)
        if key in self.entries:
            return False
        self.entries[key] = when or date.today().isoformat()
        return True

    def save(self) -> None:
        payload = {
            "runs": self.runs + 1,
            "last_run": datetime.now().isoformat(timespec="seconds"),
            "entries": self.entries,
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1, sort_keys=True)
