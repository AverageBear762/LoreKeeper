#!/usr/bin/env python3
"""
Comprehensive test suite for World Garden database layer.

Tests schema creation, CRUD operations, FTS5 search, map relationships,
and data integrity constraints (foreign keys, cascading deletes).
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.manager import DatabaseManager
from database.models import (
    Article,
    ArticleTemplate,
    BUILTIN_ARTICLE_TYPES,
    FieldDefinition,
    MapNode,
    MapConnection,
)
from database import crud


# ======================================================================
#  Test lifecycle — one in-memory DB for the whole suite
#  plus a separate file-persistence test.
# ======================================================================

def setup_module():
    """Initialise the shared in-memory database once."""
    db = DatabaseManager()
    # Force a fresh singleton
    DatabaseManager._instance = None
    db = DatabaseManager()
    db.open(":memory:")


def test_builtin_types():
    """Verify builtin article type list."""
    assert "Location" in BUILTIN_ARTICLE_TYPES
    assert "Character" in BUILTIN_ARTICLE_TYPES
    assert "Faction" in BUILTIN_ARTICLE_TYPES
    assert "Religion" in BUILTIN_ARTICLE_TYPES
    assert "Event" in BUILTIN_ARTICLE_TYPES
    assert "Species" in BUILTIN_ARTICLE_TYPES
    assert "Item" in BUILTIN_ARTICLE_TYPES
    assert "Creature" in BUILTIN_ARTICLE_TYPES
    assert "Settlement" in BUILTIN_ARTICLE_TYPES
    assert "Nation" in BUILTIN_ARTICLE_TYPES
    assert len(BUILTIN_ARTICLE_TYPES) == 10
    print(f"[PASS] {len(BUILTIN_ARTICLE_TYPES)} builtin article types defined.")


def test_create_and_get_article():
    """Create an article, fetch it, verify fields."""
    article = Article(
        title="King Aldric",
        content="The **wise** ruler of Avalon.",
        article_type="Character",
        tags=["ruler", "human", "noble"],
        is_favorite=True,
    )
    article.template_fields = {"age": 45, "realm": "Avalon"}

    created = crud.create_article(article)
    assert created.id == article.id
    print(f"[PASS] Created article: {created.title} (id={created.id[:8]}...)")

    # Fetch by id
    fetched = crud.get_article(article.id)
    assert fetched is not None
    assert fetched.title == "King Aldric"
    assert fetched.article_type == "Character"
    assert fetched.is_favorite == True
    assert "ruler" in fetched.tags
    assert fetched.template_fields["age"] == 45
    print(f"[PASS] Fetched article by id — all fields match.")

    # Fetch by title
    by_title = crud.get_article_by_title("king aldric")
    assert by_title is not None
    assert by_title.id == article.id
    print(f"[PASS] Fetched article by title (case-insensitive).")


def test_update_article():
    """Update an article and verify changes."""
    article = Article(title="Old Name", content="Old content.")
    crud.create_article(article)

    article.title = "New Name"
    article.content = "Updated content."
    article.is_favorite = True
    article.tags = ["updated"]

    crud.update_article(article)
    fetched = crud.get_article(article.id)

    assert fetched.title == "New Name"
    assert fetched.content == "Updated content."
    assert fetched.is_favorite == True
    assert fetched.tags == ["updated"]
    assert fetched.updated_at != fetched.created_at
    print(f"[PASS] Updated article — all fields persisted.")


def test_delete_article():
    """Delete an article and confirm it's gone."""
    article = Article(title="Temp Article")
    crud.create_article(article)
    deleted = crud.delete_article(article.id)
    assert deleted == True
    assert crud.get_article(article.id) is None
    # Double-delete should return False
    assert crud.delete_article(article.id) == False
    print(f"[PASS] Deleted article successfully.")


def test_list_articles():
    """Create several articles and test list/filter."""
    titles = [f"Test Article {i}" for i in range(5)]
    for idx, title in enumerate(titles):
        a = Article(title=title, article_type="Location")
        if idx < 3:
            a.article_type = "Character"
        if idx == 0:
            a.tags = ["important"]
            a.is_favorite = True
        crud.create_article(a)

    # List all
    all_arts = crud.list_articles(limit=100)
    assert len(all_arts) >= 5
    print(f"[PASS] list_articles returns {len(all_arts)} articles.")

    # Filter by type
    chars = crud.list_articles(article_type="Character", limit=100)
    assert len(chars) >= 3
    print(f"[PASS] Filtered by article_type='Character' -> {len(chars)}.")

    # Filter by favorite
    favs = crud.list_articles(favorite_only=True, limit=100)
    assert len(favs) >= 1
    print(f"[PASS] Filtered by favorite_only -> {len(favs)}.")


