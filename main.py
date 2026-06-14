#!/usr/bin/env python3
"""
LoreKeeper — Application Entry Point.

Launches the desktop application shell with:
- Database initialisation
- Theme management (light/dark)
- Main window with sidebar, article view, and toolbar

Usage:
    python main.py                    # Opens default database
    python main.py path/to/lore.db    # Opens specific database
"""

import sys
import os
from pathlib import Path

# Ensure the project root is on sys.path for reliable imports
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from database.manager import DatabaseManager
from ui.default_templates import ensure_default_templates
from ui.main_window import MainWindow
from ui.theme import ThemeManager


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LoreKeeper")
    app.setOrganizationName("LoreKeeper")
    app.setApplicationVersion("0.1.0")

    # Default font
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # Init theme manager and apply light theme by default
    theme = ThemeManager(app)
    theme.switch_to(ThemeManager.LIGHT)

    # Build and show the main window
    window = MainWindow(theme)
    window.show()

    # Open the database (default or from CLI argument)
    db_path = _resolve_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    try:
        window.open_database(db_path)
    except Exception as e:
        QMessageBox.warning(
            window,
            "Database",
            f"Could not open database at:\n{db_path}\n\n{e}\n\n"
            "A new database will be created when you save.",
        )

    # Seed default templates into the database
    try:
        from database.manager import DatabaseManager as dbm
        ensure_default_templates()
    except Exception:
        pass  # Already seeded or DB not ready

    sys.exit(app.exec())


def _resolve_db_path(cli_path: str | None) -> str:
    """Return the path to the database file to use.

    1. CLI argument (if provided)
    2. Default: ~/.lorekeeper/lorekeeper.db
    """
    from database.manager import DatabaseManager
    if cli_path:
        return str(Path(cli_path).resolve())
    return DatabaseManager.default_db_path()


if __name__ == "__main__":
    main()