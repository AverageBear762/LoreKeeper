"""
World Garden — DatabaseManager.

Singleton-style class that manages the SQLite connection, enables WAL mode,
enforces foreign keys, and runs schema migrations on startup.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional


class DatabaseManager:
    """
    Thread-safe database manager for World Garden.

    Usage::

        db = DatabaseManager()
        db.open("path/to/lorekeeper.db")
        # ... use db.conn / db.execute(...)
        db.close()

    The manager is a singleton by design — call ``DatabaseManager()``
    anywhere and the same connection (per thread) is returned.
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "DatabaseManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialised"):
            return
        self._initialised = True
        self._conn: Optional[sqlite3.Connection] = None
        self._conn_lock = threading.Lock()
        self._db_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def open(self, db_path: str | Path, migrate: bool = True) -> None:
        """Open (or create) the SQLite database at *db_path*.

        Args:
            db_path: Filesystem path for the SQLite database file, or
                     ``":memory:"`` for an in-memory database.
            migrate: Run schema migrations on open (default True).

        Safe to call multiple times — closes any existing connection first.
        """
        # Close any existing connection before opening a new one
        self.close()

        # Preserve the literal ":memory:" string — do NOT resolve it to a file.
        if isinstance(db_path, str) and db_path.strip() == ":memory:":
            resolved = ":memory:"
        else:
            resolved = str(Path(db_path).resolve())
        self._db_path = resolved
        conn = sqlite3.connect(
            resolved,
            check_same_thread=False,   # we protect with _conn_lock
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None,      # autocommit mode for WAL
        )

        # Performance & integrity pragmas
        conn.execute("PRAGMA journal_mode=WAL;")           # Write-Ahead Logging
        conn.execute("PRAGMA foreign_keys=ON;")             # Enforce FK constraints
        conn.execute("PRAGMA busy_timeout=5000;")           # Wait up to 5s on lock
        conn.execute("PRAGMA synchronous=NORMAL;")          # Balance perf/safety
        conn.execute("PRAGMA cache_size=-8000;")            # ~8 MB cache
        conn.execute("PRAGMA temp_store=MEMORY;")           # Temp tables in memory
        conn.row_factory = sqlite3.Row                      # Named column access

        self._conn = conn

        if migrate:
            from database.schema import migrate as run_migrate
            run_migrate(conn)

    @property
    def conn(self) -> sqlite3.Connection:
        """Return the active connection (raises if not opened)."""
        if self._conn is None:
            raise RuntimeError(
                "DatabaseManager not opened. Call .open(path) first."
            )
        return self._conn

    def close(self) -> None:
        """Close the database connection cleanly."""
        with self._conn_lock:
            if self._conn is not None:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> sqlite3.Cursor:
        """Execute a single SQL statement with optional parameters."""
        with self._conn_lock:
            if params is None:
                return self.conn.execute(sql)
            return self.conn.execute(sql, params)

    def executemany(
        self,
        sql: str,
        seq: list[tuple[Any, ...] | dict[str, Any]],
    ) -> sqlite3.Cursor:
        """Execute the same SQL for every item in *seq*."""
        with self._conn_lock:
            return self.conn.executemany(sql, seq)

    def fetchone(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> Optional[sqlite3.Row]:
        """Execute and return a single row (or None)."""
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> list[sqlite3.Row]:
        """Execute and return all matching rows."""
        cur = self.execute(sql, params)
        return cur.fetchall()

    def commit(self) -> None:
        """Explicit commit (needed if isolation_level is DEFERRED)."""
        with self._conn_lock:
            self.conn.commit()

    # ------------------------------------------------------------------
    # Backup / export helpers
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Optional[str]:
        """Path to the open database file, or None."""
        return self._db_path

    def backup_to(self, target_path: str | Path) -> None:
        """Create a live backup of the current database to *target_path*."""
        target = sqlite3.connect(str(target_path))
        with self._conn_lock:
            self.conn.backup(target, pages=100, progress=None)
        target.close()

    @staticmethod
    def default_db_path() -> str:
        """Return a sensible default DB path inside the user's data dir."""
        try:
            import appdirs
            data_dir = appdirs.user_data_dir("World Garden", "World Garden")
        except ImportError:
            data_dir = os.path.join(str(Path.home()), ".lorekeeper")
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(data_dir, "lorekeeper.db")


# Convenience alias
get_db = DatabaseManager