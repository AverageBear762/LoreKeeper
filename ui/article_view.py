"""
LoreKeeper — Article View & Editor.

Central widget for displaying and editing wiki articles with:
- Title editing
- Rendered markdown content with clickable [[wiki links]]
- Floating hover tooltips over wiki links
- Backlinks ("What links here?") section
- Template fields panel (structured data from template schema)
- Autosave on form changes
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.models import Article, ArticleTemplate
from ui.form_builder import DynamicForm
from ui.hover_preview import HoverPreviewWidget, HoverTracker
from ui.link_autocomplete import LinkAutocompletePopup
from ui.wiki_links import WikiTextBrowser, find_backlinks


# ---------------------------------------------------------------------------
#  Metadata bar
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
        self.type_label.setText(article.article_type)
        tags_str = ", ".join(f"#{t}" for t in article.tags) if article.tags else ""
        self.tags_label.setText(tags_str)

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
#  BacklinksSection
# ---------------------------------------------------------------------------

class BacklinksSection(QFrame):
    """Shows 'What links here?' — articles that link to the current one."""

    article_selected = Signal(str)  # article_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("BacklinksSection")
        self.setStyleSheet("""
            #BacklinksSection {
                border-top: 1px solid palette(Midlight);
                margin-top: 8px;
                padding-top: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        header = QLabel("🔗 What links here?")
        header.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: palette(Text);"
        )
        layout.addWidget(header)

        self.links_list = QVBoxLayout()
        self.links_list.setSpacing(2)
        layout.addLayout(self.links_list)

        self.empty_label = QLabel("No other articles link to this page.")
        self.empty_label.setStyleSheet("font-size: 11px; color: palette(Mid);")
        self.empty_label.setContentsMargins(12, 0, 0, 0)
        layout.addWidget(self.empty_label)

    def set_article(self, article: Optional[Article]) -> None:
        """Load backlinks for the given article."""
        self._clear_links()
        if not article or not article.title:
            self.empty_label.show()
            return

        backlinks = find_backlinks(article.title)
        if not backlinks:
            self.empty_label.show()
            return

        self.empty_label.hide()
        for bl in backlinks:
            link = QPushButton(f"📄 {bl.title}")
            link.setFlat(True)
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setStyleSheet(
                "QPushButton { text-align: left; padding: 2px 12px;"
                "  font-size: 12px; color: palette(Link); border: none; }"
                "QPushButton:hover { background: palette(AlternateBase);"
                "  border-radius: 4px; }"
            )
            link.clicked.connect(lambda checked, aid=bl.id: self.article_selected.emit(aid))
            self.links_list.addWidget(link)

    def _clear_links(self) -> None:
        while self.links_list.count():
            item = self.links_list.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.empty_label.show()


# ---------------------------------------------------------------------------
#  ArticleView
# ---------------------------------------------------------------------------

