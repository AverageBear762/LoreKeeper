#!/usr/bin/env python3
"""
World Garden — Application Entry Point.

Launches the desktop application shell with:
- ApplicationController for startup flow (World Manager or CLI path)
- Theme management (light/dark)

Usage:
    python main.py                          # Shows World Manager
    python main.py path/to/world.wgdb       # Opens that world directly
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
from ui.app_controller import ApplicationController
from ui.recent_worlds_manager import RecentWorldsManager, RECENT_WORLDS_PATH
from ui.theme import ThemeManager


LEGACY_IGNORE_FLAG = os.path.join(
    os.path.join(str(Path.home()), ".worldgarden"),
    ".legacy_ignore_done",
)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("World Garden")
    app.setOrganizationName("World Garden")
    app.setApplicationVersion("0.1.0")

    # Default font
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # Init theme manager and apply light theme by default
    theme = ThemeManager(app)
    theme.switch_to(ThemeManager.LIGHT)

    # Handle legacy lorekeeper.db on first run
    _handle_legacy_db()

    # Create the application controller and start the flow
    controller = ApplicationController(app, theme)
    controller.start()

    sys.exit(app.exec())


def _handle_legacy_db() -> None:
    """Check for legacy ~/.lorekeeper/lorekeeper.db on first run.

    Shows a dialog offering to: Add to Recent, Rename and Move, or Ignore.
    Remembers the Ignore choice so the prompt doesn't repeat.
    """
    legacy_path = os.path.join(str(Path.home()), ".lorekeeper", "lorekeeper.db")
    if not os.path.isfile(legacy_path):
        return

    # Check if we've already asked about this
    if os.path.isfile(LEGACY_IGNORE_FLAG):
        return

    # Check if it's already in recent worlds
    recent = RecentWorldsManager()
    if recent.contains_path(legacy_path):
        return

    # Show dialog (using QMessageBox since no window exists yet)
    msg = QMessageBox()
    msg.setWindowTitle("Legacy World Found")
    msg.setText(
        "A world from a previous version of World Garden (LoreKeeper) was found."
    )
    msg.setInformativeText(
        f"Location:\n{legacy_path}\n\n"
        "What would you like to do with it?"
    )

    add_btn = msg.addButton("Add to Recent Worlds", QMessageBox.ButtonRole.ActionRole)
    move_btn = msg.addButton("Rename and Move...", QMessageBox.ButtonRole.ActionRole)
    ignore_btn = msg.addButton("Ignore", QMessageBox.ButtonRole.RejectRole)
    msg.setDefaultButton(add_btn)
    msg.exec()

    clicked = msg.clickedButton()

    if clicked == add_btn:
        name = Path(legacy_path).stem
        recent.add_world(name, legacy_path)

    elif clicked == move_btn:
        # Ask for new name and location
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            None,
            "Rename Legacy World",
            "Enter a name for this world:",
            text="My World",
        )
        if ok and new_name.strip():
            new_name = new_name.strip()
            data_dir = os.path.join(str(Path.home()), ".worldgarden", "Worlds")
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            new_path = os.path.join(data_dir, f"{new_name}.wgdb")
            try:
                os.rename(legacy_path, new_path)
                recent.add_world(new_name, new_path)
            except Exception as e:
                QMessageBox.warning(
                    None, "Error", f"Could not move file:\n{e}"
                )
                # Still add the old location
                recent.add_world(new_name, legacy_path)

    elif clicked == ignore_btn:
        # Create flag file so we don't ask again
        Path(LEGACY_IGNORE_FLAG).parent.mkdir(parents=True, exist_ok=True)
        Path(LEGACY_IGNORE_FLAG).touch()


if __name__ == "__main__":
    main()
