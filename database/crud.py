"""
LoreKeeper — CRUD operations for articles, templates, and maps.

All functions accept / return model dataclass instances for clean
separation between persistence and business logic.

Uses DatabaseManager singleton for thread-safe connection access.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.manager import DatabaseManager
from database.models import (
    Article,
    ArticleTemplate,
    MapConnection,
    MapNode,
    _now,
)


# ======================================================================
#  ARTICLES
# ======================================================================

def create_article(article: Article) -> Article:
    """Insert a new article. Returns the article (with its id)."""
    db = DatabaseManager()
    db.execute(
        """
        INSERT INTO articles (id, title, content, article_type,
                              parent_id, template_fields, tags, is_favorite,
                              created_at, updated_at)
        VALUES (:id, :title, :content, :article_type,
                :parent_id, :template_fields, :tags, :is_favorite,
                :created_at, :updated_at)
        """,
        article.to_row(),
    )
    return article


def get_article(article_id: str) -> Optional[Article]:
    """Fetch a single article by id, or None."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    )
    return Article.from_row(dict(row)) if row else None


def get_article_by_title(title: str) -> Optional[Article]:
    """Fetch an article by its exact title (case-insensitive)."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM articles WHERE LOWER(title) = LOWER(?)", (title,)
    )
    return Article.from_row(dict(row)) if row else None


def update_article(article: Article) -> Article:
    """Update an existing article (matched by id). Touches updated_at."""
    article.touch()
    db = DatabaseManager()
    db.execute(
        """
        UPDATE articles SET
            title = :title,
            content = :content,
            article_type = :article_type,
            parent_id = :parent_id,
            template_fields = :template_fields,
            tags = :tags,
            is_favorite = :is_favorite,
            updated_at = :updated_at
        WHERE id = :id
        """,
        article.to_row(),
    )
    return article


def delete_article(article_id: str) -> bool:
    """Delete an article by id. Cascades to map nodes. Returns True if deleted."""
    cur = DatabaseManager().execute(
        "DELETE FROM articles WHERE id = ?", (article_id,)
    )
    return cur.rowcount > 0


def list_articles(
    article_type: Optional[str] = None,
    favorite_only: bool = False,
    tag: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_desc: bool = True,
    limit: int = 200,
    offset: int = 0,
) -> list[Article]:
    """List articles with optional filters.

    Args:
        article_type: Filter by type (e.g. "Character").
        favorite_only: Only show favorited articles.
        tag: Only show articles with this tag.
        sort_by: Column to sort by (title, created_at, updated_at, article_type).
        sort_desc: Descending order if True.
        limit: Max results.
        offset: Pagination offset.
    """
    allowed_sort = {"title", "created_at", "updated_at", "article_type"}
    sort_col = sort_by if sort_by in allowed_sort else "updated_at"
    order = "DESC" if sort_desc else "ASC"

    where_clauses: list[str] = []
    params: list[Any] = []

    if article_type:
        where_clauses.append("article_type = ?")
        params.append(article_type)
    if favorite_only:
        where_clauses.append("is_favorite = 1")
    if tag:
        where_clauses.append("tags LIKE ?")
        params.append(f"%\"{tag}\"%")

    where = ""
    if where_clauses:
        where = "WHERE " + " AND ".join(where_clauses)

    sql = f"SELECT * FROM articles {where} ORDER BY {sort_col} {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = DatabaseManager().fetchall(sql, tuple(params))
    return [Article.from_row(dict(r)) for r in rows]


def toggle_favorite(article_id: str) -> bool:
    """Toggle the favorite flag on an article. Returns the new state."""
    db = DatabaseManager()
    db.execute(
        """
        UPDATE articles
        SET is_favorite = CASE WHEN is_favorite = 0 THEN 1 ELSE 0 END,
            updated_at = ?
        WHERE id = ?
        """,
        (_now(), article_id),
    )
    row = db.fetchone("SELECT is_favorite FROM articles WHERE id = ?", (article_id,))
    return bool(row["is_favorite"]) if row else False


def search_articles(query: str, limit: int = 50) -> list[Article]:
    """Full-text search via FTS5. Returns matching articles ranked by relevance."""
    if not query.strip():
        return []

    try:
        rows = DatabaseManager().fetchall(
            """
            SELECT a.*
            FROM articles a
            JOIN articles_fts fts ON a.rowid = fts.rowid
            WHERE articles_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
    except sqlite3.OperationalError:
        # Fallback: LIKE search if FTS5 has an issue
        like = f"%{query}%"
        rows = DatabaseManager().fetchall(
            """
            SELECT * FROM articles
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (like, like, limit),
        )

    return [Article.from_row(dict(r)) for r in rows]


def list_child_articles(parent_id: str) -> list[Article]:
    """Return all articles whose parent_id matches the given id."""
    rows = DatabaseManager().fetchall(
        "SELECT * FROM articles WHERE parent_id = ? ORDER BY title",
        (parent_id,),
    )
    return [Article.from_row(dict(r)) for r in rows]


def get_article_hierarchy() -> list[tuple[Article, list[Article]]]:
    """Return (root_article, [child_articles]) pairs, sorted by type then title.

    Root articles are those with parent_id IS NULL.
    Children are fetched per root via list_child_articles().
    """
    rows = DatabaseManager().fetchall(
        "SELECT * FROM articles WHERE parent_id IS NULL "
        "ORDER BY article_type, title"
    )
    result: list[tuple[Article, list[Article]]] = []
    for r in rows:
        root = Article.from_row(dict(r))
        children = list_child_articles(root.id)
        result.append((root, children))
    return result


def set_article_parent(article_id: str, parent_id: str | None) -> None:
    """Set or clear the parent of an article."""
    DatabaseManager().execute(
        "UPDATE articles SET parent_id = ? WHERE id = ?",
        (parent_id, article_id),
    )


# ======================================================================
#  TEMPLATES
# ======================================================================

def create_template(template: ArticleTemplate) -> ArticleTemplate:
    """Insert a new custom article template."""
    DatabaseManager().execute(
        """
        INSERT INTO article_templates
            (id, type_name, field_definitions, created_at, updated_at)
        VALUES (:id, :type_name, :field_definitions, :created_at, :updated_at)
        """,
        template.to_row(),
    )
    return template


def get_template(template_id: str) -> Optional[ArticleTemplate]:
    """Fetch a single template by id."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM article_templates WHERE id = ?", (template_id,)
    )
    return ArticleTemplate.from_row(dict(row)) if row else None


