"""
World Garden — Theme Manager.

Provides light and dark palette-based themes with rich custom QSS stylesheets.
Switching is instant and applies to the entire QApplication.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# QPalette colours for Light and Dark modes
# ---------------------------------------------------------------------------

def _light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(248, 249, 250))           # --bg
    p.setColor(QPalette.WindowText, QColor(33, 37, 41))          # --fg
    p.setColor(QPalette.Base, QColor(255, 255, 255))             # card bg
    p.setColor(QPalette.AlternateBase, QColor(233, 236, 239))    # hover
    p.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    p.setColor(QPalette.ToolTipText, QColor(33, 37, 41))
    p.setColor(QPalette.Text, QColor(33, 37, 41))
    p.setColor(QPalette.Button, QColor(233, 236, 239))
    p.setColor(QPalette.ButtonText, QColor(33, 37, 41))
    p.setColor(QPalette.BrightText, QColor(220, 53, 69))
    p.setColor(QPalette.Link, QColor(13, 110, 253))
    p.setColor(QPalette.Highlight, QColor(13, 110, 253))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    # Disabled
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(173, 181, 189))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(173, 181, 189))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(173, 181, 189))
    return p


def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(25, 25, 35))              # --bg
    p.setColor(QPalette.WindowText, QColor(220, 220, 230))       # --fg
    p.setColor(QPalette.Base, QColor(35, 35, 48))                # card bg
    p.setColor(QPalette.AlternateBase, QColor(45, 45, 58))       # hover
    p.setColor(QPalette.ToolTipBase, QColor(35, 35, 48))
    p.setColor(QPalette.ToolTipText, QColor(220, 220, 230))
    p.setColor(QPalette.Text, QColor(220, 220, 230))
    p.setColor(QPalette.Button, QColor(45, 45, 58))
    p.setColor(QPalette.ButtonText, QColor(220, 220, 230))
    p.setColor(QPalette.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.Link, QColor(100, 160, 255))
    p.setColor(QPalette.Highlight, QColor(80, 110, 200))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    # Disabled
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(100, 100, 120))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(100, 100, 120))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(100, 100, 120))
    return p


# ---------------------------------------------------------------------------
# QSS stylesheet overlays
# ---------------------------------------------------------------------------

LIGHT_STYLESHEET = """
/* === World Garden Light Theme QSS === */

/* Main window & panels */
QMainWindow { background-color: #f8f9fa; }

/* Sidebar */
#SidebarPanel {
    background-color: #ffffff;
    border-right: 1px solid #dee2e6;
}
#SidebarPanel QLabel#SectionHeader {
    font-size: 11px;
    font-weight: 600;
    color: #6c757d;
    text-transform: uppercase;
    padding: 8px 12px 2px 12px;
}
#SidebarPanel QLabel#SidebarLink {
    color: #0d6efd;
    font-weight: 500;
    padding: 6px 16px;
}
#SidebarPanel QLabel#SidebarLink:hover {
    background-color: #e9ecef;
    border-radius: 4px;
}

/* Search bar */
#SearchBar {
    border: 1px solid #ced4da;
    border-radius: 6px;
    padding: 6px 10px;
    background: #ffffff;
    font-size: 13px;
    min-height: 22px;
}
#SearchBar:focus {
    border-color: #0d6efd;
    outline: none;
}

/* Tree widget */
QTreeWidget {
    background: transparent;
    border: none;
    font-size: 13px;
    outline: none;
}
QTreeWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QTreeWidget::item:hover {
    background: #e9ecef;
}
QTreeWidget::item:selected {
    background: #0d6efd;
    color: #ffffff;
}

/* Toolbar */
QToolBar {
    background: #ffffff;
    border-bottom: 1px solid #dee2e6;
    padding: 4px;
    spacing: 4px;
}
QToolBar QToolButton {
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
}
QToolBar QToolButton:hover {
    background: #e9ecef;
}
QToolBar QToolButton:pressed {
    background: #dee2e6;
}

/* Status bar */
QStatusBar {
    background: #e9ecef;
    border-top: 1px solid #dee2e6;
    font-size: 12px;
    color: #6c757d;
}

/* Article view area */
#ArticleArea {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 16px;
}

/* Article title */
#ArticleTitle {
    font-size: 24px;
    font-weight: 600;
    color: #212529;
    padding: 0px;
    border: none;
    background: transparent;
}

/* Scroll bars */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #ced4da;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #adb5bd;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #ced4da;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #adb5bd;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Splitter */
QSplitter::handle {
    background: #dee2e6;
    width: 1px;
    height: 1px;
}

