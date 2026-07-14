"""
World Garden — Data models for articles, templates, and map entities.

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
    show_on_map: bool = False      # Display metadata label on the map

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
            "show_on_map": 1 if self.show_on_map else 0,
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
            show_on_map=bool(row.get("show_on_map", 0)),
        )


# ---------------------------------------------------------------------------
# Calendar models
# ---------------------------------------------------------------------------

@dataclass
class Calendar:
    """A calendar system definition."""
    id: str = field(default_factory=_uuid)
    name: str = ""
    description: str = ""
    epoch: str = ""
    days_in_week: int = 7
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "epoch": self.epoch,
            "days_in_week": self.days_in_week,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Calendar:
        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            epoch=row.get("epoch", ""),
            days_in_week=int(row.get("days_in_week", 7)),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )


@dataclass
class CalendarMonth:
    """A month in a calendar."""
    id: str = field(default_factory=_uuid)
    calendar_id: str = ""
    name: str = ""
    days: int = 30
    position: int = 0
    created_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calendar_id": self.calendar_id,
            "name": self.name,
            "days": self.days,
            "position": self.position,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> CalendarMonth:
        return cls(
            id=row["id"],
            calendar_id=row["calendar_id"],
            name=row["name"],
            days=int(row.get("days", 30)),
            position=int(row.get("position", 0)),
            created_at=row.get("created_at", ""),
        )


@dataclass
class CalendarWeekday:
    """A weekday in a calendar."""
    id: str = field(default_factory=_uuid)
    calendar_id: str = ""
    name: str = ""
    position: int = 0
    created_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calendar_id": self.calendar_id,
            "name": self.name,
            "position": self.position,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> CalendarWeekday:
        return cls(
            id=row["id"],
            calendar_id=row["calendar_id"],
            name=row["name"],
            position=int(row.get("position", 0)),
            created_at=row.get("created_at", ""),
        )


@dataclass
class CalendarEra:
    """An era within a calendar."""
    id: str = field(default_factory=_uuid)
    calendar_id: str = ""
    name: str = ""
    abbreviation: str = ""
    start_year: int = 1
    is_primary: bool = False
    created_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calendar_id": self.calendar_id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "start_year": self.start_year,
            "is_primary": 1 if self.is_primary else 0,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> CalendarEra:
        return cls(
            id=row["id"],
            calendar_id=row["calendar_id"],
            name=row["name"],
            abbreviation=row.get("abbreviation", ""),
            start_year=int(row.get("start_year", 1)),
            is_primary=bool(row.get("is_primary", 0)),
            created_at=row.get("created_at", ""),
        )


@dataclass
class LeapYearRule:
    """A rule defining when leap years occur."""
    id: str = field(default_factory=_uuid)
    calendar_id: str = ""
    rule_type: str = "interval"
    interval: int = 4
    offset: int = 0
    month: int = 2
    days_to_add: int = 1
    description: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calendar_id": self.calendar_id,
            "rule_type": self.rule_type,
            "interval": self.interval,
            "offset": self.offset,
            "month": self.month,
            "days_to_add": self.days_to_add,
            "description": self.description,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> LeapYearRule:
        return cls(
            id=row["id"],
            calendar_id=row["calendar_id"],
            rule_type=row.get("rule_type", "interval"),
            interval=int(row.get("interval", 4)),
            offset=int(row.get("offset", 0)),
            month=int(row.get("month", 2)),
            days_to_add=int(row.get("days_to_add", 1)),
            description=row.get("description", ""),
        )