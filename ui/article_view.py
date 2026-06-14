"""
LoreKeeper — Article View & Editor.

Central widget for displaying and editing wiki articles with:
- Title editing
- Rich content area (Markdown / plain text)
- Metadata display (type, tags, timestamps)
- Read-only view mode vs edit mode
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.models import Article


# ---------------------------------------------------------------------------
#  Metadata bar (type, timestamps, tags)
# ---------------------------------------------------------------------------

class MetadataBar(QFrame):
    """Displays article metadata: type pill, tags, timestamps."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetadataBar")
        self.setMaximumHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.type_label = QLabel()
        self.type_label.setObjectName("ArticleType")
        self.type_label.setStyleSheet(
            "QLabel#ArticleType {"
            "  background: #0d6efd; color: white;"
            "  padding: 2px 10px; border-radius: 8px;"
            "  font-size: 11px; font-weight: 600;"
            "}"
        )
        layout.addWidget(self.type_label)

        self.tags_label = QLabel()
        self.tags_label.setObjectName("ArticleTags")
        self.tags_label.setStyleSheet(
            "QLabel#ArticleTags { color: #6c757d; font-size: 12px; }"
        )
        layout.addWidget(self.tags_label)

        layout.addStretch(1)

        self.updated_label = QLabel()
        self.updated_label.setObjectName("ArticleUpdated")
        self.updated_label.setStyleSheet(
            "QLabel#ArticleUpdated { color: #adb5bd; font-size: 11px; }"
        )
        layout.addWidget(self.updated_label)

    def set_metadata(self, article: Article) -> None:
        """Update the metadata display from an Article model."""
        self.type_label.setText(article.article_type)
        tags_str = ", ".join(f"#{t}" for t in article.tags) if article.tags else ""
        self.tags_label.setText(tags_str)

        # Show a human-friendly relative time
        from datetime import datetime
        try:
            updated = datetime.fromisoformat(article.updated_at)
            ago = datetime.now() - updated
            if ago.days > 0:
                time_str = f"{ago.days}d ago"
            elif ago.seconds >= 3600:
                time_str = f"{ago.seconds // 3600}h ago"
            elif ago.seconds >= 60:
                time_str = f"{ago.seconds // 60}m ago"
            else:
                time_str = "just now"
            self.updated_label.setText(f"Updated {time_str}")
        except (ValueError, TypeError):
            self.updated_label.setText("")


# ---------------------------------------------------------------------------
#  ArticleView
# ---------------------------------------------------------------------------

class ArticleView(QFrame):
    """Central widget for viewing/editing a wiki article."""

    content_changed = Signal()
    article_updated = Signal(str)  # article_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ArticleArea")

        self._article: Optional[Article] = None
        self._is_editing: bool = False
        self._edit_mode: bool = True  # Default to editable

        self._build_ui()
        self.show_placeholder()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # -- Metadata bar --
        self.metadata_bar = MetadataBar()
        layout.addWidget(self.metadata_bar)

        # -- Title --
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("ArticleTitle")
        self.title_edit.setPlaceholderText("Article Title")
        self.title_edit.setStyleSheet(
            "font-size: 24px; font-weight: 600; border: none;"
            " padding: 4px 0; margin-bottom: 8px;"
        )
        layout.addWidget(self.title_edit)

        # -- Content editor --
        self.content_edit = QPlainTextEdit()
        self.content_edit.setObjectName("ArticleContent")
        self.content_edit.setPlaceholderText(
            "Write your article content here...\n\n"
            "Use [[Article Name]] to create wiki links.\n"
            "Markdown formatting is supported."
        )
        self.content_edit.setTabChangesFocus(False)
        self.content_edit.setMinimumHeight(200)
        layout.addWidget(self.content_edit, 1)

        # -- Placeholder label (shown when no article is loaded) --
        self.placeholder = QLabel(
            "Welcome to LoreKeeper\n\n"
            "Select an article from the sidebar or create a new one.\n\n"
            "🗺  Use the Travel Map to visualize locations.\n"
            "🔍  Search for articles by name or content."
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(
            "color: #adb5bd; font-size: 16px; padding: 60px;"
        )
        layout.addWidget(self.placeholder)

        # -- Save indicator --
        self.save_indicator = QLabel("")
        self.save_indicator.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.save_indicator.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.save_indicator)

        # Connect signals
        self.title_edit.textChanged.connect(self._on_content_edited)
        self.content_edit.textChanged.connect(self._on_content_edited)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_article(self, article: Article) -> None:
        """Load an article into the view (read-write)."""
        self._article = article
        self.placeholder.hide()
        self.title_edit.show()
        self.content_edit.show()
        self.metadata_bar.show()

        # Block signals while setting content
        self.title_edit.blockSignals(True)
        self.content_edit.blockSignals(True)

        self.title_edit.setText(article.title)
        self.content_edit.setPlainText(article.content)

        self.title_edit.blockSignals(False)
        self.content_edit.blockSignals(False)

        self.metadata_bar.set_metadata(article)
        self.save_indicator.setText("")

    def load_article_by_id(self, article_id: str) -> None:
        """Fetch an article from the database and load it."""
        article = crud.get_article(article_id)
        if article:
            self.load_article(article)

    def show_placeholder(self) -> None:
        """Show the welcome placeholder, hide article content."""
        self._article = None
        self.placeholder.show()
        self.title_edit.hide()
        self.content_edit.hide()
        self.metadata_bar.hide()
        self.save_indicator.setText("")

    def clear(self) -> None:
        """Clear the editor."""
        self._article = None
        self.title_edit.blockSignals(True)
        self.content_edit.blockSignals(True)
        self.title_edit.clear()
        self.content_edit.clear()
        self.title_edit.blockSignals(False)
        self.content_edit.blockSignals(False)
        self.save_indicator.setText("")
        self.show_placeholder()

    def save(self) -> bool:
        """Save the current article to the database. Returns True on success."""
        if self._article is None:
            return False

        new_title = self.title_edit.text().strip()
        new_content = self.content_edit.toPlainText()

        if not new_title:
            self.save_indicator.setText("⚠ Title cannot be empty")
            return False

        self._article.title = new_title
        self._article.content = new_content
        self._article.touch()

        crud.update_article(self._article)
        self.save_indicator.setText("✓ Saved")
        self.article_updated.emit(self._article.id)
        return True

    def create_new(self, article_type: str = "Location") -> Article:
        """Create a new blank article of the given type and open it for editing."""
        article = Article(title="", content="", article_type=article_type)
        crud.create_article(article)
        self.load_article(article)
        self.title_edit.setFocus()
        self.title_edit.selectAll()
        return article

    @property
    def current_article(self) -> Optional[Article]:
        return self._article

    @property
    def is_dirty(self) -> bool:
        """Check if the article has unsaved changes."""
        if self._article is None:
            return False
        return (
            self.title_edit.text() != self._article.title
            or self.content_edit.toPlainText() != self._article.content
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_content_edited(self) -> None:
        """Mark the article as having unsaved changes."""
        if self._article:
            self.save_indicator.setText("✎ Unsaved changes")
            self.content_changed.emit()

    def set_edit_mode(self, editing: bool) -> None:
        """Toggle edit mode (editable vs read-only view)."""
        self._edit_mode = editing
        self.title_edit.setReadOnly(not editing)
        self.content_edit.setReadOnly(not editing)
        if editing:
            self.content_edit.setStyleSheet(
                "QPlainTextEdit { background: transparent; }"
            )
        else:
            self.content_edit.setStyleSheet(
                "QPlainTextEdit { background: transparent; color: inherit; }"
            )