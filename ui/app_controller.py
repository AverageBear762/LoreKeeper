"""
World Garden — ApplicationController.

Orchestrates the transition between the World Manager (startup) and the
Main Window (editing). Owns both windows and the RecentWorldsManager.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from database.manager import DatabaseManager
from database.schema import migrate
from ui.recent_worlds_manager import RecentWorldsManager
from ui.theme import ThemeManager


class ApplicationController:
    """Controls app lifecycle: startup, world switching, and shutdown."""

    def __init__(self, app: QApplication, theme: ThemeManager) -> None:
        self._app = app
        self._theme = theme
        self._recent = RecentWorldsManager()
        self._main_window = None
        self._world_manager = None

        # Lazy import to avoid circular imports
        from ui.main_window import MainWindow
        self._MainWindowCls = MainWindow

    @property
    def recent(self) -> RecentWorldsManager:
        return self._recent

    @property
    def main_window(self):
        return self._main_window

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Run the startup flow. Called once after app creation."""
        # Check CLI argument
        if len(sys.argv) > 1:
            cli_path = sys.argv[1]
            if os.path.isfile(cli_path):
                self.open_world(cli_path)
                return
            else:
                QMessageBox.warning(
                    None,
                    "Invalid Path",
                    f'File not found:\n{cli_path}\n\nOpening World Manager.',
                )

        # Show World Manager
        self.show_world_manager()

    # ------------------------------------------------------------------
    # World management
    # ------------------------------------------------------------------

    def show_world_manager(self) -> None:
        """Display the World Manager window, closing MainWindow if open."""
        self._close_main_window()

        from ui.world_manager import WorldManagerWindow
        if self._world_manager is None:
            self._world_manager = WorldManagerWindow(self._recent, self)
        self._world_manager.refresh()
        self._world_manager.show()
        self._world_manager.raise_()

    def open_world(self, path: str, name: Optional[str] = None) -> None:
        """Open a world database file and switch to the main editor."""
        path = str(Path(path).resolve())

        if not os.path.isfile(path):
            QMessageBox.critical(
                None, "File Not Found",
                f"Could not find world file:\n{path}",
            )
            return

        try:
            db = DatabaseManager()
            db.open(path, migrate=True)
        except Exception as e:
            QMessageBox.critical(
                None, "Error",
                f"Could not open world:\n{path}\n\n{e}",
            )
            return

        # Seed default templates
        from ui.default_templates import ensure_default_templates
        try:
            ensure_default_templates()
        except Exception:
            pass

        # Track in recent worlds
        if name is None:
            name = Path(path).stem
        self._recent.add_world(name, path)

        # Build and show the main window
        self._build_main_window()

    def create_world(self, name: str, path: str) -> None:
        """Create a new empty world database and open it."""
        path = str(Path(path).resolve())

        # Create the directory if needed
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # Create fresh database with migration
        db = DatabaseManager()
        db.open(path, migrate=True)

        # Seed default templates
        from ui.default_templates import ensure_default_templates
        try:
            ensure_default_templates()
        except Exception:
            pass

        # Track in recent worlds
        self._recent.add_world(name, path)

        # Build and show the main window
        self._build_main_window()

    def close_current_world(self) -> None:
        """Close the current world and return to the World Manager."""
        self._close_main_window()
        self.show_world_manager()

    def duplicate_world(self, source_path: str, dest_path: str) -> Optional[str]:
        """Duplicate a world database using SQLite backup API.
        Returns the destination path on success, None on failure.
        """
        try:
            import sqlite3
            source = sqlite3.connect(str(Path(source_path).resolve()))
            dest = sqlite3.connect(str(Path(dest_path).resolve()))
            source.backup(dest, pages=100)
            dest.close()
            source.close()
            return str(Path(dest_path).resolve())
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not duplicate world:\n{e}")
            return None

    def rename_world_file(self, old_path: str, new_name: str) -> Optional[str]:
        """Rename a world database file on disk.
        Returns the new path on success, None on failure.
        """
        old = Path(old_path).resolve()
        new = old.with_stem(new_name)
        try:
            old.rename(new)
            return str(new)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not rename file:\n{e}")
            return None

    def delete_world_file(self, path: str) -> bool:
        """Permanently delete a world database file."""
        try:
            Path(path).unlink()
            return True
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not delete file:\n{e}")
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_main_window(self) -> None:
        """Create and show the MainWindow."""
        self._close_main_window()

        self._main_window = self._MainWindowCls(self._theme)
        self._main_window.set_controller(self)
        self._main_window.show()
        self._main_window.raise_()

        # Set the window title to include the world name
        db = DatabaseManager()
        if db.db_path:
            world_name = Path(db.db_path).stem
            self._main_window.setWindowTitle(f"World Garden — {world_name}")
            self._main_window._update_db_status()

    def _close_main_window(self) -> None:
        """Safely destroy the main window if it exists."""
        if self._main_window is not None:
            self._main_window._autosave_timer.stop()
            if self._main_window.article_view.is_dirty:
                self._main_window.article_view.save()
            self._main_window.close()
            self._main_window.deleteLater()
            self._main_window = None
