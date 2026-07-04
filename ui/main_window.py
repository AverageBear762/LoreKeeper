"""
World Garden — Main Window.

Top-level application window with:
- Menu bar (File, Edit, View, Help)
- Toolbar (New, Save, Undo, Redo, Theme toggle, Search)
- Sidebar with search, category tree, favorites, recent, travel map link
- Central article view area with read/edit modes
- Status bar
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QSize, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.manager import DatabaseManager
from database.models import Article
from ui.article_view import ArticleView
from ui.backup_manager import export_json_dialog, import_json_dialog, backup_database_dialog
from ui.search_dialog import SearchDialog
from ui.sidebar import Sidebar
from ui.template_editor import TemplateManagementDialog
from ui.theme import ThemeManager
from ui.travel_map import TravelMapWidget


class MainWindow(QMainWindow):
    """World Garden main application window."""

    APP_TITLE = "World Garden — Worldbuilding Wiki"

    def __init__(self, theme_mgr: ThemeManager) -> None:
        super().__init__()
        self.theme = theme_mgr
        self._autosave_timer = QTimer(self)
        self._db: Optional[DatabaseManager] = None
        self._search_dialog: Optional[SearchDialog] = None

        self.setWindowTitle(self.APP_TITLE)
        self.setMinimumSize(1024, 680)
        self.resize(1280, 800)

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Autosave every 30 seconds
        self._autosave_timer.setInterval(30_000)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menubar = self.menuBar()

        # -- File --
        file_menu = menubar.addMenu("&File")
        self.act_new = QAction("&New Article", self)
        self.act_new.setShortcut(QKeySequence("Ctrl+N"))
        self.act_new.triggered.connect(self._on_new_article)
        file_menu.addAction(self.act_new)

        self.act_save = QAction("&Save", self)
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.triggered.connect(self._on_save)
        file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Save &As...", self)
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.triggered.connect(self._on_save_as)
        file_menu.addAction(self.act_save_as)

        file_menu.addSeparator()

        self.act_export_json = QAction("&Export JSON Snapshot...", self)
        self.act_export_json.triggered.connect(self._on_export_json)
        file_menu.addAction(self.act_export_json)

        self.act_import_json = QAction("&Import JSON Snapshot...", self)
        self.act_import_json.triggered.connect(self._on_import_json)
        file_menu.addAction(self.act_import_json)

        file_menu.addSeparator()

        self.act_backup_db = QAction("&Backup Database...", self)
        self.act_backup_db.triggered.connect(self._on_backup_db)
        file_menu.addAction(self.act_backup_db)

        self.act_open_db = QAction("&Open Database...", self)
        self.act_open_db.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open_db.triggered.connect(self._on_open_database)
        file_menu.addAction(self.act_open_db)

        file_menu.addSeparator()

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_quit.triggered.connect(self.close)
        file_menu.addAction(self.act_quit)

        # -- Edit --
        edit_menu = menubar.addMenu("&Edit")
        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        edit_menu.addAction(self.act_undo)

        self.act_redo = QAction("&Redo", self)
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        edit_menu.addAction(self.act_redo)

        edit_menu.addSeparator()

        self.act_search = QAction("&Search Articles...", self)
        self.act_search.setShortcut(QKeySequence("Ctrl+F"))
        self.act_search.triggered.connect(self._on_global_search_dialog)
        edit_menu.addAction(self.act_search)

        edit_menu.addSeparator()

        self.act_delete = QAction("&Delete Article", self)
        self.act_delete.setShortcut(QKeySequence("Del"))
        self.act_delete.triggered.connect(self._on_delete_article)
        edit_menu.addAction(self.act_delete)

        # -- View --
        view_menu = menubar.addMenu("&View")
        self.act_toggle_theme = QAction("Toggle &Dark Mode", self)
        self.act_toggle_theme.setShortcut(QKeySequence("Ctrl+D"))
        self.act_toggle_theme.triggered.connect(self._on_toggle_theme)
        view_menu.addAction(self.act_toggle_theme)

        view_menu.addSeparator()

        self.act_travel_map = QAction("&Travel Map", self)
        self.act_travel_map.setShortcut(QKeySequence("Ctrl+M"))
        self.act_travel_map.triggered.connect(self._on_travel_map)
        view_menu.addAction(self.act_travel_map)

        # -- Help --
        help_menu = menubar.addMenu("&Help")

        # -- Templates menu --
        templates_menu = menubar.addMenu("&Templates")
        self.act_manage_templates = QAction("&Manage Templates...", self)
        self.act_manage_templates.triggered.connect(self._on_manage_templates)
        templates_menu.addAction(self.act_manage_templates)
        templates_menu.addSeparator()
        self.act_seed_templates = QAction("&Restore Default Templates", self)
        self.act_seed_templates.triggered.connect(self._on_seed_templates)
        templates_menu.addAction(self.act_seed_templates)

        # -- Help --
        self.act_about = QAction("&About World Garden", self)
        self.act_about.triggered.connect(self._on_about)
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(self.font().pointSize() * 2, self.font().pointSize() * 2))
        self.addToolBar(toolbar)

        # Tool buttons
        self.tb_new = QPushButton("📄 New")
        self.tb_new.setObjectName("ToolBtn")
        self.tb_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tb_new.clicked.connect(self._on_new_article)
        toolbar.addWidget(self.tb_new)

        self.tb_save = QPushButton("💾 Save")
        self.tb_save.setObjectName("ToolBtn")
        self.tb_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tb_save.clicked.connect(self._on_save)
        toolbar.addWidget(self.tb_save)

        toolbar.addSeparator()

        self.tb_undo = QPushButton("↩ Undo")
        self.tb_undo.setObjectName("ToolBtn")
        self.tb_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tb_undo.clicked.connect(self._on_undo)
        toolbar.addWidget(self.tb_undo)

        self.tb_redo = QPushButton("↪ Redo")
        self.tb_redo.setObjectName("ToolBtn")
        self.tb_redo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tb_redo.clicked.connect(self._on_redo)
        toolbar.addWidget(self.tb_redo)

        toolbar.addSeparator()

        self.tb_theme = QPushButton("🌓 Theme")
        self.tb_theme.setObjectName("ToolBtn")
        self.tb_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tb_theme.clicked.connect(self._on_toggle_theme)
        toolbar.addWidget(self.tb_theme)

        toolbar.addSeparator()

        self.tb_map = QPushButton("🗺 Map")
        self.tb_map.setObjectName("ToolBtn")
        self.tb_map.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tb_map.clicked.connect(self._on_travel_map)
        toolbar.addWidget(self.tb_map)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Quick search in toolbar
        self.toolbar_search = QPushButton("🔍 Search")
        self.toolbar_search.setObjectName("ToolBtn")
        self.toolbar_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toolbar_search.clicked.connect(lambda: self.sidebar.search_bar.setFocus())
        toolbar.addWidget(self.toolbar_search)

    def _build_central(self) -> None:
        """Build the main content area with sidebar + tabbed views."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for resizable sidebar/content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        # Sidebar (always visible)
        self.sidebar = Sidebar()
        splitter.addWidget(self.sidebar)

        # Right side: tab widget with Articles and Travel Map tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Tab bar for switching between views
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBarAutoHide(False)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Tab 0: Articles
        self.article_view = ArticleView()
        self.tab_widget.addTab(self.article_view, "📄 Articles")

        # Tab 1: Travel Map
        self.travel_map = TravelMapWidget()
        self.tab_widget.addTab(self.travel_map, "🗺 Travel Map")

        right_layout.addWidget(self.tab_widget)

        splitter.addWidget(right_panel)

        # Set proportions: 260px sidebar, rest for content
        splitter.setSizes([260, 1020])

        layout.addWidget(splitter)

        # Connect signals
        self.sidebar.article_selected.connect(self.article_view.load_article_by_id)
        self.sidebar.search_requested.connect(self._on_global_search)
        self.sidebar.travel_map_requested.connect(self._switch_to_travel_map)
        self.sidebar.create_article_requested.connect(self._on_new_article)
        self.sidebar.delete_article_requested.connect(self._on_delete_article_by_id)

        # Travel map signals
        self.travel_map.article_navigated.connect(self._on_travel_map_navigate)
        self.travel_map.article_edit_requested.connect(self._on_travel_map_edit)

        # Wiki link signals from article view
        self.article_view.link_navigated.connect(self._on_article_link_navigated)
        self.article_view.link_creation_requested.connect(self._on_article_link_creation)

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # DB status
        self.db_status_label = QLabel("")
        self.db_status_label.setStyleSheet("color: #6c757d; margin-right: 8px;")
        self.status_bar.addPermanentWidget(self.db_status_label)

    def _setup_shortcuts(self) -> None:
        """Additional keyboard shortcuts beyond menu actions."""
        # Escape to blur search
        from PySide6.QtGui import QShortcut
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self.sidebar.clear_search)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_database(self, db_path: str) -> None:
        """Open a World Garden database file and refresh the UI."""
        db = DatabaseManager()
        db.open(db_path)
        self._db = db
        self._update_db_status()
        self.refresh_ui()

    def refresh_ui(self) -> None:
        """Refresh all sidebar lists and tree."""
        self.sidebar.refresh_favorites()
        self.sidebar.refresh_recent()
        self.sidebar.refresh_category_tree()
        self.status_label.setText("Database loaded")

    # ------------------------------------------------------------------
    # Slots — actions
    # ------------------------------------------------------------------

    def _on_new_article(self) -> None:
        """Create a new article — first select its type."""
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QVBoxLayout, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("New Article")
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select article type:"))

        combo = QComboBox()
        types = crud.list_all_article_types()
        combo.addItems(types)
        combo.setCurrentText("Location")
        layout.addWidget(combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            article_type = combo.currentText()
            article = self.article_view.create_new(article_type)
            self.status_label.setText(f"New {article_type}: {article.id[:8]}...")
            self.sidebar.refresh_recent()
            self.sidebar.refresh_favorites()
            self.sidebar.refresh_category_tree()

    def _on_save(self) -> None:
        """Save the current article."""
        if self.article_view.save():
            self.status_label.setText("Article saved")
            self.sidebar.refresh_recent()
            self.sidebar.refresh_category_tree()
        else:
            self.status_label.setText("Save failed")

    def _on_save_as(self) -> None:
        """Export the current article content as a Markdown file."""
        article = self.article_view.current_article
        if not article:
            self.status_label.setText("No article to export")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Article",
            f"{article.title.replace(' ', '_')}.md",
            "Markdown (*.md);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w") as f:
                    f.write(f"# {article.title}\n\n{article.content}")
                self.status_label.setText(f"Exported to {Path(path).name}")
            except OSError as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def _on_open_database(self) -> None:
        """Open a different database file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open World Garden Database",
            str(Path.home()),
            "SQLite Database (*.db *.sqlite);;All Files (*)",
        )
        if path:
            try:
                self.open_database(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open database:\n{e}")

    def _on_delete_article(self) -> None:
        """Delete the currently displayed article."""
        article = self.article_view.current_article
        if not article:
            return

        result = QMessageBox.question(
            self,
            "Delete Article",
            f'Are you sure you want to delete "{article.title}"?\n'
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._perform_delete_article(article.id, article.title)

    def _on_delete_article_by_id(self, article_id: str) -> None:
        """Delete an article by id (from sidebar context menu)."""
        article = crud.get_article(article_id)
        if not article:
            return

        result = QMessageBox.question(
            self,
            "Delete Article",
            f'Are you sure you want to delete "{article.title}"?\n'
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._perform_delete_article(article.id, article.title)

    def _perform_delete_article(self, article_id: str, title: str) -> None:
        """Common delete logic used by both delete paths."""
        crud.delete_article(article_id)
        if (self.article_view.current_article
                and self.article_view.current_article.id == article_id):
            self.article_view.clear()
        self.status_label.setText(f"Deleted: {title}")
        self.sidebar.refresh_favorites()
        self.sidebar.refresh_recent()
        self.sidebar.refresh_category_tree()

    def _on_toggle_theme(self) -> None:
        new_theme = self.theme.toggle()
        self.act_toggle_theme.setText(
            "Toggle &Light Mode" if new_theme == "dark" else "Toggle &Dark Mode"
        )
        self.status_label.setText(f"Switched to {new_theme} theme")

    def _on_travel_map(self) -> None:
        """Switch to the Travel Map tab."""
        self._switch_to_travel_map()

    def _switch_to_travel_map(self) -> None:
        """Switch to the travel map tab."""
        self.tab_widget.setCurrentIndex(1)
        self.travel_map.reload()
        self.status_label.setText("🗺 Travel Map")

    def _switch_to_article_view(self) -> None:
        """Switch to the articles tab."""
        self.tab_widget.setCurrentIndex(0)
        self.status_label.setText("Wiki View")

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab switch — reload travel map data when switching to it."""
        if index == 1:
            self.travel_map.reload()
            self.status_label.setText("🗺 Travel Map")
        else:
            self.status_label.setText("Wiki View")

    def _on_travel_map_navigate(self, article_id: str) -> None:
        """Navigate from travel map to an article."""
        self._switch_to_article_view()
        self.article_view.load_article_by_id(article_id)

    def _on_travel_map_edit(self, article_id: str) -> None:
        """Open an article for editing from the travel map."""
        self._switch_to_article_view()
        self.article_view.load_article_by_id(article_id)

    def _on_manage_templates(self) -> None:
        """Open the template management dialog."""
        dialog = TemplateManagementDialog(self)
        dialog.templates_changed.connect(self.sidebar.refresh_category_tree)
        dialog.exec()
        self.sidebar.refresh_category_tree()

    def _on_seed_templates(self) -> None:
        """Restore default templates."""
        from ui.default_templates import seed_default_templates
        result = QMessageBox.question(
            self,
            "Restore Default Templates",
            "This will update existing default templates (Character, Item, Location, Creature).\n"
            "Custom templates will not be affected.\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            count = len(seed_default_templates(overwrite=True))
            self.status_label.setText(f"Restored {count} default templates")
            self.sidebar.refresh_category_tree()

    def _on_undo(self) -> None:
        """Undo the last edit in the article view."""
        self.article_view.content_edit.undo()
        self.status_label.setText("Undo")

    def _on_redo(self) -> None:
        """Redo the last undone edit."""
        self.article_view.content_edit.redo()
        self.status_label.setText("Redo")

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About World Garden",
            "<h2>World Garden</h2>"
            "<p>Version 0.1.0</p>"
            "<p>A fully offline, local-first worldbuilding database and wiki<br>"
            "for tabletop RPG game masters, writers, and creators.</p>"
            "<p>Built with Python, PySide6, and SQLite FTS5.</p>"
            "<p>© 2026 World Garden Team</p>",
        )

    def _on_global_search_dialog(self) -> None:
        """Open the global search dialog."""
        if self._search_dialog is None:
            self._search_dialog = SearchDialog(self)
            self._search_dialog.article_selected.connect(
                self.article_view.load_article_by_id
            )
        self._search_dialog.focus_search()
        self._search_dialog.show()
        self._search_dialog.raise_()

    def _on_export_json(self) -> None:
        """Export JSON snapshot."""
        export_json_dialog(self)

    def _on_import_json(self) -> None:
        """Import JSON snapshot."""
        import_json_dialog(self)

    def _on_backup_db(self) -> None:
        """Backup database."""
        backup_database_dialog(self)

    def _on_global_search(self, query: str) -> None:
        """Perform a full-text search and show results."""
        results = crud.search_articles(query)
        if not results:
            self.status_label.setText(f"No results for '{query}'")
            self.article_view.show_placeholder()
            return

        self.status_label.setText(f"Found {len(results)} result(s) for '{query}'")
        # Load the first result
        self.article_view.load_article(results[0])

    def _on_article_link_navigated(self, article_id: str) -> None:
        """Handle a wiki link click in the article preview — navigate to that article."""
        article = crud.get_article(article_id)
        if article:
            self.article_view.load_article(article)
            self.status_label.setText(f"Navigated to: {article.title}")
        else:
            self.status_label.setText(f"Article not found: {article_id[:8]}...")

    def _on_article_link_creation(self, article_name: str) -> None:
        """Handle clicking a link to a non-existent article — offer to create it."""
        result = QMessageBox.question(
            self,
            "Create Article",
            f'The article "{article_name}" does not exist yet.\n\n'
            "Would you like to create it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if result == QMessageBox.StandardButton.Yes:
            # Show type selector
            from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QVBoxLayout, QLabel
            dialog = QDialog(self)
            dialog.setWindowTitle(f'New Article: "{article_name}"')
            dialog.setMinimumWidth(360)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f'Select type for "{article_name}":'))
            combo = QComboBox()
            types = crud.list_all_article_types()
            combo.addItems(types)
            combo.setCurrentText("Location")
            layout.addWidget(combo)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                article_type = combo.currentText()
                article = Article(title=article_name, content="", article_type=article_type)
                crud.create_article(article)
                self.article_view.load_article(article)
                self.status_label.setText(f'Created: "{article_name}" ({article_type})')
                self.sidebar.refresh_recent()
                # Refresh autocomplete so the new article appears in [[ suggestions
                self.article_view._link_autocomplete.refresh()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _autosave(self) -> None:
        """Autosave the current article if it has unsaved changes."""
        if self.article_view.is_dirty:
            self.article_view.save()

    def _update_db_status(self) -> None:
        if self._db and self._db.db_path:
            name = Path(self._db.db_path).name
            self.db_status_label.setText(f"DB: {name}")

    def closeEvent(self, event) -> None:
        """Handle window close — autosave before exiting."""
        self._autosave_timer.stop()
        if self.article_view.is_dirty:
            self.article_view.save()
        event.accept()