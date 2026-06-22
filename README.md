# LoreKeeper

> **Fully offline, local-first worldbuilding database and wiki** for tabletop RPG game masters, writers, and creators.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.11+-green.svg)](https://wiki.qt.io/Qt_for_Python)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)](LICENSE)

LoreKeeper offers rich structured articles, automatic backlinking, hover previews, and an interactive node-based travel map — all operating **100% offline**. Your data stays yours in open, human-readable formats (SQLite + optional JSON/Markdown exports).

**No subscriptions. No cloud. No telemetry. Your lore, your machine.**

---

## ✨ Features

| Feature | Description |
|---|---|
| **📝 Structured Articles** | Create wiki entries by type: Character, Location, Faction, Religion, Event, Species, Item, Creature, Settlement, Nation, or custom types with user-defined templates |
| **🔗 Wiki Links & Backlinks** | Use `[[Article Name]]` syntax to cross-reference articles; automatic backlink discovery shows what links to your article |
| **🔍 Full-Text Search** | Blazing-fast FTS5 search with type/tag/favorite filters, accessed via `Ctrl+F` |
| **🗺️ Travel Map** | Interactive node-based map (QGraphicsView) with draggable nodes, travel connections, danger ratings, background images, and zoom/pan |
| **🔎 Hover Tooltips** | Hover over `[[wiki links]]` or map nodes for instant previews with portraits, metadata, and content summaries |
| **📋 Templates** | Define custom article type schemas with multiple field types: Text, LongText, Number, Boolean, Date, Select, Image |
| **📁 Organization** | Sidebar with category tree (with counts), favorites, recently viewed, tags, and global search |
| **🌗 Light/Dark Theme** | Toggle instantly with keyboard shortcuts or menu |
| **💾 Autosave** | Automatic saving every 60 seconds — never lose your work |
| **📤 Export & Backup** | SQLite-native backup, JSON snapshot export/import — full data portability |
| **🔌 Fully Offline** | No internet connection required. Ever. |

---

## 🚀 Quick Start

### Development Mode

```bash
# 1. Clone the repository
git clone https://github.com/your-org/lorekeeper.git
cd lorekeeper

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the database tests (optional, recommended)
python test_database.py

# 5. Launch LoreKeeper
python main.py

# Or open a specific database file
python main.py /path/to/my_world.db
```

### First Launch

On first launch, LoreKeeper creates a default database at:

| Platform | Location |
|---|---|
| **Linux** | `~/.local/share/LoreKeeper/lorekeeper.db` |
| **macOS** | `~/Library/Application Support/LoreKeeper/lorekeeper.db` |
| **Windows** | `%APPDATA%\LoreKeeper\lorekeeper.db` |

You can also pass a custom path as a CLI argument: `python main.py my_campaign.db`

---

## 📦 Building a Standalone Executable

### Prerequisites

```bash
pip install pyinstaller
```

### Using the Build Script (Recommended)

```bash
# Default build (one-directory bundle, recommended)
./compile.sh

# Clean build (removes old artifacts first)
./compile.sh --clean

# Debug build (verbose logging)
./compile.sh --debug
```

Output: `dist/LoreKeeper/` — run it with:

```bash
./dist/LoreKeeper/LoreKeeper
```

### Manual PyInstaller Build

```bash
# One-directory bundle (recommended for PySide6)
pyinstaller lorekeeper.spec --noconfirm

# Single-file executable (experimental — larger startup time)
pyinstaller lorekeeper.spec --onefile --noconfirm
```

### Platform-Specific Notes

#### Linux

```bash
# Build on the target distribution (or oldest glibc you support)
./compile.sh

# Optional: Create an AppImage using appimagetool
# See: https://github.com/AppImage/AppImageKit
```

- The spec sets `console=False` (GUI app) — but on Linux this is advisory; terminals are fine.
- Test on your target distros. PySide6 bundles its own Qt, so no system Qt is needed.

#### macOS

```bash
# Build
./compile.sh

# Code-sign (required for distribution)
codesign -s "Developer ID Application: Your Name" dist/LoreKeeper.app

# Create DMG installer
# brew install create-dmg
create-dmg --app "LoreKeeper" --volname "LoreKeeper" \
    "LoreKeeper.dmg" "dist/LoreKeeper.app"
```

- The spec auto-detects macOS and sets `console=False`.
- Without code-signing, Gatekeeper may block the app. Use `spctl --assess --verbose dist/LoreKeeper.app` to verify.

#### Windows

```cmd
:: Build in cmd.exe or PowerShell
python -m PyInstaller lorekeeper.spec --noconfirm

:: Create installer with Inno Setup or NSIS
:: Or simply zip dist/LoreKeeper/ as a portable app
```

- The spec sets `console=False` — no terminal window appears on launch.
- Use [Inno Setup](https://jrsoftware.org/isinfo.php) to create a proper installer.

### Bundle Size Notes

PySide6 is a large framework. The one-directory bundle is typically **150–250 MB**. This is normal for Qt6 desktop applications. The single-file (`--onefile`) option increases startup time because the OS must decompress the archive before launching.

---

## 📖 User Manual

### Creating Articles

1. Press **`Ctrl+N`** or click **File → New Article**.
2. Enter a **Title** and select an **Article Type** (Character, Location, Faction, etc.).
3. The **Editor** shows two tabs:
   - **Edit** — Write markdown content for the article body.
   - **Preview** — Rendered HTML with wiki links as clickable buttons.
4. If the article type has a template (e.g., Character), the **Template Fields** panel appears on the right with structured fields (e.g., Age, Race, Occupation).
5. Add **Tags** by typing and pressing Enter.
6. Toggle **Favorite** (star icon) to mark important articles.
7. Press **`Ctrl+S`** or wait for the autosave (every 60 seconds).

### Wiki Links (`[[` Syntax)

While editing, type `[[` to trigger the autocomplete popup:

```
The king of [[Avalon]] ruled wisely for decades.
```

- The autocomplete suggests matching article titles as you type.
- Press **Tab** or **Enter** to select a suggestion.
- In Preview mode, `[[Article Name]]` renders as a clickable link.
- Hover over any wiki link for an instant tooltip with portrait and metadata.
- The **Backlinks** section at the bottom of each article shows which other articles link to it.

### Templates

1. Click **File → Manage Templates** to open the template manager.
2. **Create a new template**: Give it a type name (e.g., "Spell") and add fields.
3. **Field types**:
   - **Text** — Single-line text input
   - **LongText** — Multi-line text area
   - **Number** — Numeric input with optional min/max
   - **Boolean** — Checkbox
   - **Date** — Date picker
   - **Select** — Dropdown with predefined options
   - **Image** — File path for portrait/map images
4. **Edit or delete** existing templates as needed.
5. When you create an article with a matching type, the template fields appear automatically.

### Travel Map

1. Click the **Travel Map** button in the toolbar or sidebar.
2. **Add a node**: Right-click on the canvas → **Add Node** → select an existing article.
3. **Move a node**: Drag it to any position.
4. **Connect nodes**: Click the **Connect** button in the toolbar, then click two nodes sequentially.
5. **Edit connection**: Double-click a connection line to set distance, travel time, terrain, and danger level.
6. **Open article**: Click a node to open its article.
7. **Background image**: Right-click on empty canvas → **Set Background Image**.
8. **Zoom**: Scroll wheel. **Pan**: Middle-click drag or right-click drag.

### Search

- Press **`Ctrl+F`** to open the global search dialog.
- Type a query — results appear instantly (FTS5-powered).
- Filter by **Article Type**, **Tags**, or **Favorites only**.
- Navigate results with **↑/↓** and press **Enter** to open.
- Press **`Esc`** to close.

### Backup & Export

| Action | Menu Path | Description |
|---|---|---|
| **Backup Database** | File → Backup → Create Backup | Copies the live SQLite database to a timestamped file |
| **Export JSON** | File → Backup → Export as JSON | Exports all articles as a human-readable JSON file |
| **Import JSON** | File → Backup → Import from JSON | Imports articles from a previously exported JSON file |

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New article |
| `Ctrl+E` | Edit selected article |
| `Ctrl+S` | Save current article |
| `Ctrl+F` | Search / Find |
| `Ctrl+Shift+T` | Toggle theme (Light/Dark) |
| `Ctrl+W` | Close current article |
| `Ctrl+Q` | Quit application |
| `F5` | Refresh sidebar |
| `Esc` | Close search dialog / clear selection |

---

## 📁 Project Structure

```
/code
├── lorekeeper.spec          # PyInstaller packaging spec
├── compile.sh               # Cross-platform build script
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── test_database.py         # Database test suite (13 tests)
├── README.md                # This file
├── LICENSE                  # License file
│
├── database/                # Database & data layer
│   ├── __init__.py          # Package exports
│   ├── manager.py           # DatabaseManager — connection, WAL, pragmas, backup
│   ├── models.py            # Dataclasses: Article, ArticleTemplate, MapNode, MapConnection
│   ├── schema.py            # DDL, FTS5, triggers, migration runner
│   └── crud.py              # Full CRUD for articles, templates, map nodes, connections
│
└── ui/                      # Desktop UI layer (PySide6)
    ├── __init__.py
    ├── article_view.py      # Article editor with preview, wiki links, hover tooltips
    ├── backup_manager.py    # Backup, JSON export/import, SQLite backup
    ├── default_templates.py # Seed templates for Character, Item, Location, Creature
    ├── form_builder.py      # Dynamic form generator from template schema
    ├── hover_preview.py     # Floating frameless tooltip with fade animation
    ├── link_autocomplete.py # [[ autocomplete popup
    ├── main_window.py       # Top-level window: menu, toolbar, status bar, navigation
    ├── search_dialog.py     # Global FTS5 search dialog with filters
    ├── sidebar.py           # Category tree, favorites, recently viewed
    ├── template_editor.py   # Template creation/editing dialog
    ├── theme.py             # Light/Dark theme manager with QPalette + QSS
    ├── travel_map.py        # Interactive QGraphicsView node-based travel map
    └── wiki_links.py        # [[Parser]], HTML renderer, backlink engine
```

---

## 🗄️ Database Schema

### `articles` — Structured wiki entries

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `title` | TEXT NOT NULL UNIQUE | Article title |
| `content` | TEXT | Markdown body |
| `article_type` | TEXT | e.g., `Character`, `Location`, or custom |
| `template_fields` | TEXT (JSON) | Structured data per template |
| `tags` | TEXT (JSON array) | e.g., `["elf", "noble"]` |
| `is_favorite` | INTEGER (0/1) | Favorite flag |
| `created_at` | TEXT (ISO 8601) | Creation timestamp |
| `updated_at` | TEXT (ISO 8601) | Last update |

### `articles_fts` — Full-text search (FTS5 virtual table)

- Indexes: `title`, `content`
- Auto-synced via triggers on `INSERT`, `UPDATE`, `DELETE`
- Uses `porter` stemmer + `unicode61` tokenizer

### `article_templates` — Custom template schemas

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `type_name` | TEXT UNIQUE | Template name, e.g., `Spell` |
| `field_definitions` | TEXT (JSON) | Array of `FieldDefinition` objects |

### `map_nodes` — Travel map location nodes

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `article_id` | TEXT (FK → articles) | Linked article (CASCADE delete) |
| `x`, `y` | REAL | Position on the map canvas |
| `label_visible` | INTEGER (0/1) | Show/hide node label |
| `created_at` | TEXT (ISO 8601) | Creation timestamp |

### `map_connections` — Travel paths between nodes

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `node_a_id`, `node_b_id` | TEXT (FK → map_nodes) | Connected nodes (CASCADE delete) |
| `distance` | REAL | Travel distance (any unit) |
| `travel_time` | TEXT | e.g., "3 days", "6 hours" |
| `terrain` | TEXT | e.g., "forest", "mountain" |
| `danger` | TEXT | `low`, `medium`, `high`, `extreme` |
| `notes` | TEXT | Free-form notes |

---

## 🔧 Development

### Running Tests

```bash
# Database tests (13 tests covering CRUD, FTS5, cascade, persistence, backup)
python test_database.py
```

### Code Quality

- Pure Python 3.12+, no type-checker dependencies required.
- Database layer uses `sqlite3.Row` for named-column access.
- UI layer uses `QGraphicsScene`/`QGraphicsView` for the travel map.
- Follows singleton pattern for `DatabaseManager`.

### Adding a New UI Component

1. Create the file in `ui/`.
2. Add the import to `lorekeeper.spec`'s `HIDDEN_IMPORTS` list.
3. Wire it into `main_window.py` (slots, toolbar, menu).

---

## 🧪 Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.12+ |
| **GUI Framework** | PySide6 (Qt 6.11+) |
| **Database** | SQLite 3 (with FTS5) |
| **Image Processing** | Pillow |
| **Graphics/Map** | QGraphicsView / QGraphicsScene |
| **Packaging** | PyInstaller 6.x |

---

## 🎯 Design Principles

1. **Data Ownership** — Everything lives in a local SQLite file. No cloud, no telemetry, no lock-in.
2. **Zero Corruption** — WAL journaling, foreign keys, transactional CRUD, schema versioning, and autosave ensure integrity.
3. **Speed** — All queries use indexed columns and FTS5. UI targets <50ms transitions.
4. **Offline-First** — 100% offline. No internet access needed for any feature.
5. **Extensible** — Custom article templates, free-form tags, JSON-structured fields — model any world.

---

## 🗺️ Roadmap

- [x] Database & models layer
- [x] PySide6 desktop UI shell
- [x] Wiki article editor with preview
- [x] Interactive travel map (QGraphicsView)
- [x] Hover preview tooltips
- [x] Folder / tag / favorites browser
- [x] Global search (FTS5)
- [x] Template engine & structured forms
- [x] Wiki links (`[[ ]]`) with autocomplete
- [x] Backlinks & hover previews
- [x] Backup, export, and import
- [x] Light/Dark theme toggle
- [x] Standalone executable packaging
- [ ] **Pro**: Custom themes & HTML/PDF export
- [ ] **Pro**: Interactive HTML map export
- [ ] Plugin system for custom renderers
- [ ] Spellcheck / grammar in editor

---

## 📄 License

Proprietary. All rights reserved.

LoreKeeper is **free** for personal use. The core desktop application remains free and open-source (code available). A "Pay What You Want" Pro License unlocks premium custom themes and advanced exports (interactive HTML bundles, styled PDFs).

---

## 🙏 Acknowledgements

- [Qt for Python (PySide6)](https://wiki.qt.io/Qt_for_Python) — Cross-platform GUI framework
- [SQLite FTS5](https://www.sqlite.org/fts5.html) — Full-text search engine
- [PyInstaller](https://pyinstaller.org/) — Application packaging
- [Pillow](https://python-pillow.org/) — Image processing
