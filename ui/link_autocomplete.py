"""
LoreKeeper — Link Autocomplete for Wiki Content Editor.

Detects when the user types `[[` in the article content editor
and shows a dropdown list of matching article titles for
quick insertion of wiki links.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCompleter,
    QListWidget,
    QListWidgetItem,
)

from database import crud


class WikiLinkCompleter(QCompleter):
    """Completer that suggests article titles when typing ``[[``."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setMaxVisibleItems(10)

        # Load all article titles as completion model
        self._refresh_model()

    def _refresh_model(self) -> None:
        """Reload article titles from the database."""
        articles = crud.list_articles(limit=500, sort_by="title")
        titles = [a.title for a in articles if a.title]
        from PySide6.QtCore import QStringListModel
        self.setModel(QStringListModel(sorted(titles)))

    def refresh(self) -> None:
        """Called after creating a new article to update suggestions."""
        self._refresh_model()


class LinkAutocompletePopup(QListWidget):
    """Floating popup list that shows article title suggestions for [[ links.

    Attach to a QPlainTextEdit by monitoring text changes.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMaximumHeight(200)
        self.setMinimumWidth(250)
        self.setAlternatingRowColors(True)
        self.itemDoubleClicked.connect(self._on_item_activated)
        self.itemActivated.connect(self._on_item_activated)

        self._all_titles: list[str] = []
        self._refresh_titles()

    def _refresh_titles(self) -> None:
        """Load all article titles from the DB."""
        articles = crud.list_articles(limit=500, sort_by="title")
        self._all_titles = sorted(
            [a.title for a in articles if a.title],
            key=str.lower,
        )

    def refresh(self) -> None:
        self._refresh_titles()

    def show_for_query(self, query: str, widget_pos, global_pos) -> None:
        """Show the popup near the cursor with matching titles."""
        self.clear()

        if not query:
            self.hide()
            return

        query_lower = query.lower()
        matches = [t for t in self._all_titles if query_lower in t.lower()]

        if not matches:
            self.hide()
            return

        for title in matches[:8]:  # Max 8 suggestions
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, title)
            self.addItem(item)

        # Position near the cursor
        self.move(global_pos)
        self.setMinimumWidth(
            max(250, self.sizeHintForColumn(0) + 30)
        )
        self.setCurrentRow(0)
        self.show()
        self.raise_()

    def get_selected_title(self) -> Optional[str]:
        """Return the currently selected title, or None."""
        item = self.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def select_next(self) -> None:
        """Select the next item in the list."""
        row = self.currentRow()
        if row < self.count() - 1:
            self.setCurrentRow(row + 1)

    def select_prev(self) -> None:
        """Select the previous item."""
        row = self.currentRow()
        if row > 0:
            self.setCurrentRow(row - 1)

    def _on_item_activated(self, item) -> None:
        """Emit a signal or just hide — handled by the editor."""
        self.hide()

    def hideEvent(self, event) -> None:
        """Ensure clean hide."""
        self.clear()
        super().hideEvent(event)