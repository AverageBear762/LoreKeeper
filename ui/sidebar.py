"""
World Garden — Sidebar widget.

Contains:
- Quick search bar
- Folder / category navigation tree (grouped by article type)
- Favorites shortcut list
- Recently Viewed shortcut list
- Link to Travel Map mode
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.models import Article, BUILTIN_ARTICLE_TYPES


# ======================================================================
#  Sidebar
# ======================================================================

class Sidebar(QFrame):
    """Main sidebar panel for World Garden."""

    # Signals
    article_selected = Signal(str)       # article_id
    search_requested = Signal(str)       # search query
    travel_map_requested = Signal()
    create_article_requested = Signal()
    delete_article_requested = Signal(str)  # article_id

    SECTION_STYLE = "QLabel#SectionHeader {}"
    LINK_STYLE = "QLabel#SidebarLink {}"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarPanel")
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Search bar --
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(12, 12, 12, 8)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.setPlaceholderText("🔍  Search articles...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        self.search_bar.returnPressed.connect(self._on_search_activated)
        search_layout.addWidget(self.search_bar)
        layout.addWidget(search_container)

        # -- New Article button --
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(12, 4, 12, 8)

        self.new_article_btn = QPushButton("+ New Article")
        self.new_article_btn.setObjectName("NewArticleBtn")
        self.new_article_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_article_btn.clicked.connect(self.create_article_requested.emit)
        btn_layout.addWidget(self.new_article_btn)
        layout.addWidget(btn_container)

        # -- Scrollable sidebar content --
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        # --- Type / Folder Tree ---
        scroll_layout.addWidget(self._make_section_label("CATEGORIES"))
        self.type_tree = QTreeWidget()
        self.type_tree.setHeaderHidden(True)
        self.type_tree.setIndentation(16)
        self.type_tree.setAnimated(True)
        self.type_tree.setFrameShape(QFrame.Shape.NoFrame)
        self.type_tree.setMinimumHeight(200)
        self.type_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.type_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.type_tree.itemClicked.connect(self._on_tree_item_clicked)
        scroll_layout.addWidget(self.type_tree)

        # --- Separator ---
        scroll_layout.addSpacing(12)

        # --- Favorites ---
        scroll_layout.addWidget(self._make_section_label("FAVORITES"))
        self.favorites_list = QListWidget()
        self.favorites_list.setFrameShape(QFrame.Shape.NoFrame)
        self.favorites_list.setMinimumHeight(60)
        self.favorites_list.itemClicked.connect(self._on_favorite_clicked)
        scroll_layout.addWidget(self.favorites_list)

        # --- Separator ---
        scroll_layout.addSpacing(12)

        # --- Recently Viewed ---
        scroll_layout.addWidget(self._make_section_label("RECENTLY VIEWED"))
        self.recent_list = QListWidget()
        self.recent_list.setFrameShape(QFrame.Shape.NoFrame)
        self.recent_list.setMinimumHeight(60)
        self.recent_list.itemClicked.connect(self._on_recent_clicked)
        scroll_layout.addWidget(self.recent_list)

        # --- Separator ---
        scroll_layout.addSpacing(12)

        # --- Travel Map Link ---
        map_link = QLabel('<a href="#" style="color: #0d6efd; text-decoration: none;">🗺  Travel Map</a>')
        map_link.setObjectName("SidebarLink")
        map_link.setAlignment(Qt.AlignmentFlag.AlignLeft)
        map_link.setCursor(Qt.CursorShape.PointingHandCursor)
        map_link.setTextFormat(Qt.TextFormat.RichText)
        map_link.setOpenExternalLinks(False)
        map_link.linkActivated.connect(self.travel_map_requested.emit)
        map_link.setContentsMargins(16, 8, 16, 8)
        scroll_layout.addWidget(map_link)

        scroll_layout.addStretch(1)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Populate tree
        self._populate_type_tree()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionHeader")
        label.setContentsMargins(16, 8, 16, 4)
        return label

    def _populate_type_tree(self) -> None:
        """Fill the category tree with article types and hierarchy."""
        self.type_tree.clear()
        all_types = crud.list_all_article_types()

        # Get hierarchical article data: (root_article, [child_articles])
        hierarchy = crud.get_article_hierarchy()
        # Also track orphan articles (no parent, but still listed per type)
        orphan_ids = {a.id for a, _ in hierarchy}

        # Group roots by type
        roots_by_type: dict[str, list[tuple[Article, list[Article]]]] = {}
        for root, children in hierarchy:
            t = root.article_type
            if t not in roots_by_type:
                roots_by_type[t] = []
            roots_by_type[t].append((root, children))

        for t in all_types:
            # Only show types that have articles
            roots = roots_by_type.get(t, [])
            total_count = len(roots) + sum(len(c) for _, c in roots)
            if total_count == 0:
                continue  # Skip empty types

            type_root = QTreeWidgetItem([f"{t}  ({total_count})"])
            type_root.setData(0, Qt.ItemDataRole.UserRole, t)
            type_root.setData(0, Qt.ItemDataRole.DecorationRole, self._type_icon(t))
            type_root.setFlags(type_root.flags() | Qt.ItemFlag.ItemIsEnabled)
            type_root.setExpanded(True)
            self.type_tree.addTopLevelItem(type_root)

            # Add root articles (parent_id IS NULL) as children of type
            for root_article, child_articles in roots_by_type.get(t, []):
                root_item = QTreeWidgetItem([
                    f"{self._type_icon(root_article.article_type)} {root_article.title}"
                ])
                root_item.setData(0, Qt.ItemDataRole.UserRole, root_article.id)
                root_item.setToolTip(0, f"{root_article.article_type}")
                type_root.addChild(root_item)
                root_item.setExpanded(True)

                # Add child articles beneath each root
                for child in child_articles:
                    child_item = QTreeWidgetItem([
                        f"  {self._type_icon(child.article_type)} {child.title}"
                    ])
                    child_item.setData(0, Qt.ItemDataRole.UserRole, child.id)
                    child_item.setToolTip(0, f"Child of: {root_article.title}")
                    root_item.addChild(child_item)

            # Update count on type header
            child_count = type_root.childCount()
            type_root.setText(0, f"{t}  ({child_count})")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, text: str) -> None:
        """Emit search request after a brief pause (debounce handled by caller)."""
        if len(text) >= 2:
            self.search_requested.emit(text)

    def _on_search_activated(self) -> None:
        query = self.search_bar.text().strip()
        if query:
            self.search_requested.emit(query)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Navigate to an article or filter by type."""
        article_id = item.data(0, Qt.ItemDataRole.UserRole)
        if article_id and len(article_id) == 36:  # UUID length = 36 chars
            # This is an article item — navigate to it
            self.article_selected.emit(article_id)
        elif article_id:
            # This is a type header — emit search/filter for that type
            results = crud.list_articles(article_type=article_id, limit=200)
            if results:
                self.article_selected.emit(results[0].id)

    def _on_tree_context_menu(self, pos) -> None:
        """Right-click context menu on the category tree."""
        item = self.type_tree.itemAt(pos)
        if not item:
            return
        article_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not article_id or len(article_id) != 36:
            return  # Only show for article items, not type headers

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act_delete = QAction("🗑 Delete Article", self)
        act_delete.triggered.connect(lambda: self.delete_article_requested.emit(article_id))
        menu.addAction(act_delete)
        menu.exec(self.type_tree.viewport().mapToGlobal(pos))

    def _on_favorite_clicked(self, item: QListWidgetItem) -> None:
        article_id = item.data(Qt.ItemDataRole.UserRole)
        if article_id:
            self.article_selected.emit(article_id)

    def _on_recent_clicked(self, item: QListWidgetItem) -> None:
        article_id = item.data(Qt.ItemDataRole.UserRole)
        if article_id:
            self.article_selected.emit(article_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_favorites(self) -> None:
        """Reload the favorites list with type icons and timestamps."""
        self.favorites_list.clear()
        favs = crud.list_articles(favorite_only=True, limit=50)
        for a in favs:
            icon = self._type_icon(a.article_type)
            item = QListWidgetItem(f"{icon} {a.title}")
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            item.setToolTip(f"{a.article_type} — Updated: {a.updated_at[:10]}")
            self.favorites_list.addItem(item)

    def refresh_recent(self) -> None:
        """Reload the recently viewed list with relative timestamps."""
        self.recent_list.clear()
        recent = crud.list_articles(sort_by="updated_at", sort_desc=True, limit=20)
        for a in recent:
            from datetime import datetime
            time_str = ""
            try:
                updated = datetime.fromisoformat(a.updated_at)
                ago = datetime.now() - updated
                if ago.days > 0:
                    time_str = f" {ago.days}d"
                elif ago.seconds >= 3600:
                    time_str = f" {ago.seconds // 3600}h"
                elif ago.seconds >= 60:
                    time_str = f" {ago.seconds // 60}m"
                else:
                    time_str = " now"
            except (ValueError, TypeError):
                pass
            icon = self._type_icon(a.article_type)
            item = QListWidgetItem(f"{icon} {a.title}{time_str}")
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            self.recent_list.addItem(item)

    def refresh_category_tree(self) -> None:
        """Rebuild the type/category tree."""
        self._populate_type_tree()

    def set_search_text(self, text: str) -> None:
        """Programmatically set the search bar text."""
        self.search_bar.setText(text)

    def clear_search(self) -> None:
        """Clear the search bar."""
        self.search_bar.clear()

    @staticmethod
    def _type_icon(article_type: str) -> str:
        icons = {
            "Character": "🧑", "Location": "📍", "Faction": "⚜",
            "Item": "⚔", "Creature": "🐉", "Event": "📅",
            "Religion": "✝", "Species": "🧬", "Settlement": "🏘",
            "Nation": "🏰",
        }
        return icons.get(article_type, "📄")