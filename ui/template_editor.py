"""
World Garden — Template Editor.

Dialog for creating, editing, and managing article template schemas.
Users can add/remove/reorder fields and configure each field's type, label, and options.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from database import crud
from database.models import ArticleTemplate, FieldDefinition


# ======================================================================
#  Field Editor Row
# ======================================================================

class FieldEditorRow(QWidget):
    """A single row for editing a FieldDefinition inside the template editor."""

    removed = Signal(object)  # emits self

    FIELD_TYPES = [
        ("text", "Text (short)"),
        ("longtext", "Text (long)"),
        ("number", "Number"),
        ("boolean", "Yes/No"),
        ("date", "Date"),
        ("select", "Dropdown"),
        ("image", "Image"),
    ]

    def __init__(
        self,
        field_def: Optional[FieldDefinition] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._def = field_def or FieldDefinition()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # Field name (identifier)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("field_name")
        self.name_edit.setMaximumWidth(140)
        self.name_edit.setText(self._def.name)
        layout.addWidget(self.name_edit)

        # Label (display name)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Display Label")
        self.label_edit.setText(self._def.label)
        layout.addWidget(self.label_edit, 1)

        # Field type
        self.type_combo = QComboBox()
        for code, display in self.FIELD_TYPES:
            self.type_combo.addItem(display, code)
        idx = self.type_combo.findData(self._def.field_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        # Required checkbox
        self.required_cb = type(self)  # placeholder, will be QCheckBox
        from PySide6.QtWidgets import QCheckBox as QCB
        self.required_cb = QCB("Req.")
        self.required_cb.setChecked(self._def.required)
        layout.addWidget(self.required_cb)

        # Remove button
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setMaximumWidth(28)
        self.remove_btn.setStyleSheet(
            "QPushButton { color: #dc3545; font-weight: bold; border: none; }"
            "QPushButton:hover { background: #f8d7da; border-radius: 4px; }"
        )
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(self.remove_btn)

    def _on_type_changed(self, idx: int) -> None:
        """Show/hide options editor for 'select' type."""
        # We'll handle options through a separate dialog
        pass

    def get_field_definition(self) -> FieldDefinition:
        raw_name = self.name_edit.text().strip()
        raw_label = self.label_edit.text().strip()
        return FieldDefinition(
            name=raw_name or "unnamed_field",
            label=raw_label or raw_name.replace("_", " ") or "Unnamed",
            field_type=self.type_combo.currentData() or "text",
            required=self.required_cb.isChecked(),
            options=self._def.options if self._def.field_type == "select" else [],
            placeholder="",
        )


# ======================================================================
#  Template Editor Dialog
# ======================================================================

class TemplateEditorDialog(QDialog):
    """Dialog for creating or editing an article template schema."""

    template_saved = Signal(str)  # template_id

    def __init__(
        self,
        template: Optional[ArticleTemplate] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._field_rows: list[FieldEditorRow] = []

        self.setWindowTitle(
            f"Edit Template: {template.type_name}" if template else "New Template"
        )
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._build_ui()

        if template:
            self._load_fields(template.field_definitions)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Template name ---
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Template Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Spell, Kingdom, God...")
        if self._template:
            self.name_edit.setText(self._template.type_name)
        name_layout.addWidget(self.name_edit, 1)
        layout.addLayout(name_layout)

        # --- Field list ---
        layout.addWidget(QLabel("Fields:"))
        self.field_list = QListWidget()
        self.field_list.setMinimumHeight(200)
        layout.addWidget(self.field_list, 1)

        # --- Add field button ---
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Field")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_field_row)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        # --- Dialog buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_fields(self, fields: list[FieldDefinition]) -> None:
        for fd in fields:
            self._add_field_row(fd)

    def _add_field_row(
        self,
        field_def: Optional[FieldDefinition] = None,
    ) -> None:
        """Add a new FieldEditorRow to the list."""
        row = FieldEditorRow(field_def)
        row.removed.connect(self._remove_field_row)

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.field_list.addItem(item)
        self.field_list.setItemWidget(item, row)
        self._field_rows.append(row)

    def _remove_field_row(self, row: FieldEditorRow) -> None:
        """Remove a field row from the list."""
        if row in self._field_rows:
            idx = self._field_rows.index(row)
            self._field_rows.remove(row)
            item = self.field_list.takeItem(idx)
            if item:
                self.field_list.removeItemWidget(item)
            row.deleteLater()

    def _on_save(self) -> None:
        """Validate and save the template."""
        type_name = self.name_edit.text().strip()
        if not type_name:
            QMessageBox.warning(self, "Validation", "Template name is required.")
            return

        fields = [row.get_field_definition() for row in self._field_rows]
        if not fields:
            QMessageBox.warning(self, "Validation", "At least one field is required.")
            return

        if self._template:
            # Update existing
            self._template.type_name = type_name
            self._template.field_definitions = fields
            self._template.touch()
            crud.update_template(self._template)
            saved_id = self._template.id
        else:
            # Create new
            template = ArticleTemplate(
                type_name=type_name,
                field_definitions=fields,
            )
            crud.create_template(template)
            saved_id = template.id

        self.template_saved.emit(saved_id)
        self.accept()


# ======================================================================
#  Template Management Panel (embedded in sidebar or dialog)
# ======================================================================

class TemplateManagementDialog(QDialog):
    """Dialog listing all templates with options to create, edit, or delete."""

    templates_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Templates")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        layout.addWidget(QLabel("Custom Article Types:"))

        # Template list
        self.template_list = QListWidget()
        layout.addWidget(self.template_list, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("New Template")
        self.new_btn.clicked.connect(self._new_template)
        btn_layout.addWidget(self.new_btn)

        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self._edit_template)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet("QPushButton { color: #dc3545; }")
        self.delete_btn.clicked.connect(self._delete_template)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        # Close
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)

    def _refresh_list(self) -> None:
        self.template_list.clear()
        types = crud.list_all_article_types()
        for t in types:
            item = QListWidgetItem(t)
            # Check if it's a custom template (not built-in)
            from database.models import BUILTIN_ARTICLE_TYPES
            if t in BUILTIN_ARTICLE_TYPES:
                item.setToolTip("Built-in type (cannot be edited)")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(Qt.GlobalColor.gray)
            else:
                template = crud.get_template_by_type_name(t)
                if template:
                    item.setData(Qt.ItemDataRole.UserRole, template.id)
            self.template_list.addItem(item)

    def _new_template(self) -> None:
        dialog = TemplateEditorDialog(parent=self)
        dialog.template_saved.connect(lambda tid: self._refresh_list())
        dialog.exec()

    def _edit_template(self) -> None:
        selected = self.template_list.currentItem()
        if not selected:
            return
        tid = selected.data(Qt.ItemDataRole.UserRole)
        if not tid:
            return
        template = crud.get_template(tid)
        if template:
            dialog = TemplateEditorDialog(template, parent=self)
            dialog.template_saved.connect(lambda tid: self._refresh_list())
            dialog.exec()

    def _delete_template(self) -> None:
        selected = self.template_list.currentItem()
        if not selected:
            return
        tid = selected.data(Qt.ItemDataRole.UserRole)
        if not tid:
            return
        type_name = selected.text()
        result = QMessageBox.question(
            self,
            "Delete Template",
            f'Delete template "{type_name}"?\n'
            "Articles using this type will retain their data but won't have a schema.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            crud.delete_template(tid)
            self._refresh_list()