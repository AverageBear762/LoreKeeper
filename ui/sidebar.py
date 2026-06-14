"""
LoreKeeper — Sidebar widget.

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
from PySide6.QtGui import QIcon
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
    """Main sidebar panel for LoreKeeper."""

    # Signals
    article_selected = Signal(str)       # article_id
    search_requested = Signal(str)       # search query
    travel_map_requested = Signal()
    create_article_requested = Signal()

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
        """Fill the category tree with article types."""
        self.type_tree.clear()
        all_types = crud.list_all_article_types()
        for t in all_types:
            item = QTreeWidgetItem([t])
            item.setData(0, Qt.ItemDataRole.UserRole, t)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
            self.type_tree.addTopLevelItem(item)

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
        """Filter articles by the selected type."""
        article_type = item.data(0, Qt.ItemDataRole.UserRole)
        if article_type:
            results = crud.list_articles(article_type=article_type, limit=200)
            # Emit the first matching article or just the type filter
            if results:
                self.article_selected.emit(results[0].id)

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
        """Reload the favorites list from the database."""
        self.favorites_list.clear()
        favs = crud.list_articles(favorite_only=True, limit=50)
        for a in favs:
            item = QListWidgetItem(f"⭐ {a.title}")
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            self.favorites_list.addItem(item)

    def refresh_recent(self) -> None:
        """Reload the recently viewed list from the database."""
        self.recent_list.clear()
        recent = crud.list_articles(sort_by="updated_at", sort_desc=True, limit=20)
        for a in recent:
            item = QListWidgetItem(a.title)
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