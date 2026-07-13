"""
World Garden — WorldManagerWindow.

Startup window shown when no world is open. Displays recent worlds,
and provides options to create or open a world.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.manager import DatabaseManager
from ui.recent_worlds_manager import RecentWorldsManager


INVALID_FILENAME_CHARS = set('\\/:*?"<>|')


class NewWorldDialog(QDialog):
    """Dialog to enter a world name and choose a save location."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New World")
        self.setMinimumWidth(450)

        self._world_name: str = ""
        self._file_path: str = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Choose a name and location for your new world:"))

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. My Fantasy World")
        self.name_edit.textChanged.connect(self._on_name_changed)
        form.addRow("World Name:", self.name_edit)

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Choose file location...")
        path_layout.addWidget(self.path_edit, 1)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(self.browse_btn)

        form.addRow("Save As:", path_layout)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Set default path
        self._set_default_path()

    def _set_default_path(self) -> None:
        """Set the default save directory."""
        data_dir = os.path.join(str(Path.home()), ".worldgarden", "Worlds")
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self._default_dir = data_dir
        self._update_path()

    def _update_path(self) -> None:
        """Update the file path based on the current name."""
        name = self.name_edit.text().strip()
        if name:
            safe_name = "".join(c for c in name if c not in INVALID_FILENAME_CHARS)
            self._file_path = os.path.join(self._default_dir, f"{safe_name}.wgdb")
            self.path_edit.setText(self._file_path)
        else:
            self._file_path = ""
            self.path_edit.setText("")

    def _on_name_changed(self, text: str) -> None:
        self._update_path()
        self.error_label.setText("")

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save New World",
            self._file_path or str(Path.home()),
            "World Garden Database (*.wgdb);;All Files (*)",
        )
        if path:
            self._file_path = path
            self.path_edit.setText(path)

    def _on_accept(self) -> None:
        """Validate and accept the dialog."""
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()

        # Validate name
        if not name:
            self.error_label.setText("World name cannot be empty.")
            return

        if any(c in INVALID_FILENAME_CHARS for c in name):
            self.error_label.setText("Name contains invalid characters: \\ / : * ? \" < > |")
            return

        # Validate path
        if not path:
            self.error_label.setText("Please choose a file location.")
            return

        if Path(path).suffix not in (".wgdb", ".db", ".sqlite"):
            path += ".wgdb"
            self._file_path = path
            self.path_edit.setText(path)

        if Path(path).exists():
            self.error_label.setText(f"File already exists:\n{path}")
            return

        self._world_name = name
        self._file_path = path
        self.accept()

    @property
    def world_name(self) -> str:
        return self._world_name

    @property
    def file_path(self) -> str:
        return self._file_path


