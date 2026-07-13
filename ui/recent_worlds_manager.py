"""
World Garden — RecentWorldsManager.

Manages the `recent_worlds.json` file in the user data directory.
Tracks display name, path, last_opened timestamp, and pinned status.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


def _user_data_dir() -> str:
    """Return the user data directory for World Garden."""
    data_dir = os.path.join(str(Path.home()), ".worldgarden")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    return data_dir


RECENT_WORLDS_PATH = os.path.join(_user_data_dir(), "recent_worlds.json")
MAX_RECENT_WORLDS = 20


@dataclass
class RecentWorldEntry:
    """A single entry in the recent worlds list."""

    name: str
    path: str
    last_opened: float = field(default_factory=time.time)
    pinned: bool = False


class RecentWorldsManager:
    """Manages the list of recently opened worlds, persisted to JSON."""

    def __init__(self) -> None:
        self._entries: list[RecentWorldEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_worlds(self) -> list[RecentWorldEntry]:
        """Return entries sorted: pinned first, then by last_opened descending."""
        return sorted(
            self._entries,
            key=lambda e: (0 if e.pinned else 1, -e.last_opened),
        )

    def add_world(self, name: str, path: str) -> None:
        """Add or update a world entry. Normalizes the path and deduplicates."""
        norm_path = str(Path(path).resolve())
        # Remove existing entry with same path
        self._entries = [e for e in self._entries if Path(e.path).resolve() != Path(norm_path).resolve()]
        entry = RecentWorldEntry(name=name, path=norm_path, last_opened=time.time())
        self._entries.insert(0, entry)
        # Trim to max
        if len(self._entries) > MAX_RECENT_WORLDS:
            self._entries = self._entries[:MAX_RECENT_WORLDS]
        self._save()

    def remove_world(self, path: str) -> None:
        """Remove an entry from the recent list by path."""
        norm_path = str(Path(path).resolve())
        self._entries = [e for e in self._entries if Path(e.path).resolve() != Path(norm_path).resolve()]
        self._save()

    def rename_world(self, path: str, new_name: str) -> None:
        """Update the display name for a world entry."""
        for entry in self._entries:
            if Path(entry.path).resolve() == Path(path).resolve():
                entry.name = new_name
                self._save()
                return

    def pin_world(self, path: str, pinned: bool = True) -> None:
        """Set the pinned status for a world entry."""
        for entry in self._entries:
            if Path(entry.path).resolve() == Path(path).resolve():
                entry.pinned = pinned
                self._save()
                return

    def touch_world(self, path: str) -> None:
        """Update the last_opened timestamp for a world."""
        for entry in self._entries:
            if Path(entry.path).resolve() == Path(path).resolve():
                entry.last_opened = time.time()
                self._save()
                return

    def world_exists(self, path: str) -> bool:
        """Check if a world path exists in the recent list."""
        norm_path = str(Path(path).resolve())
        return any(Path(e.path).resolve() == Path(norm_path).resolve() for e in self._entries)

    def contains_path(self, path: str) -> bool:
        """Check if a path string is already tracked (for legacy check)."""
        norm_path = str(Path(path).resolve())
        return any(Path(e.path).resolve() == Path(norm_path).resolve() for e in self._entries)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load entries from the JSON file."""
        if not os.path.isfile(RECENT_WORLDS_PATH):
            self._entries = []
            return
        try:
            with open(RECENT_WORLDS_PATH, "r") as f:
                data = json.load(f)
            self._entries = [RecentWorldEntry(**item) for item in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            self._entries = []

    def _save(self) -> None:
        """Persist entries to the JSON file."""
        Path(RECENT_WORLDS_PATH).parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._entries]
        with open(RECENT_WORLDS_PATH, "w") as f:
            json.dump(data, f, indent=2)