def test_toggle_favorite():
    """Toggle the favorite flag."""
    article = Article(title="Fav Test")
    crud.create_article(article)
    new_state = crud.toggle_favorite(article.id)
    assert new_state == True
    new_state = crud.toggle_favorite(article.id)
    assert new_state == False
    print(f"[PASS] Toggle favorite works correctly.")


def test_full_text_search():
    """Create articles and test FTS5 search."""
    crud.create_article(Article(
        title="Avalon Castle",
        content="The grand castle in the heart of Avalon.",
        tags=["castle"],
    ))
    crud.create_article(Article(
        title="Dark Forest",
        content="A dangerous forest filled with shadows.",
        tags=["forest"],
    ))
    crud.create_article(Article(
        title="King Aldric's Throne",
        content="The throne of King Aldric in Avalon Castle.",
    ))

    results = crud.search_articles("Avalon")
    assert len(results) >= 2
    print(f"[PASS] FTS5 search 'Avalon' returned {len(results)} results.")

    results = crud.search_articles("castle throne")
    assert len(results) >= 1
    print(f"[PASS] FTS5 search 'castle throne' returned {len(results)} results.")

    results = crud.search_articles("nonexistent_xyz")
    assert len(results) == 0
    print(f"[PASS] FTS5 search for non-existent term returns empty.")


def test_article_templates():
    """Test custom template CRUD."""
    template = ArticleTemplate(
        type_name="Spell",
        field_definitions=[
            FieldDefinition(
                name="school", label="School of Magic",
                field_type="select",
                options=["Evocation", "Necromancy", "Divination"],
            ),
            FieldDefinition(
                name="level", label="Spell Level", field_type="number",
            ),
            FieldDefinition(
                name="ritual", label="Ritual", field_type="boolean",
            ),
        ],
    )
    crud.create_template(template)
    print(f"[PASS] Created template: {template.type_name}")

    fetched = crud.get_template(template.id)
    assert fetched is not None
    assert fetched.type_name == "Spell"
    assert len(fetched.field_definitions) == 3
    assert fetched.field_definitions[0].field_type == "select"
    print(f"[PASS] Fetched template — {len(fetched.field_definitions)} field definitions.")

    by_name = crud.get_template_by_type_name("Spell")
    assert by_name is not None
    print(f"[PASS] Fetched template by type_name.")

    # List all types (should include builtins + custom)
    all_types = crud.list_all_article_types()
    assert "Spell" in all_types
    assert "Location" in all_types
    print(f"[PASS] list_all_article_types includes builtins + custom ({len(all_types)} total).")

    # Update
    template.type_name = "Arcane Spell"
    crud.update_template(template)
    fetched2 = crud.get_template(template.id)
    assert fetched2.type_name == "Arcane Spell"
    print(f"[PASS] Updated template type_name.")

    # Delete
    crud.delete_template(template.id)
    assert crud.get_template(template.id) is None
    print(f"[PASS] Deleted template.")


def test_map_nodes():
    """Test map node CRUD and article linkage."""
    article = Article(title="Avalon", article_type="Location")
    crud.create_article(article)

    node = MapNode(article_id=article.id, x=150.0, y=300.0, label_visible=True)
    crud.create_map_node(node)
    print(f"[PASS] Created map node at ({node.x}, {node.y}).")

    # Fetch by id
    fetched = crud.get_map_node(node.id)
    assert fetched is not None
    assert fetched.article_id == article.id
    assert fetched.x == 150.0
    print(f"[PASS] Fetched map node by id.")

    # Fetch by article
    by_article = crud.get_map_node_by_article(article.id)
    assert by_article is not None
    assert by_article.id == node.id
    print(f"[PASS] Fetched map node by article_id.")

    # Update position
    node.x = 200.0
    node.y = 400.0
    crud.update_map_node(node)
    fetched2 = crud.get_map_node(node.id)
    assert fetched2.x == 200.0
    assert fetched2.y == 400.0
    print(f"[PASS] Updated map node position.")

    # Quick position update
    crud.update_node_position(node.id, 500.0, 600.0)
    fetched3 = crud.get_map_node(node.id)
    assert fetched3.x == 500.0
    print(f"[PASS] Quick position update.")

    # List all nodes
    all_nodes = crud.list_all_map_nodes()
    assert len(all_nodes) >= 1
    print(f"[PASS] list_all_map_nodes -> {len(all_nodes)} nodes.")