class MissingFileDialog(QDialog):
    """Dialog shown when a recent world's file is missing."""

    def __init__(self, name: str, path: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("World File Missing")
        self.setMinimumWidth(400)

        self._action: str = "remove"  # 'remove', 'locate'

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel(f'The world "{name}" could not be found at:'))
        layout.addWidget(QLabel(f'<code style="font-size: 11px;">{path}</code>'))

        btn_layout = QHBoxLayout()
        locate_btn = QPushButton("Locate File...")
        locate_btn.clicked.connect(self._on_locate)
        btn_layout.addWidget(locate_btn)

        remove_btn = QPushButton("Remove from Recent")
        remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(remove_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _on_locate(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Locate World File",
            str(Path.home()),
            "World Garden Database (*.wgdb *.db *.sqlite);;All Files (*)",
        )
        if path:
            self._new_path = path
            self._action = "locate"
            self.accept()

    def _on_remove(self) -> None:
        self._action = "remove"
        self.accept()

    @property
    def action(self) -> str:
        return self._action

    @property
    def new_path(self) -> str:
        return getattr(self, "_new_path", "")


class WorldManagerWindow(QDialog):
    """Startup window for managing worlds."""

    def __init__(
        self,
        recent_mgr: RecentWorldsManager,
        controller: Any,  # ApplicationController
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._recent = recent_mgr
        self._controller = controller

        self.setWindowTitle("World Garden — World Manager")
        self.setMinimumSize(500, 400)
        self.setModal(False)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header = QLabel("<h1>🌍 World Garden</h1>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        subtitle = QLabel("Select a world to open, or create a new one.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #6c757d; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # Buttons
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("✨ New World")
        self.new_btn.setMinimumHeight(36)
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.clicked.connect(self._on_new_world)
        btn_layout.addWidget(self.new_btn)

        self.open_btn = QPushButton("📂 Open World")
        self.open_btn.setMinimumHeight(36)
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._on_open_world)
        btn_layout.addWidget(self.open_btn)

        layout.addLayout(btn_layout)

        # Recent worlds label
        layout.addWidget(QLabel("<b>Recent Worlds:</b>"))

        # Recent worlds list
        self.world_list = QListWidget()
        self.world_list.setAlternatingRowColors(True)
        self.world_list.setMinimumHeight(200)
        self.world_list.itemDoubleClicked.connect(self._on_world_activated)
        self.world_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.world_list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.world_list, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload the recent worlds list."""
        self.world_list.clear()
        worlds = self._recent.list_worlds()

        for entry in worlds:
            file_exists = os.path.isfile(entry.path)

            # Format date
            try:
                from datetime import datetime
                dt = datetime.fromtimestamp(entry.last_opened)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = ""

            # Build display text
            pin_mark = "📌 " if entry.pinned else ""
            missing_mark = " [MISSING]" if not file_exists else ""
            display = f"{pin_mark}{entry.name}{missing_mark}"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, entry.path)
            item.setData(Qt.ItemDataRole.UserRole + 1, entry.name)

            # Tooltip with path and date
            tooltip = f"Path: {entry.path}"
            if date_str:
                tooltip += f"\nLast opened: {date_str}"
            if not file_exists:
                tooltip += "\n⚠ File not found"
            item.setToolTip(tooltip)

            # Style missing entries
            if not file_exists:
                item.setForeground(QColor("#dc3545"))

            self.world_list.addItem(item)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_new_world(self) -> None:
        """Show the New World dialog."""
        dialog = NewWorldDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._controller.create_world(dialog.world_name, dialog.file_path)
            self.close()

    def _on_open_world(self) -> None:
        """Open an existing world file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open World",
            str(Path.home()),
            "World Garden Database (*.wgdb *.db *.sqlite);;All Files (*)",
        )
        if path:
            self._controller.open_world(path)
            self.close()

    def _on_world_activated(self, item: QListWidgetItem) -> None:
        """Double-click a world to open it."""
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)

        if not os.path.isfile(path):
            self._show_missing_dialog(name, path, item)
            return

        self._controller.open_world(path, name)
        self.close()

    def _on_context_menu(self, pos) -> None:
        """Show context menu for a recent world entry."""
        item = self.world_list.itemAt(pos)
        if not item:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)
        file_exists = os.path.isfile(path)

        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)

        act_open = menu.addAction("📂 Open")
        act_open.triggered.connect(lambda: self._open_entry(item))

        if file_exists:
            menu.addSeparator()
            act_rename = menu.addAction("✏ Rename...")
            act_rename.triggered.connect(lambda: self._rename_entry(item))
            act_duplicate = menu.addAction("📋 Duplicate...")
            act_duplicate.triggered.connect(lambda: self._duplicate_entry(item))
            act_pin = menu.addAction("📌 Pin" if not self._is_pinned(path) else "📌 Unpin")
            act_pin.triggered.connect(lambda: self._toggle_pin(item))

        menu.addSeparator()
        act_remove = menu.addAction("🗑 Remove from Recent")
        act_remove.triggered.connect(lambda: self._remove_entry(item))

        if file_exists:
            act_delete = menu.addAction("💥 Delete File...")
            act_delete.setStyleSheet("color: #dc3545;")
            act_delete.triggered.connect(lambda: self._delete_entry(item))

        menu.exec(self.world_list.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Entry operations
    # ------------------------------------------------------------------

    def _open_entry(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)
        if not os.path.isfile(path):
            self._show_missing_dialog(name, path, item)
            return
        self._controller.open_world(path, name)
        self.close()

    def _rename_entry(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        old_name = item.data(Qt.ItemDataRole.UserRole + 1)

        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Rename World", "New name:", text=old_name,
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        # Rename file on disk
        new_path = self._controller.rename_world_file(path, new_name)
        if new_path:
            self._recent.rename_world(path, new_name)
            # If path changed, update the entry
            if new_path != path:
                self._recent.remove_world(path)
                self._recent.add_world(new_name, new_path)
            self.refresh()

    def _duplicate_entry(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)

        dest, _ = QFileDialog.getSaveFileName(
            self, "Duplicate World",
            str(Path(path).parent / f"{name}_copy.wgdb"),
            "World Garden Database (*.wgdb);;All Files (*)",
        )
        if not dest:
            return

        new_path = self._controller.duplicate_world(path, dest)
        if new_path:
            new_name = Path(new_path).stem
            self._recent.add_world(new_name, new_path)
            self.refresh()

    def _delete_entry(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)

        result = QMessageBox.question(
            self,
            "Delete World File",
            f'Permanently delete "{name}"?\n\nPath: {path}\n\n'
            "This will delete the database file from disk.\n"
            "This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            if self._controller.delete_world_file(path):
                self._recent.remove_world(path)
                self.refresh()

    def _remove_entry(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        self._recent.remove_world(path)
        self.refresh()

    def _toggle_pin(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        is_pinned = self._is_pinned(path)
        self._recent.pin_world(path, not is_pinned)
        self.refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_pinned(self, path: str) -> bool:
        for entry in self._recent.list_worlds():
            if Path(entry.path).resolve() == Path(path).resolve():
                return entry.pinned
        return False

    def _show_missing_dialog(self, name: str, path: str, item: QListWidgetItem) -> None:
        """Show dialog for a missing file."""
        dialog = MissingFileDialog(name, path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.action == "locate":
                new_path = dialog.new_path
                self._recent.remove_world(path)
                self._recent.add_world(name, new_path)
                self.refresh()
            elif dialog.action == "remove":
                self._recent.remove_world(path)
                self.refresh()
