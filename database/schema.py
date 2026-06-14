"""
LoreKeeper — SQLite schema definitions and migration.

Uses a simple schema version table to track migrations.
On startup, the database creates all tables if they don't exist
and runs any pending migrations in order.
"""

from __future__ import annotations

import sqlite3
from typing import Any

# ---------------------------------------------------------------------------
# Schema version tracking
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1  # bump when adding new migrations

CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

CREATE_ARTICLES = """
CREATE TABLE IF NOT EXISTS articles (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    article_type TEXT NOT NULL DEFAULT 'Location',
    template_fields TEXT NOT NULL DEFAULT '{}',
    tags        TEXT NOT NULL DEFAULT '[]',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

CREATE_ARTICLE_TEMPLATES = """
CREATE TABLE IF NOT EXISTS article_templates (
    id                TEXT PRIMARY KEY,
    type_name         TEXT NOT NULL UNIQUE,
    field_definitions TEXT NOT NULL DEFAULT '[]',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
"""

CREATE_MAP_NODES = """
CREATE TABLE IF NOT EXISTS map_nodes (
    id           TEXT PRIMARY KEY,
    article_id   TEXT NOT NULL,
    x            REAL NOT NULL DEFAULT 0.0,
    y            REAL NOT NULL DEFAULT 0.0,
    label_visible INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);
"""

CREATE_MAP_CONNECTIONS = """
CREATE TABLE IF NOT EXISTS map_connections (
    id         TEXT PRIMARY KEY,
    node_a_id  TEXT NOT NULL,
    node_b_id  TEXT NOT NULL,
    distance   REAL NOT NULL DEFAULT 0.0,
    travel_time TEXT NOT NULL DEFAULT '',
    terrain    TEXT NOT NULL DEFAULT '',
    danger     TEXT NOT NULL DEFAULT 'low',
    notes      TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (node_a_id) REFERENCES map_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (node_b_id) REFERENCES map_nodes(id) ON DELETE CASCADE
);
"""

# ---------------------------------------------------------------------------
# FTS5 virtual table (full-text search)
# ---------------------------------------------------------------------------

CREATE_ARTICLES_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title,
    content,
    content='articles',
    content_rowid='rowid',
    tokenize='porter unicode61'
);
"""

# ---------------------------------------------------------------------------
# Indexes for common queries
# ---------------------------------------------------------------------------

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_articles_type ON articles(article_type);",
    "CREATE INDEX IF NOT EXISTS idx_articles_favorite ON articles(is_favorite);",
    "CREATE INDEX IF NOT EXISTS idx_articles_updated ON articles(updated_at);",
    "CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_map_nodes_article ON map_nodes(article_id);",
    "CREATE INDEX IF NOT EXISTS idx_map_connections_a ON map_connections(node_a_id);",
    "CREATE INDEX IF NOT EXISTS idx_map_connections_b ON map_connections(node_b_id);",
]

# ---------------------------------------------------------------------------
# Triggers to keep FTS in sync
# ---------------------------------------------------------------------------

FTS_SYNC_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
        INSERT INTO articles_fts(rowid, title, content)
        VALUES (new.rowid, new.title, new.content);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
        INSERT INTO articles_fts(articles_fts, rowid, title, content)
        VALUES ('delete', old.rowid, old.title, old.content);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles
    WHEN old.title != new.title OR old.content != new.content
    BEGIN
        INSERT INTO articles_fts(articles_fts, rowid, title, content)
        VALUES ('delete', old.rowid, old.title, old.content);
        INSERT INTO articles_fts(rowid, title, content)
        VALUES (new.rowid, new.title, new.content);
    END;
    """,
]

# ---------------------------------------------------------------------------
# Populate FTS from existing articles (run after table creation / migration)
# ---------------------------------------------------------------------------

REBUILD_FTS = "INSERT INTO articles_fts(articles_fts) VALUES('rebuild');"


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------

def create_all_tables(conn: sqlite3.Connection) -> None:
    """Create all tables, indexes, triggers if they don't exist yet."""
    conn.executescript(CREATE_SCHEMA_VERSION)
    conn.executescript(CREATE_ARTICLES)
    conn.executescript(CREATE_ARTICLE_TEMPLATES)
    conn.executescript(CREATE_MAP_NODES)
    conn.executescript(CREATE_MAP_CONNECTIONS)

    # FTS table
    conn.execute(CREATE_ARTICLES_FTS)

    for idx in CREATE_INDEXES:
        conn.execute(idx)

    for trig in FTS_SYNC_TRIGGERS:
        conn.executescript(trig)

    conn.execute(REBUILD_FTS)
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if not initialised."""
    try:
        cur = conn.execute("SELECT COALESCE(MAX(version), 0) FROM _schema_version")
        return cur.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Record that a schema version has been applied."""
    conn.execute(
        "INSERT INTO _schema_version (version) VALUES (?)",
        (version,),
    )
    conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    """Run all pending migrations to bring the DB up to SCHEMA_VERSION."""
    current = get_schema_version(conn)

    if current == 0:
        # Fresh install — create everything
        create_all_tables(conn)
        set_schema_version(conn, SCHEMA_VERSION)
        return

    # Future migrations go here:
    # if current < 2:
    #     _migrate_v2(conn)
    #     set_schema_version(conn, 2)
    # if current < 3:
    #     ...

    # If we already match, ensure at least all tables exist
    if current >= SCHEMA_VERSION:
        return

    create_all_tables(conn)
    set_schema_version(conn, SCHEMA_VERSION)