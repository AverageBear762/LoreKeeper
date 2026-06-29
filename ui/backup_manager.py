"""
World Garden — Backup Manager.

Provides:
- Full JSON snapshot export (all articles, templates, map data)
- JSON snapshot import (restore from JSON)
- Database file backup (live backup via SQLite backup API)
- Automatic backup scheduling
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from database import crud
from database.manager import DatabaseManager
from database.models import (
    Article,
    ArticleTemplate,
    MapConnection,
    MapNode,
    _now,
)


class BackupManager:
    """Manages database backups and JSON snapshots."""

    def __init__(self) -> None:
        self._auto_backup_timer: Optional[QTimer] = None

    # ----------------------------------------------------------------
    # JSON Export (full snapshot)
    # ----------------------------------------------------------------

    def export_json(self, filepath: str) -> bool:
        """Export all data as a JSON file. Returns True on success."""
        try:
            data = self._build_snapshot()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except (OSError, Exception) as e:
            raise RuntimeError(f"Export failed: {e}")

    def _build_snapshot(self) -> dict[str, Any]:
        """Build a complete data snapshot dictionary."""
        articles = crud.list_articles(limit=99999)
        templates_raw = DatabaseManager().fetchall(
            "SELECT * FROM article_templates ORDER BY type_name"
        )
        nodes, connections = crud.get_full_map_data()

        return {
            "lorekeeper_version": "0.1.0",
            "exported_at": _now(),
            "stats": {
                "articles": len(articles),
                "templates": len(templates_raw),
                "map_nodes": len(nodes),
                "map_connections": len(connections),
            },
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "content": a.content,
                    "article_type": a.article_type,
                    "template_fields": a.template_fields,
                    "tags": a.tags,
                    "is_favorite": a.is_favorite,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                }
                for a in articles
            ],
            "templates": [
                {
                    "id": r["id"],
                    "type_name": r["type_name"],
                    "field_definitions": json.loads(r["field_definitions"] or "[]"),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in templates_raw
            ],
            "map_nodes": [
                {
                    "id": n.id,
                    "article_id": n.article_id,
                    "x": n.x,
                    "y": n.y,
                    "label_visible": n.label_visible,
                }
                for n in nodes
            ],
            "map_connections": [
                {
                    "id": c.id,
                    "node_a_id": c.node_a_id,
                    "node_b_id": c.node_b_id,
                    "distance": c.distance,
                    "travel_time": c.travel_time,
                    "terrain": c.terrain,
                    "danger": c.danger,
                    "notes": c.notes,
                }
                for c in connections
            ],
        }

    # ----------------------------------------------------------------
    # JSON Import (restore from snapshot)
    # ----------------------------------------------------------------

    def import_json(self, filepath: str, merge: bool = True) -> dict[str, int]:
        """Import data from a JSON snapshot file.

        Args:
            filepath: Path to the JSON file.
            merge: If True, merge with existing data (skip duplicates).
                   If False, clear all data before importing (NOT IMPLEMENTED).

        Returns:
            Dict of counts: articles, templates, nodes, connections.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        counts = {"articles": 0, "templates": 0, "nodes": 0, "connections": 0}

        # Import templates
        for tdata in data.get("templates", []):
            existing = crud.get_template(tdata["id"])
            if not existing and not crud.get_template_by_type_name(tdata["type_name"]):
                fields = [
                    crud.FieldDefinition(**fd) if isinstance(fd, dict) else fd
                    for fd in tdata.get("field_definitions", [])
                ]
                template = ArticleTemplate(
                    id=tdata["id"],
                    type_name=tdata["type_name"],
                    field_definitions=fields,
                    created_at=tdata.get("created_at", _now()),
                    updated_at=tdata.get("updated_at", _now()),
                )
                crud.create_template(template)
                counts["templates"] += 1

        # Import articles
        for adata in data.get("articles", []):
            existing = crud.get_article(adata["id"])
            if not existing and not crud.get_article_by_title(adata["title"]):
                article = Article(
                    id=adata["id"],
                    title=adata["title"],
                    content=adata.get("content", ""),
                    article_type=adata.get("article_type", "Location"),
                    template_fields=adata.get("template_fields", {}),
                    tags=adata.get("tags", []),
                    is_favorite=adata.get("is_favorite", False),
                    created_at=adata.get("created_at", _now()),
                    updated_at=adata.get("updated_at", _now()),
                )
                crud.create_article(article)
                counts["articles"] += 1

        # Import map nodes (must exist after articles)
        ndata = data.get("map_nodes", [])
        for nd in ndata:
            existing = crud.get_map_node(nd["id"])
            if not existing and crud.get_article(nd["article_id"]):
                node = MapNode(
                    id=nd["id"],
                    article_id=nd["article_id"],
                    x=nd.get("x", 0),
                    y=nd.get("y", 0),
                    label_visible=nd.get("label_visible", True),
                )
                crud.create_map_node(node)
                counts["nodes"] += 1

        # Import connections
        for cd in data.get("map_connections", []):
            existing = crud.get_map_connection(cd["id"])
            if not existing:
                conn = MapConnection(
                    id=cd["id"],
                    node_a_id=cd["node_a_id"],
                    node_b_id=cd["node_b_id"],
                    distance=cd.get("distance", 0),
                    travel_time=cd.get("travel_time", ""),
                    terrain=cd.get("terrain", ""),
                    danger=cd.get("danger", "low"),
                    notes=cd.get("notes", ""),
                )
                crud.create_map_connection(conn)
                counts["connections"] += 1

        return counts

    # ----------------------------------------------------------------
    # Database backup (file-level)
    # ----------------------------------------------------------------

    def backup_database(self, target_path: str) -> bool:
        """Create a live backup of the current SQLite database."""
        db = DatabaseManager()
        if db.db_path is None:
            raise RuntimeError("No database is open")
        db.backup_to(target_path)
        return True

    def create_timestamped_backup(self, backup_dir: str) -> str:
        """Create a timestamped backup file in *backup_dir*.

        Returns the path to the backup file.
        """
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"lorekeeper_backup_{timestamp}.db")
        self.backup_database(backup_path)
        return backup_path


