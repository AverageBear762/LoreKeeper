"""
LoreKeeper — Offline local-first worldbuilding database.

Database layer providing:
- SQLite with WAL mode, FTS5 full-text search, foreign keys
- Dataclass models for Articles, Templates, MapNodes, MapConnections
- Full CRUD for all entities
- Schema creation and migration on startup
"""

from database.manager import DatabaseManager, get_db
from database.models import (
    Article,
    ArticleTemplate,
    BUILTIN_ARTICLE_TYPES,
    FieldDefinition,
    MapConnection,
    MapNode,
)
from database import crud

__all__ = [
    "DatabaseManager",
    "get_db",
    "Article",
    "ArticleTemplate",
    "BUILTIN_ARTICLE_TYPES",
    "FieldDefinition",
    "MapConnection",
    "MapNode",
    "crud",
]