class ArticleView(QFrame):
    """Central widget for viewing/editing a wiki article."""

    content_changed = Signal()
    article_updated = Signal(str)  # article_id
    link_navigated = Signal(str)   # article_id
    link_creation_requested = Signal(str)  # article_name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ArticleArea")

        self._article: Optional[Article] = None
        self._edit_mode: bool = True

        # Hover tooltip system
        self._tooltip = HoverPreviewWidget()
        self._hover_tracker = HoverTracker(self._tooltip)
        self._hover_timer_link = QTimer()
        self._hover_timer_link.setSingleShot(True)
        self._hover_timer_link.setInterval(200)
        self._hover_timer_link.timeout.connect(self._on_hover_timeout)
        self._hover_article_name: Optional[str] = None
        self._hover_global_pos: tuple[int, int] = (0, 0)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Metadata bar --
        self.metadata_bar = MetadataBar()
        root.addWidget(self.metadata_bar)

        # -- Central scroll area --
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(24, 16, 24, 16)
        scroll_layout.setSpacing(8)

        # -- Title --
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("ArticleTitle")
        self.title_edit.setPlaceholderText("Article Title")
        self.title_edit.setStyleSheet(
            "font-size: 24px; font-weight: 600; border: none;"
            " padding: 4px 0; margin-bottom: 4px;"
        )
        scroll_layout.addWidget(self.title_edit)

        # -- Splitter: content area (left) + template fields (right) --
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left panel: tabs for Edit/Preview
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # View/Edit toggle buttons
        mode_bar = QHBoxLayout()
        mode_bar.setSpacing(4)
        self.edit_btn = QPushButton("✏ Edit")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setChecked(True)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 2px 10px; border: 1px solid palette(Midlight);"
            "  border-radius: 4px; }"
            "QPushButton:checked { background: palette(Highlight); color: palette(HighlightedText); }"
        )
        self.edit_btn.toggled.connect(self._on_edit_mode_toggled)
        mode_bar.addWidget(self.edit_btn)

        self.preview_btn = QPushButton("👁 Preview")
        self.preview_btn.setCheckable(True)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 2px 10px; border: 1px solid palette(Midlight);"
            "  border-radius: 4px; }"
            "QPushButton:checked { background: palette(Highlight); color: palette(HighlightedText); }"
        )
        self.preview_btn.toggled.connect(self._on_preview_mode_toggled)
        mode_bar.addWidget(self.preview_btn)

        mode_bar.addStretch(1)
        left_layout.addLayout(mode_bar)

        # Content editor (QPlainTextEdit)
        self.content_edit = QPlainTextEdit()
        self.content_edit.setObjectName("ArticleContent")
        self.content_edit.setPlaceholderText(
            "Write your article content here...\n\n"
            "Use [[Article Name]] to create wiki links.\n"
            "Use [[Article Name|Display Text]] for custom link text.\n"
            "Markdown: **bold**, *italic*, `code`, # headings"
        )
        self.content_edit.setTabChangesFocus(False)
        self.content_edit.setMinimumHeight(200)
        left_layout.addWidget(self.content_edit, 1)

        # Link autocomplete popup
        self._link_autocomplete = LinkAutocompletePopup(self)
        self.content_edit.textChanged.connect(self._on_content_autocomplete)
        self._autocomplete_active = False
        self._autocomplete_query = ""

        # Preview browser (WikiTextBrowser with rendered wiki links)
        self.preview_browser = WikiTextBrowser()
        self.preview_browser.setMinimumHeight(200)
        self.preview_browser.link_navigated.connect(self._on_link_navigated)
        self.preview_browser.link_creation_requested.connect(
            self.link_creation_requested.emit
        )
        # Mouse tracking for hover tooltips in the preview
        self.preview_browser.setMouseTracking(True)
        self.preview_browser.viewport().installEventFilter(self)
        left_layout.addWidget(self.preview_browser, 1)

        self.content_edit.show()
        self.preview_browser.hide()

        splitter.addWidget(left_panel)

        # Right panel: template fields
        self.template_fields_panel = DynamicForm()
        splitter.addWidget(self.template_fields_panel)

        splitter.setSizes([600, 300])
        scroll_layout.addWidget(splitter, 1)

        # -- Backlinks section --
        self.backlinks_section = BacklinksSection()
        self.backlinks_section.article_selected.connect(self.link_navigated.emit)
        scroll_layout.addWidget(self.backlinks_section)

        # -- Save indicator --
        self.save_indicator = QLabel("")
        self.save_indicator.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.save_indicator.setAlignment(Qt.AlignmentFlag.AlignRight)
        scroll_layout.addWidget(self.save_indicator)

        scroll_area.setWidget(scroll_content)
        root.addWidget(scroll_area, 1)

        # -- Welcome placeholder --
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
        root.addWidget(self.placeholder)

        # Connect signals
        self.title_edit.textChanged.connect(self._on_content_edited)
        self.content_edit.textChanged.connect(self._on_content_edited)
        self.template_fields_panel.value_changed.connect(self._on_content_edited)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_article(self, article: Article) -> None:
        """Load an article into the view."""
        self._article = article
        self.placeholder.hide()

        self.title_edit.blockSignals(True)
        self.content_edit.blockSignals(True)

        self.title_edit.setText(article.title)
        self.content_edit.setPlainText(article.content)

        self.title_edit.blockSignals(False)
        self.content_edit.blockSignals(False)

        self.metadata_bar.set_metadata(article)

        # Refresh preview
        self.preview_browser.set_wiki_content(article.content)

        # Template fields
        template = crud.get_template_by_type_name(article.article_type)
        self.template_fields_panel.load_template(template, article.template_fields)

        # Backlinks
        self.backlinks_section.set_article(article)

        self.save_indicator.setText("")

    def load_article_by_id(self, article_id: str) -> None:
        """Fetch and load an article by id."""
        article = crud.get_article(article_id)
        if article:
            self.load_article(article)

    def show_placeholder(self) -> None:
        """Show the welcome placeholder."""
        self._article = None
        self.placeholder.show()

    def clear(self) -> None:
        """Clear the editor."""
        self._article = None
        self.title_edit.blockSignals(True)
        self.content_edit.blockSignals(True)
        self.title_edit.clear()
        self.content_edit.clear()
        self.title_edit.blockSignals(False)
        self.content_edit.blockSignals(False)
        self.preview_browser.clear()
        self.template_fields_panel.clear()
        self.backlinks_section.set_article(None)
        self.save_indicator.setText("")
        self.show_placeholder()

    def save(self) -> bool:
        """Save the current article. Returns True on success."""
        if self._article is None:
            return False

        new_title = self.title_edit.text().strip()
        new_content = self.content_edit.toPlainText()

        if not new_title:
            self.save_indicator.setText("⚠ Title cannot be empty")
            return False

        self._article.title = new_title
        self._article.content = new_content
        self._article.template_fields = self.template_fields_panel.get_values()
        self._article.touch()

        crud.update_article(self._article)

        # Refresh the preview after save
        self.preview_browser.set_wiki_content(new_content)
        self.backlinks_section.set_article(self._article)

        self.save_indicator.setText("✓ Saved")
        self.article_updated.emit(self._article.id)
        return True

    def create_new(self, article_type: str = "Location") -> Article:
        """Create a new article and open it for editing."""
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
        if self._article is None:
            return False
        return (
            self.title_edit.text() != self._article.title
            or self.content_edit.toPlainText() != self._article.content
        )

    # ------------------------------------------------------------------
    # Event filter for hover tooltip tracking on the preview browser
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self.preview_browser.viewport():
            if event.type() == event.Type.MouseMove:
                self._on_mouse_move(event)
            elif event.type() == event.Type.Leave:
                self._hover_tracker.stop()
        return super().eventFilter(obj, event)

    def _on_mouse_move(self, event) -> None:
        """Check if mouse is over a wiki link in the preview browser."""
        pos = event.pos()
        cursor = self.preview_browser.cursorForPosition(pos)
        # Check if the cursor is over an anchor
        char_format = cursor.charFormat()
        anchor_href = char_format.anchorHref() if char_format else ""

        if anchor_href and ("wikilink://" in anchor_href or "wikicreate://" in anchor_href):
            # Extract article name
            article_name = anchor_href.split("://", 1)[-1] if "://" in anchor_href else ""
            if article_name:
                global_pos = self.preview_browser.viewport().mapToGlobal(pos)
                self._hover_tracker.on_mouse_move(article_name, (global_pos.x(), global_pos.y()))
                return

        # Not over a link
        self._hover_tracker.on_mouse_move(None, (0, 0))

    def _on_hover_timeout(self) -> None:
        if self._hover_article_name:
            self._tooltip.show_for_article(
                self._hover_article_name, self._hover_global_pos
            )

    # ------------------------------------------------------------------
    # Link autocomplete
    # ------------------------------------------------------------------

    def _on_content_autocomplete(self) -> None:
        """Detect [[ typing and show autocomplete popup."""
        cursor = self.content_edit.textCursor()
        pos = cursor.position()
        text = self.content_edit.toPlainText()

        # Look backwards for [[ before cursor
        if pos < 2:
            self._dismiss_autocomplete()
            return

        # Find the last [[ before cursor
        before = text[:pos]
        last_open = before.rfind("[[")

        if last_open == -1 or pos - last_open > 30:
            self._dismiss_autocomplete()
            return

        # Check if there's a ]] that closes it
        after = text[last_open + 2:pos]
        if "]]" in after:
            self._dismiss_autocomplete()
            return

        # Extract the partial query
        query = before[last_open + 2:]
        # Check if query has a pipe (display text)
        pipe_idx = query.find("|")
        if pipe_idx >= 0:
            query = query[:pipe_idx]

        # Clean and show
        query = query.strip()
        if query and query != query:
            self._dismiss_autocomplete()
            return

        # Get cursor position for popup placement
        cursor_rect = self.content_edit.cursorRect(cursor)
        global_pos = self.content_edit.viewport().mapToGlobal(
            cursor_rect.bottomLeft()
        )

        self._autocomplete_active = True
        self._autocomplete_query = query
        self._link_autocomplete.show_for_query(query, cursor_rect, global_pos)

        # Override key press events while autocomplete is active
        if self._autocomplete_active:
            self.content_edit.keyPressEvent = self._content_key_press_with_autocomplete

    def _dismiss_autocomplete(self) -> None:
        """Hide the autocomplete popup."""
        if self._autocomplete_active:
            self._link_autocomplete.hide()
            self._autocomplete_active = False
            self._autocomplete_query = ""
            self.content_edit.keyPressEvent = self._content_key_press_default

    def _content_key_press_with_autocomplete(self, event) -> None:
        """Handle key events while autocomplete is visible."""
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import Qt

        key = event.key()
        if key == Qt.Key.Key_Down:
            self._link_autocomplete.select_next()
            event.accept()
        elif key == Qt.Key.Key_Up:
            self._link_autocomplete.select_prev()
            event.accept()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            selected = self._link_autocomplete.get_selected_title()
            if selected:
                self._insert_wiki_link(selected)
                event.accept()
                return
            self._dismiss_autocomplete()
            self._content_key_press_default(event)
        elif key == Qt.Key.Key_Escape:
            self._dismiss_autocomplete()
            event.accept()
        else:
            self._content_key_press_default(event)

    def _content_key_press_default(self, event) -> None:
        """Default key press handler (no autocomplete)."""
        QPlainTextEdit.keyPressEvent(self.content_edit, event)

    def _insert_wiki_link(self, article_title: str) -> None:
        """Replace the [[partial with [[Full Title]]."""
        cursor = self.content_edit.textCursor()
        text = self.content_edit.toPlainText()
        pos = cursor.position()

        # Find the [[ that started this
        before = text[:pos]
        last_open = before.rfind("[[")

        if last_open == -1:
            self._dismiss_autocomplete()
            return

        # Select from [[ to current position
        cursor.setPosition(last_open)
        cursor.setPosition(pos, cursor.MoveMode.KeepAnchor)
        cursor.insertText(f"[[{article_title}]]")
        self._dismiss_autocomplete()

    def _on_content_edited(self) -> None:
        if self._article:
            self.save_indicator.setText("✎ Unsaved changes")
            self.content_changed.emit()

    def _on_edit_mode_toggled(self, checked: bool) -> None:
        if checked:
            self.content_edit.show()
            self.preview_browser.hide()
            self.edit_btn.setChecked(True)
            self.preview_btn.setChecked(False)

    def _on_preview_mode_toggled(self, checked: bool) -> None:
        if checked:
            # Sync preview from current editor content
            self.preview_browser.set_wiki_content(self.content_edit.toPlainText())
            self.content_edit.hide()
            self.preview_browser.show()
            self.edit_btn.setChecked(False)
            self.preview_btn.setChecked(True)

    def _on_link_navigated(self, article_id: str) -> None:
        """Handle clicking a wiki link in preview mode."""
        self.link_navigated.emit(article_id)

    def set_edit_mode(self, editing: bool) -> None:
        """Toggle edit mode."""
        self._edit_mode = editing
        self.title_edit.setReadOnly(not editing)
        self.content_edit.setReadOnly(not editing)