# LoreKeeper

> Fully offline, local-first worldbuilding database and wiki for tabletop RPG game masters, writers, and creators.

LoreKeeper offers rich structured articles, automatic backlinking, hover previews, and an interactive node-based travel map — all operating **100% offline**. Your data stays yours in open, human-readable formats (SQLite + optional Markdown exports).

---

## Status

**Early Development.** This repository currently contains the database and models layer only. A PySide6 desktop UI, rendering engine, and packaging configuration are coming soon.

---

## Architecture

```
/code
├── database/            # Database & models layer
│   ├── __init__.py      # Package exports
│   ├── manager.py       # DatabaseManager (connection, WAL, pragmas)
│   ├── models.py        # Dataclasses: Article, ArticleTemplate, MapNode, MapConnection
│   ├── schema.py        # SQL schema, FTS5, triggers, migrations
│   └── crud.py          # Full CRUD for all entities
├── requirements.txt     # Python dependencies
├── .gitignore
└── README.md
```

### Database Layer

| Module | Purpose |
|---|---|
| `manager.py` | Singleton `DatabaseManager` — opens SQLite with WAL mode, foreign keys, busy timeout, row factories. Handles backup and default path resolution. |
| `schema.py` | Table DDL, FTS5 virtual table, indexes, triggers that auto-sync FTS on article changes, and a lightweight migration runner. |
| `models.py` | Pure dataclass models (`Article`, `ArticleTemplate`, `FieldDefinition`, `MapNode`, `MapConnection`) with `to_row()` / `from_row()` serialisation helpers. |
| `crud.py` | Complete CRUD functions: create, read, update, delete, list, search, toggle-favorite for all entity types. |

### Data Schema

**articles** — Structured wiki entries.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `title` | TEXT NOT NULL | Article title |
| `content` | TEXT | Markdown body |
| `article_type` | TEXT | Location / Character / Faction / Religion / Event / Species / Item / Creature / Settlement / Nation / custom |
| `template_fields` | TEXT (JSON) | Structured data per template schema |
| `tags` | TEXT (JSON array) | User-defined tags |
| `is_favorite` | INTEGER (bool) | Favorite flag |
| `created_at` | TEXT (ISO 8601) | Creation timestamp |
| `updated_at` | TEXT (ISO 8601) | Last update timestamp |

**article_templates** — Custom article type schemas.

| Column | Type |
|---|---|
| `id` | TEXT (UUID) |
| `type_name` | TEXT UNIQUE |
| `field_definitions` | TEXT (JSON array of `FieldDefinition`) |
| `created_at` / `updated_at` | TEXT (ISO 8601) |

**map_nodes** — Location nodes on the travel map, linked to articles.

| Column | Type |
|---|---|
| `id` | TEXT (UUID) |
| `article_id` | TEXT (FK → articles) |
| `x`, `y` | REAL |
| `label_visible` | INTEGER (bool) |
| `created_at` | TEXT |

**map_connections** — Travel paths between nodes.

| Column | Type |
|---|---|
| `id` | TEXT (UUID) |
| `node_a_id`, `node_b_id` | TEXT (FK → map_nodes) |
| `distance` | REAL |
| `travel_time` | TEXT |
| `terrain` | TEXT |
| `danger` | TEXT (low/medium/high/extreme) |
| `notes` | TEXT |

### Full-text Search

An **FTS5** virtual table (`articles_fts`) indexes article titles and content using the `porter` stemmer and `unicode61` tokenizer. Triggers keep it synchronised on `INSERT`, `UPDATE`, and `DELETE`. The `search_articles()` CRUD function searches via `MATCH` with result ranking.

---

## Getting Started

```bash
# Clone and install
cd LoreKeeper
pip install -r requirements.txt

# Quick test (inside /code)
python -c "
from database.manager import DatabaseManager
from database.models import Article
from database import crud

db = DatabaseManager()
db.open(':memory:')

# Create an article
article = Article(title='King Aldric', content='The wise ruler of **Avalon**.', article_type='Character')
crud.create_article(article)

# Search
results = crud.search_articles('Aldric')
for r in results:
    print(f'{r.title}: {r.content[:60]}...')
"
```

---

## Design Principles

1. **Data ownership** — Everything lives in a local SQLite file. No cloud, no telemetry, no lock-in.
2. **Zero corruption** — WAL journaling, foreign keys, transactional CRUD, and schema versioning ensure integrity.
3. **Fast** — All queries use indexed columns and FTS5. UI rendering targets <50ms transitions.
4. **Extensible** — Custom article templates, free-form tags, and JSON-structured fields let you model any world.

---

## Roadmap

- [x] Database & models layer
- [ ] PySide6 desktop UI
- [ ] Wiki article editor with Markdown preview
- [ ] Interactive travel map (QGraphicsView)
- [ ] Hover preview tooltips
- [ ] Folder / tag / favorites browser
- [ ] Pro features: custom themes, HTML/PDF export
- [ ] Standalone executable packaging (PyInstaller)