# ----------------------------------------------------------------
# Convenience dialog functions
# ----------------------------------------------------------------

def export_json_dialog(parent_widget) -> bool:
    """Show a save dialog and export JSON. Returns True on success."""
    path, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "Export JSON Snapshot",
        f"lorekeeper_export_{datetime.now().strftime('%Y%m%d')}.json",
        "JSON (*.json);;All Files (*)",
    )
    if not path:
        return False
    try:
        mgr = BackupManager()
        mgr.export_json(path)
        QMessageBox.information(parent_widget, "Export", f"Exported to:\n{path}")
        return True
    except Exception as e:
        QMessageBox.critical(parent_widget, "Export Error", str(e))
        return False


def import_json_dialog(parent_widget) -> bool:
    """Show an open dialog and import JSON. Returns True on success."""
    path, _ = QFileDialog.getOpenFileName(
        parent_widget,
        "Import JSON Snapshot",
        "",
        "JSON (*.json);;All Files (*)",
    )
    if not path:
        return False
    try:
        mgr = BackupManager()
        counts = mgr.import_json(path)
        QMessageBox.information(
            parent_widget, "Import Complete",
            f"Imported:\n"
            f"  {counts['articles']} articles\n"
            f"  {counts['templates']} templates\n"
            f"  {counts['nodes']} map nodes\n"
            f"  {counts['connections']} connections",
        )
        return True
    except Exception as e:
        QMessageBox.critical(parent_widget, "Import Error", str(e))
        return False


def backup_database_dialog(parent_widget) -> bool:
    """Show a save dialog and create DB backup. Returns True on success."""
    path, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "Backup Database",
        f"lorekeeper_backup_{datetime.now().strftime('%Y%m%d')}.db",
        "SQLite Database (*.db);;All Files (*)",
    )
    if not path:
        return False
    try:
        mgr = BackupManager()
        mgr.backup_database(path)
        QMessageBox.information(parent_widget, "Backup", f"Database backed up to:\n{path}")
        return True
    except Exception as e:
        QMessageBox.critical(parent_widget, "Backup Error", str(e))
        return False