def get_template_by_type_name(type_name: str) -> Optional[ArticleTemplate]:
    """Fetch a template by its type name (e.g. \"Spell\")."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM article_templates WHERE type_name = ?", (type_name,)
    )
    return ArticleTemplate.from_row(dict(row)) if row else None


def list_all_article_types() -> list[str]:
    """Return all available article types: built-in + custom, deduplicated."""
    from database.models import BUILTIN_ARTICLE_TYPES
    custom = DatabaseManager().fetchall(
        "SELECT type_name FROM article_templates ORDER BY type_name"
    )
    custom_names = [r["type_name"] for r in custom]
    # Merge — custom templates override built-in if they share a name
    seen: set[str] = set()
    result: list[str] = []
    for name in sorted(BUILTIN_ARTICLE_TYPES) + custom_names:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def update_template(template: ArticleTemplate) -> ArticleTemplate:
    """Update an existing template."""
    template.touch()
    DatabaseManager().execute(
        """
        UPDATE article_templates SET
            type_name = :type_name,
            field_definitions = :field_definitions,
            updated_at = :updated_at
        WHERE id = :id
        """,
        template.to_row(),
    )
    return template


def delete_template(template_id: str) -> bool:
    """Delete a template by id."""
    cur = DatabaseManager().execute(
        "DELETE FROM article_templates WHERE id = ?", (template_id,)
    )
    return cur.rowcount > 0


# ======================================================================
#  MAP NODES
# ======================================================================

def create_map_node(node: MapNode) -> MapNode:
    """Insert a new map node."""
    DatabaseManager().execute(
        """
        INSERT INTO map_nodes (id, article_id, x, y, label_visible, created_at)
        VALUES (:id, :article_id, :x, :y, :label_visible, :created_at)
        """,
        node.to_row(),
    )
    return node


def get_map_node(node_id: str) -> Optional[MapNode]:
    """Fetch a map node by id."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM map_nodes WHERE id = ?", (node_id,)
    )
    return MapNode.from_row(dict(row)) if row else None


