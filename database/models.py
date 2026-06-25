"""
LoreKeeper — Data models for articles, templates, and map entities.

All models are plain dataclasses so they stay decoupled from persistence logic.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def _json_serialise(obj: Any) -> str:
    """Serialise a Python object to a JSON string, handling sets and dataclasses."""
    def _default(o):
        if isinstance(o, set):
            return sorted(o)
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serialisable")
    return json.dumps(obj, default=_default, ensure_ascii=False)


def _json_deserialise(raw: str | None) -> Any:
    """Safely deserialise a JSON string, returning None on empty/null input."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Static list of built-in article types
# ---------------------------------------------------------------------------

BUILTIN_ARTICLE_TYPES = frozenset({
    "Location",
    "Character",
    "Faction",
    "Religion",
    "Event",
    "Species",
    "Item",
    "Creature",
    "Settlement",
    "Nation",
})


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------

@dataclass
class Article:
    """A single wiki article."""
    id: str = field(default_factory=_uuid)
    title: str = ""
    content: str = ""
    article_type: str = "Location"
    parent_id: Optional[str] = None
    template_fields: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    is_favorite: bool = False
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        """Convert to a flat dictionary suitable for SQLite INSERT/UPDATE."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "article_type": self.article_type,
            "parent_id": self.parent_id,
            "template_fields": _json_serialise(self.template_fields),
            "tags": _json_serialise(self.tags),
            "is_favorite": 1 if self.is_favorite else 0,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Article:
        """Build an Article from a raw SQLite row dict."""
        return cls(
            id=row["id"],
            title=row["title"],
            content=row.get("content", ""),
            article_type=row.get("article_type", "Location"),
            parent_id=row.get("parent_id"),
            template_fields=_json_deserialise(row.get("template_fields")) or {},
            tags=_json_deserialise(row.get("tags")) or [],
            is_favorite=bool(row.get("is_favorite", 0)),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def touch(self) -> None:
        """Update the 'updated_at' timestamp."""
        self.updated_at = _now()


# ---------------------------------------------------------------------------
# ArticleTemplate  (custom types)
# ---------------------------------------------------------------------------

@dataclass
class FieldDefinition:
    """A single field in a template schema."""
    name: str = ""
    label: str = ""
    field_type: str = "text"  # text, longtext, number, boolean, date, select
    required: bool = False
    options: list[str] = field(default_factory=list)  # for 'select' type
    placeholder: str = ""


@dataclass
class ArticleTemplate:
    """A custom article type definition (schema)."""
    id: str = field(default_factory=_uuid)
    type_name: str = ""
    field_definitions: list[FieldDefinition] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type_name": self.type_name,
            "field_definitions": _json_serialise(self.field_definitions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ArticleTemplate:
        raw_fields = _json_deserialise(row.get("field_definitions")) or []
        fields = [
            FieldDefinition(**fd) if isinstance(fd, dict) else fd
            for fd in raw_fields
        ]
        return cls(
            id=row["id"],
            type_name=row["type_name"],
            field_definitions=fields,
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def touch(self) -> None:
        self.updated_at = _now()


# ---------------------------------------------------------------------------
# MapNode
# ---------------------------------------------------------------------------

@dataclass
class MapNode:
    """A node on the interactive travel map, linked to an Article."""
    id: str = field(default_factory=_uuid)
    article_id: str = ""
    x: float = 0.0
    y: float = 0.0
    label_visible: bool = True
    created_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "x": self.x,
            "y": self.y,
            "label_visible": 1 if self.label_visible else 0,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MapNode:
        return cls(
            id=row["id"],
            article_id=row["article_id"],
            x=float(row.get("x", 0)),
            y=float(row.get("y", 0)),
            label_visible=bool(row.get("label_visible", 1)),
            created_at=row.get("created_at", ""),
        )


# ---------------------------------------------------------------------------
# MapConnection  (edges between map nodes)
# ---------------------------------------------------------------------------

@dataclass
class MapConnection:
    """Travel path between two MapNodes."""
    id: str = field(default_factory=_uuid)
    node_a_id: str = ""
    node_b_id: str = ""
    distance: float = 0.0          # km / miles
    travel_time: str = ""          # e.g. "3 days", "2 hours"
    terrain: str = ""              # e.g. "mountain", "forest", "plains"
    danger: str = "low"            # low / medium / high / extreme
    notes: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_a_id": self.node_a_id,
            "node_b_id": self.node_b_id,
            "distance": self.distance,
            "travel_time": self.travel_time,
            "terrain": self.terrain,
            "danger": self.danger,
            "notes": self.notes,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MapConnection:
        return cls(
            id=row["id"],
            node_a_id=row["node_a_id"],
            node_b_id=row["node_b_id"],
            distance=float(row.get("distance", 0)),
            travel_time=row.get("travel_time", ""),
            terrain=row.get("terrain", ""),
            danger=row.get("danger", "low"),
            notes=row.get("notes", ""),
        )