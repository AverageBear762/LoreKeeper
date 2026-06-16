"""
LoreKeeper — Global Search Dialog.

Full-text search powered by SQLite FTS5 with:
- Real-time search results as you type
- Filter by article type, tags, and category
- Results preview with article type icon and content snippet
- Keyboard shortcuts (↑↓ to navigate, Enter to open)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.models import Article


class SearchDialog(QDialog):
    """Global search dialog with type/tag filtering and live results."""

    article_selected = Signal(str)  # article_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search Articles")
        self.setMinimumSize(550, 450)
        self.setModal(False)

        self._all_results: list[Article] = []

        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Search bar ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search by title, content, or tags...")
        self.search_input.setMinimumHeight(36)
        self.search_input.setStyleSheet("font-size: 15px; padding: 6px 12px;")
        self.search_input.textChanged.connect(self._on_search)
        layout.addWidget(self.search_input)

        # --- Filters row ---
        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(8)

        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", "")
        for t in crud.list_all_article_types():
            self.type_filter.addItem(t, t)
        self.type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(QLabel("Type:"))
        filters_layout.addWidget(self.type_filter)

        self.fav_filter = QPushButton("⭐ Favorites Only")
        self.fav_filter.setCheckable(True)
        self.fav_filter.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 4px 10px; border: 1px solid palette(Midlight);"
            "  border-radius: 4px; }"
            "QPushButton:checked { background: palette(Highlight); color: palette(HighlightedText); }"
        )
        self.fav_filter.toggled.connect(self._on_filter_changed)
        filters_layout.addWidget(self.fav_filter)

        filters_layout.addStretch(1)
        self.result_count = QLabel("")
        self.result_count.setStyleSheet("font-size: 11px; color: palette(Mid);")
        filters_layout.addWidget(self.result_count)

        layout.addLayout(filters_layout)

        # --- Results list ---
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setSpacing(2)
        self.results_list.itemDoubleClicked.connect(self._on_item_activated)
        self.results_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.results_list, 1)

        # --- Bottom hint ---
        hint = QLabel("⏎ Open  |  ↑↓ Navigate  |  Esc Close")
        hint.setStyleSheet("font-size: 11px; color: palette(Mid);")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Up"), self, self._navigate_up)
        QShortcut(QKeySequence("Down"), self, self._navigate_down)
        QShortcut(QKeySequence("Return"), self, self._activate_current)
        QShortcut(QKeySequence("Escape"), self, self.close)

    # ----------------------------------------------------------------
    # Search logic
    # ----------------------------------------------------------------

    def _on_search(self) -> None:
        """Trigger search on text change with debounce."""
        text = self.search_input.text().strip()
        if len(text) < 2:
            self.results_list.clear()
            self.result_count.setText("Type at least 2 characters to search")
            return
        self._execute_search()

    def _on_filter_changed(self) -> None:
        """Re-filter current results or re-execute search."""
        if self.search_input.text().strip():
            self._execute_search()

    def _execute_search(self) -> None:
        """Perform FTS5 search with active filters."""
        query = self.search_input.text().strip()
        if not query:
            return

        # Get FTS5 results
        results = crud.search_articles(query, limit=100)

        # Apply filters
        article_type = self.type_filter.currentData()
        if article_type:
            results = [a for a in results if a.article_type == article_type]

        if self.fav_filter.isChecked():
            results = [a for a in results if a.is_favorite]

        self._all_results = results
        self._populate_results(results)

    def _populate_results(self, results: list[Article]) -> None:
        """Fill the results list with article entries."""
        self.results_list.clear()

        if not results:
            item = QListWidgetItem("No results found.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(Qt.GlobalColor.gray)
            self.results_list.addItem(item)
            self.result_count.setText("0 results")
            return

        for article in results:
            # Icon + title
            icon = self._type_icon(article.article_type)
            title = article.title or "Untitled"
            display = f"{icon}  {title}"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, article.id)
            item.setToolTip(f"Type: {article.article_type}")

            # Subtitle with snippet
            snippet = article.content[:80].strip().replace("\n", " ")
            if len(article.content) > 80:
                snippet += "..."
            if snippet:
                item.setToolTip(
                    f"[{article.article_type}]\n{snippet}\n\nTags: {', '.join(article.tags) if article.tags else 'none'}"
                )

            self.results_list.addItem(item)

        self.result_count.setText(f"{len(results)} result(s)")

    # ----------------------------------------------------------------
    # Navigation
    # ----------------------------------------------------------------

    def _navigate_up(self) -> None:
        idx = self.results_list.currentRow()
        if idx > 0:
            self.results_list.setCurrentRow(idx - 1)

    def _navigate_down(self) -> None:
        idx = self.results_list.currentRow()
        if idx < self.results_list.count() - 1:
            self.results_list.setCurrentRow(idx + 1)

    def _activate_current(self) -> None:
        item = self.results_list.currentItem()
        if item:
            self._on_item_activated(item)

    def _on_item_activated(self, item) -> None:
        article_id = item.data(Qt.ItemDataRole.UserRole)
        if article_id:
            self.article_selected.emit(article_id)
            self.accept()

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def focus_search(self) -> None:
        """Focus the search input and select all text."""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def set_search_text(self, text: str) -> None:
        """Pre-fill the search bar."""
        self.search_input.setText(text)

    @staticmethod
    def _type_icon(article_type: str) -> str:
        icons = {
            "Character": "🧑", "Location": "📍", "Faction": "⚜",
            "Item": "⚔", "Creature": "🐉", "Event": "📅",
            "Religion": "✝", "Species": "🧬", "Settlement": "🏘",
            "Nation": "🏰",
        }
        return icons.get(article_type, "📄")