def get_map_node_by_article(article_id: str) -> Optional[MapNode]:
    """Fetch the map node associated with an article (or None)."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM map_nodes WHERE article_id = ?", (article_id,)
    )
    return MapNode.from_row(dict(row)) if row else None


def update_map_node(node: MapNode) -> MapNode:
    """Update an existing map node (position, label visibility)."""
    DatabaseManager().execute(
        """
        UPDATE map_nodes SET
            x = :x, y = :y, label_visible = :label_visible
        WHERE id = :id
        """,
        node.to_row(),
    )
    return node


def delete_map_node(node_id: str) -> bool:
    """Delete a map node and its connections. Cascades to connections."""
    cur = DatabaseManager().execute(
        "DELETE FROM map_nodes WHERE id = ?", (node_id,)
    )
    return cur.rowcount > 0


def list_all_map_nodes() -> list[MapNode]:
    """Return every map node (used for rendering the full map)."""
    rows = DatabaseManager().fetchall("SELECT * FROM map_nodes ORDER BY created_at")
    return [MapNode.from_row(dict(r)) for r in rows]


def update_node_position(node_id: str, x: float, y: float) -> None:
    """Quickly update just the position of a node (for drag events)."""
    DatabaseManager().execute(
        "UPDATE map_nodes SET x = ?, y = ? WHERE id = ?",
        (x, y, node_id),
    )


# ======================================================================
#  MAP CONNECTIONS
# ======================================================================

def create_map_connection(connection: MapConnection) -> MapConnection:
    """Insert a new map connection (travel path)."""
    DatabaseManager().execute(
        """
        INSERT INTO map_connections
            (id, node_a_id, node_b_id, distance, travel_time,
             terrain, danger, notes)
        VALUES (:id, :node_a_id, :node_b_id, :distance, :travel_time,
                :terrain, :danger, :notes)
        """,
        connection.to_row(),
    )
    return connection


def get_map_connection(connection_id: str) -> Optional[MapConnection]:
    """Fetch a single connection by id."""
    row = DatabaseManager().fetchone(
        "SELECT * FROM map_connections WHERE id = ?", (connection_id,)
    )
    return MapConnection.from_row(dict(row)) if row else None


def update_map_connection(connection: MapConnection) -> MapConnection:
    """Update an existing connection."""
    DatabaseManager().execute(
        """
        UPDATE map_connections SET
            distance = :distance,
            travel_time = :travel_time,
            terrain = :terrain,
            danger = :danger,
            notes = :notes
        WHERE id = :id
        """,
        connection.to_row(),
    )
    return connection


def delete_map_connection(connection_id: str) -> bool:
    """Delete a connection by id."""
    cur = DatabaseManager().execute(
        "DELETE FROM map_connections WHERE id = ?", (connection_id,)
    )
    return cur.rowcount > 0


def list_connections_for_node(node_id: str) -> list[MapConnection]:
    """Return all connections originating from or ending at a specific node."""
    rows = DatabaseManager().fetchall(
        """
        SELECT * FROM map_connections
        WHERE node_a_id = ? OR node_b_id = ?
        ORDER BY distance
        """,
        (node_id, node_id),
    )
    return [MapConnection.from_row(dict(r)) for r in rows]


def list_all_connections() -> list[MapConnection]:
    """Return every map connection."""
    rows = DatabaseManager().fetchall(
        "SELECT * FROM map_connections ORDER BY distance"
    )
    return [MapConnection.from_row(dict(r)) for r in rows]


# ======================================================================
#  Convenience: fetch full map graph (nodes + connections)
# ======================================================================

def get_full_map_data() -> tuple[list[MapNode], list[MapConnection]]:
    """Return (nodes, connections) for the full travel map."""
    return list_all_map_nodes(), list_all_connections()