def test_map_connections():
    """Test map connection CRUD with node relationships."""
    art1 = Article(title="Avalon", article_type="Location")
    art2 = Article(title="Darkwood", article_type="Location")
    crud.create_article(art1)
    crud.create_article(art2)

    node1 = MapNode(article_id=art1.id, x=0, y=0)
    node2 = MapNode(article_id=art2.id, x=100, y=100)
    crud.create_map_node(node1)
    crud.create_map_node(node2)

    conn = MapConnection(
        node_a_id=node1.id,
        node_b_id=node2.id,
        distance=50.0,
        travel_time="2 days",
        terrain="forest",
        danger="medium",
        notes="Watch for bandits.",
    )
    crud.create_map_connection(conn)
    print(f"[PASS] Created map connection ({conn.distance} units).")

    # Fetch
    fetched = crud.get_map_connection(conn.id)
    assert fetched is not None
    assert fetched.distance == 50.0
    assert fetched.terrain == "forest"
    assert fetched.danger == "medium"
    print(f"[PASS] Fetched map connection.")

    # Update
    conn.distance = 75.0
    conn.danger = "high"
    crud.update_map_connection(conn)
    fetched2 = crud.get_map_connection(conn.id)
    assert fetched2.distance == 75.0
    assert fetched2.danger == "high"
    print(f"[PASS] Updated map connection.")

    # List connections for a node
    conns_for_node1 = crud.list_connections_for_node(node1.id)
    assert len(conns_for_node1) == 1
    print(f"[PASS] list_connections_for_node -> {len(conns_for_node1)} connection(s).")

    # List all connections
    all_conns = crud.list_all_connections()
    assert len(all_conns) >= 1
    print(f"[PASS] list_all_connections -> {len(all_conns)} connection(s).")

    # Full map data
    nodes, conns = crud.get_full_map_data()
    assert len(nodes) >= 2
    assert len(conns) >= 1
    print(f"[PASS] get_full_map_data: {len(nodes)} nodes, {len(conns)} connections.")


def test_cascade_delete():
    """Verify that deleting an article cascades to its map nodes."""
    art = Article(title="Doomed City")
    crud.create_article(art)

    node = MapNode(article_id=art.id, x=10, y=20)
    crud.create_map_node(node)

    # Delete article
    crud.delete_article(art.id)
    assert crud.get_article(art.id) is None
    assert crud.get_map_node(node.id) is None
    print(f"[PASS] Cascading delete: article deletion removes map node.")


def test_file_persistence():
    """Test that data persists to a real file (separate DB instance)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name

    try:
        # Close the shared in-memory DB, open a file DB
        shared_db = DatabaseManager()
        shared_db.close()
        DatabaseManager._instance = None

        db1 = DatabaseManager()
        db1.open(tmp_path)
        art = Article(title="Persistent Article")
        crud.create_article(art)
        db1.close()

        # Re-open
        DatabaseManager._instance = None
        db2 = DatabaseManager()
        db2.open(tmp_path)
        fetched = crud.get_article(art.id)
        assert fetched is not None
        assert fetched.title == "Persistent Article"
        db2.close()

        # Restore the in-memory DB for subsequent tests
        DatabaseManager._instance = None
        setup_db = DatabaseManager()
        setup_db.open(":memory:")

        print(f"[PASS] Data persists across open/close cycle.")
    finally:
        os.unlink(tmp_path)


def test_backup():
    """Test database backup."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        backup_path = f.name

    try:
        db = DatabaseManager()
        # Use the shared in-memory DB
        art = Article(title="Backup Test Article")
        crud.create_article(art)
        db.backup_to(backup_path)

        # Open the backup independently
        DatabaseManager._instance = None
        bk_db = DatabaseManager()
        bk_db.open(backup_path, migrate=False)
        bk_art = crud.get_article(art.id)
        assert bk_art is not None
        assert bk_art.title == "Backup Test Article"
        bk_db.close()

        # Restore the in-memory DB
        DatabaseManager._instance = None
        setup_db = DatabaseManager()
        setup_db.open(":memory:")

        print(f"[PASS] Backup created and verified.")
    finally:
        os.unlink(backup_path)


# ======================================================================
#  Runner
# ======================================================================

def run_all():
    tests = [
        test_builtin_types,
        test_create_and_get_article,
        test_update_article,
        test_delete_article,
        test_list_articles,
        test_toggle_favorite,
        test_full_text_search,
        test_article_templates,
        test_map_nodes,
        test_map_connections,
        test_cascade_delete,
        test_file_persistence,
        test_backup,
    ]

    passed = 0
    failed = 0

    setup_module()

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            import traceback
            print(f"[FAIL] {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)