/* Tooltip */
QToolTip {
    background: #ffffff;
    color: #212529;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}

/* Menu bar */
QMenuBar {
    background: #ffffff;
    border-bottom: 1px solid #dee2e6;
    padding: 2px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #e9ecef;
}
QMenu {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #0d6efd;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #dee2e6;
    margin: 4px 8px;
}
"""


DARK_STYLESHEET = """
/* === World Garden Dark Theme QSS === */

QMainWindow { background-color: #191923; }

#SidebarPanel {
    background-color: #232330;
    border-right: 1px solid #3a3a4a;
}
#SidebarPanel QLabel#SectionHeader {
    font-size: 11px;
    font-weight: 600;
    color: #8b8b9a;
    text-transform: uppercase;
    padding: 8px 12px 2px 12px;
}
#SidebarPanel QLabel#SidebarLink {
    color: #64a0ff;
    font-weight: 500;
    padding: 6px 16px;
}
#SidebarPanel QLabel#SidebarLink:hover {
    background-color: #2d2d3a;
    border-radius: 4px;
}

#SearchBar {
    border: 1px solid #4a4a5a;
    border-radius: 6px;
    padding: 6px 10px;
    background: #2d2d3a;
    color: #dcdce6;
    font-size: 13px;
    min-height: 22px;
}
#SearchBar:focus {
    border-color: #64a0ff;
}

QTreeWidget {
    background: transparent;
    border: none;
    color: #dcdce6;
    font-size: 13px;
    outline: none;
}
QTreeWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QTreeWidget::item:hover {
    background: #2d2d3a;
}
QTreeWidget::item:selected {
    background: #506ec8;
    color: #ffffff;
}

QToolBar {
    background: #232330;
    border-bottom: 1px solid #3a3a4a;
    padding: 4px;
    spacing: 4px;
}
QToolBar QToolButton {
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
    color: #dcdce6;
}
QToolBar QToolButton:hover {
    background: #2d2d3a;
}
QToolBar QToolButton:pressed {
    background: #3a3a4a;
}

QStatusBar {
    background: #2d2d3a;
    border-top: 1px solid #3a3a4a;
    font-size: 12px;
    color: #8b8b9a;
}

#ArticleArea {
    background: #232330;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 16px;
}

#ArticleTitle {
    font-size: 24px;
    font-weight: 600;
    color: #dcdce6;
    padding: 0px;
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #4a4a5a;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #5a5a6a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #4a4a5a;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #5a5a6a;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QSplitter::handle {
    background: #3a3a4a;
    width: 1px;
    height: 1px;
}

QToolTip {
    background: #232330;
    color: #dcdce6;
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}

QMenuBar {
    background: #232330;
    border-bottom: 1px solid #3a3a4a;
    padding: 2px;
    color: #dcdce6;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #2d2d3a;
}
QMenu {
    background: #232330;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 4px;
    color: #dcdce6;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #506ec8;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #3a3a4a;
    margin: 4px 8px;
}

/* Text edit / editor area */
QPlainTextEdit, QTextEdit {
    background: #1e1e2c;
    color: #dcdce6;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 8px;
    font-size: 14px;
}
"""


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

class ThemeManager:
    """Manages light/dark theme switching for the entire application."""

    LIGHT = "light"
    DARK = "dark"

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._current_theme: str = self.LIGHT
        self._on_theme_changed: list[callable] = []

    @property
    def current_theme(self) -> str:
        return self._current_theme

    def switch_to(self, theme: str) -> None:
        """Apply the given theme (light or dark) to the whole application."""
        if theme not in (self.LIGHT, self.DARK):
            return
        self._current_theme = theme
        if theme == self.DARK:
            self._app.setStyle("Fusion")
            self._app.setPalette(_dark_palette())
            self._app.setStyleSheet(DARK_STYLESHEET)
        else:
            self._app.setStyle("Fusion")
            self._app.setPalette(_light_palette())
            self._app.setStyleSheet(LIGHT_STYLESHEET)

        for cb in self._on_theme_changed:
            cb(theme)

    def toggle(self) -> str:
        """Toggle between light and dark. Returns the new theme name."""
        new_theme = self.DARK if self._current_theme == self.LIGHT else self.LIGHT
        self.switch_to(new_theme)
        return new_theme

    def on_theme_changed(self, callback: callable) -> None:
        """Register a callable that is called with the new theme name."""
        self._on_theme_changed.append(callback)