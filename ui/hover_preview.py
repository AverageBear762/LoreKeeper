"""
World Garden — Floating Hover Tooltips.

When hovering over a wiki link (in the article view or on the map),
displays a custom frameless floating widget near the cursor with
the article's portrait, summary, and key metadata fields.

Key features:
- 200ms hover delay before showing
- Fast DB lookup (<50ms)
- Smooth fade in/out (opacity animation)
- Never obstructs reading (intelligent positioning)
- User-customizable visible fields per template
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import (
    QEvent,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    Signal,
    Property,
)
from PySide6.QtGui import (
    QCursor,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPixmap,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.models import Article, ArticleTemplate


# ======================================================================
#  HoverPreviewWidget — the floating tooltip
# ======================================================================

class HoverPreviewWidget(QFrame):
    """Floating frameless tooltip that displays article preview information."""

    PREVIEW_WIDTH = 320
    PREVIEW_MAX_HEIGHT = 280

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(self.PREVIEW_WIDTH)
        self.setMaximumWidth(self.PREVIEW_WIDTH)
        self.setMaximumHeight(self.PREVIEW_MAX_HEIGHT)

        self._opacity = 1.0
        self._fade_anim: Optional[QPropertyAnimation] = None

        # Container with rounded borders and shadow effect
        self._container = QFrame(self)
        self._container.setObjectName("TooltipContainer")
        self._container.setStyleSheet("""
            #TooltipContainer {
                background: palette(Base);
                border: 1px solid palette(Midlight);
                border-radius: 8px;
                padding: 8px;
            }
        """)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(6)

        # Top row: portrait + title + type
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.portrait_label = QLabel()
        self.portrait_label.setFixedSize(64, 64)
        self.portrait_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.portrait_label.setStyleSheet("""
            QLabel {
                border: 1px solid palette(Midlight);
                border-radius: 6px;
                background: palette(AlternateBase);
            }
        """)
        top_row.addWidget(self.portrait_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: palette(Text);"
        )
        self.title_label.setWordWrap(True)
        title_col.addWidget(self.title_label)

        self.type_label = QLabel()
        self.type_label.setStyleSheet(
            "font-size: 11px; color: palette(Link); font-weight: 500;"
        )
        title_col.addWidget(self.type_label)

        top_row.addLayout(title_col, 1)
        container_layout.addLayout(top_row)

        # Metadata fields
        self.fields_container = QVBoxLayout()
        self.fields_container.setSpacing(2)
        container_layout.addLayout(self.fields_container)

        # Summary line
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(
            "font-size: 12px; color: palette(Text); line-height: 1.4;"
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setMaximumHeight(60)
        container_layout.addWidget(self.summary_label)

        container_layout.addStretch(1)

        # Outer layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)
        outer_layout.addWidget(self._container)

        self._article: Optional[Article] = None
        self._template: Optional[ArticleTemplate] = None
        self._hide_pending = False

    # ----------------------------------------------------------------
    # Custom opacity property for fade animation
    # ----------------------------------------------------------------

    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self.setWindowOpacity(value)

    opacity = Property(float, _get_opacity, _set_opacity)

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def show_for_article(
        self,
        article_name: str,
        global_pos: tuple[int, int],
    ) -> None:
        """Load article preview and show tooltip near *global_pos*."""
        article = crud.get_article_by_title(article_name)
        if not article:
            self.hide()
            return

        self._article = article
        self._template = crud.get_template_by_type_name(article.article_type)

        self._populate(article)
        self._position_near(global_pos)
        self._fade_in()

    def _populate(self, article: Article) -> None:
        """Fill the tooltip widgets with article data."""
        self.title_label.setText(article.title or "Untitled")
        self.type_label.setText(article.article_type)

        # Portrait / image
        portrait_path = article.template_fields.get("portrait", "") or \
                        article.template_fields.get("image", "") or \
                        article.template_fields.get("map_image", "") or ""
        if portrait_path and os.path.isfile(portrait_path):
            pix = QPixmap(portrait_path)
            if not pix.isNull():
                self.portrait_label.setPixmap(
                    pix.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                )
                self.portrait_label.setText("")
            else:
                self.portrait_label.setText("🖼")
        else:
            self.portrait_label.setText(self._type_icon(article.article_type))

        # Metadata fields — read from template or custom field config
        visible_fields = self._get_visible_fields(article.article_type)

        # Clear old field widgets
        self._clear_layout(self.fields_container)

        for field_name in visible_fields:
            value = article.template_fields.get(field_name)
            if value is None or value == "" or value == 0:
                continue
            label_text = field_name.replace("_", " ").title()
            value_str = str(value)
            if len(value_str) > 60:
                value_str = value_str[:57] + "..."

            row = QHBoxLayout()
            row.setSpacing(6)
            name_lbl = QLabel(f"{label_text}:")
            name_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: palette(Text);")
            name_lbl.setMaximumWidth(100)
            row.addWidget(name_lbl)

            val_lbl = QLabel(value_str)
            val_lbl.setStyleSheet("font-size: 11px; color: palette(Text);")
            val_lbl.setWordWrap(True)
            row.addWidget(val_lbl, 1)
            self.fields_container.addLayout(row)

        # Summary (first 120 chars of content)
        summary = article.content[:150].strip().replace("\n", " ")
        if len(article.content) > 150:
            summary += "..."
        self.summary_label.setText(summary if summary else "")

    def _get_visible_fields(self, article_type: str) -> list[str]:
        """Return the list of field names to display in the preview.

        Checks for a saved configuration per template. Falls back to
        the first 4 fields of the template definition.
        """
        # Check for saved config
        config_key = f"_preview_fields_{article_type}"
        if hasattr(self, config_key):
            return getattr(self, config_key)

        # Default: first 4 fields from the template
        template = self._template
        if template and template.field_definitions:
            names = [fd.name for fd in template.field_definitions[:4]]
        else:
            names = []
        return names

    def configure_preview_fields(
        self, article_type: str, field_names: list[str]
    ) -> None:
        """Set which fields are shown in the hover preview for a type."""
        setattr(self, f"_preview_fields_{article_type}", field_names)

    # ----------------------------------------------------------------
    # Positioning
    # ----------------------------------------------------------------

    def _position_near(self, global_pos: tuple[int, int]) -> None:
        """Position the tooltip near the cursor, avoiding screen edges."""
        x, y = global_pos
        screen = self.screen()
        if screen:
            screen_geom = screen.geometry()
            # Offset below and to the right of cursor
            x += 16
            y += 16
            # Don't go off screen
            if x + self.PREVIEW_WIDTH > screen_geom.right():
                x = global_pos[0] - self.PREVIEW_WIDTH - 8
            if y + self.PREVIEW_MAX_HEIGHT > screen_geom.bottom():
                y = global_pos[1] - self.PREVIEW_MAX_HEIGHT - 8
            if x < screen_geom.left():
                x = screen_geom.left() + 4
            if y < screen_geom.top():
                y = screen_geom.top() + 4

        self.move(x, y)

    # ----------------------------------------------------------------
    # Animations
    # ----------------------------------------------------------------

    def _fade_in(self) -> None:
        """Fade in the tooltip with opacity animation."""
        self._stop_fade()
        self.setWindowOpacity(0.0)
        self.show()
        self._fade_anim = QPropertyAnimation(self, b"opacity")
        self._fade_anim.setDuration(120)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(0.95)
        self._fade_anim.start()

    def fade_out(self) -> None:
        """Fade out and hide."""
        self._stop_fade()
        self._fade_anim = QPropertyAnimation(self, b"opacity")
        self._fade_anim.setDuration(100)
        self._fade_anim.setStartValue(self._opacity)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.hide)
        self._fade_anim.start()

    def _stop_fade(self) -> None:
        if self._fade_anim:
            self._fade_anim.stop()
            self._fade_anim.deleteLater()
            self._fade_anim = None

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item:
                if item.layout():
                    while item.layout().count():
                        child = item.layout().takeAt(0)
                        if child and child.widget():
                            child.widget().deleteLater()
                if item.widget():
                    item.widget().deleteLater()

    @staticmethod
    def _type_icon(article_type: str) -> str:
        icons = {
            "Character": "🧑",
            "Location": "📍",
            "Faction": "⚜",
            "Item": "⚔",
            "Creature": "🐉",
            "Event": "📅",
            "Religion": "✝",
            "Species": "🧬",
            "Settlement": "🏘",
            "Nation": "🏰",
        }
        return icons.get(article_type, "📄")


# ======================================================================
#  HoverTracker — manages hover detection for tooltips
# ======================================================================

class HoverTracker:
    """Tracks mouse hover over wiki links and triggers the tooltip.

    Attach to a QTextBrowser by connecting its mouse-move events.
    Uses a QTimer for the 200ms hover delay.
    """

    def __init__(self, tooltip: HoverPreviewWidget) -> None:
        self._tooltip = tooltip
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(200)  # 200ms hover delay
        self._hover_timer.timeout.connect(self._on_hover_timeout)

        self._current_article_name: Optional[str] = None
        self._last_global_pos: tuple[int, int] = (0, 0)
        self._is_hovering = False

    def start(self) -> None:
        """Call this when the tracker is ready."""
        pass

    def stop(self) -> None:
        """Cancel any pending hover and hide tooltip."""
        self._hover_timer.stop()
        self._tooltip.fade_out()
        self._is_hovering = False
        self._current_article_name = None

    def on_mouse_move(
        self, article_name: Optional[str], global_pos: tuple[int, int]
    ) -> None:
        """Called on mouse move events — track hover over links."""
        self._last_global_pos = global_pos

        if article_name:
            if article_name != self._current_article_name:
                # New link hovered — restart timer
                self._hover_timer.stop()
                self._tooltip.fade_out()
                self._current_article_name = article_name
                self._is_hovering = True
                self._hover_timer.start()
        else:
            # Not hovering a link
            if self._is_hovering:
                self.stop()

    def _on_hover_timeout(self) -> None:
        """Hover delay elapsed — show the tooltip."""
        if self._current_article_name:
            self._tooltip.show_for_article(
                self._current_article_name, self._last_global_pos
            )

    @property
    def tooltip(self) -> HoverPreviewWidget:
        return self._tooltip