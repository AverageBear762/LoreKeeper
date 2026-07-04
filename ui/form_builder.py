"""
World Garden — Dynamic Form Builder.

Generates Qt input widgets on-the-fly from an ArticleTemplate's field definitions.
Supports: Text, LongText, Number, Boolean, Date, Select, Image.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from database.models import ArticleTemplate, FieldDefinition


# ---------------------------------------------------------------------------
#  Field Widget Factory
# ---------------------------------------------------------------------------

class FormFieldWidget(QWidget):
    """Wrapper around a single form field input widget."""

    value_changed = Signal()

    def __init__(
        self,
        definition: FieldDefinition,
        current_value: Any = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._def = definition
        self._widget: Optional[QWidget] = None
        self._image_label: Optional[QLabel] = None

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        label_text = definition.label or definition.name.replace("_", " ").title()
        if definition.required:
            label_text += " *"

        self._widget = self._build_widget(definition, current_value)
        layout.addRow(QLabel(label_text), self._widget)

        if definition.field_type == "image":
            self._image_label = QLabel()
            self._image_label.setFixedSize(120, 120)
            self._image_label.setStyleSheet(
                "border: 1px dashed #ccc; border-radius: 4px;"
                " background: transparent;"
            )
            self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._image_label.setText("No image")
            layout.addRow("", self._image_label)

            if isinstance(current_value, str) and current_value:
                self._set_image_preview(current_value)

    def _build_widget(self, defn: FieldDefinition, value: Any) -> QWidget:
        ft = defn.field_type

        if ft == "text":
            w = QLineEdit()
            w.setPlaceholderText(defn.placeholder or "")
            w.setMaxLength(255)
            if isinstance(value, str):
                w.setText(value)
            w.textChanged.connect(self.value_changed.emit)
            return w

        elif ft == "longtext":
            w = QPlainTextEdit()
            w.setPlaceholderText(defn.placeholder or "")
            w.setMinimumHeight(120)
            w.setMaximumHeight(300)
            w.setStyleSheet("QPlainTextEdit { line-height: 1.4; padding: 6px; }")
            if isinstance(value, str):
                w.setPlainText(value)
            w.textChanged.connect(self.value_changed.emit)
            return w

        elif ft == "number":
            w = QSpinBox()
            w.setRange(-999999, 999999)
            if value is not None:
                try:
                    w.setValue(int(value))
                except (ValueError, TypeError):
                    pass
            w.valueChanged.connect(self.value_changed.emit)
            return w

        elif ft == "boolean":
            w = QCheckBox("Yes")
            if isinstance(value, bool):
                w.setChecked(value)
            elif isinstance(value, (int, float)):
                w.setChecked(bool(value))
            w.toggled.connect(self.value_changed.emit)
            return w

        elif ft == "date":
            w = QDateEdit()
            w.setCalendarPopup(False)  # Disabled due to rendering bugs
            w.setSpecialValueText("Not set")
            w.setDisplayFormat("yyyy-MM-dd")
            w.clear()
            w.dateChanged.connect(self.value_changed.emit)
            return w

        elif ft == "select":
            w = QComboBox()
            w.setEditable(False)
            w.addItems(defn.options or [])
            if isinstance(value, str) and value in (defn.options or []):
                w.setCurrentText(value)
            w.currentTextChanged.connect(self.value_changed.emit)
            return w

        elif ft == "image":
            layout = QHBoxLayout()
            btn = QPushButton("Browse...")
            btn.setMaximumWidth(100)
            self._image_path = QLineEdit()
            self._image_path.setPlaceholderText(defn.placeholder or "Select image file...")
            self._image_path.setReadOnly(True)
            if isinstance(value, str):
                self._image_path.setText(value)

            def _browse():
                path, _ = QFileDialog.getOpenFileName(
                    self, "Select Image", "",
                    "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp)",
                )
                if path:
                    self._image_path.setText(path)
                    self._set_image_preview(path)
                    self.value_changed.emit()

            btn.clicked.connect(_browse)
            layout.addWidget(self._image_path)
            layout.addWidget(btn)
            container = QWidget()
            container.setLayout(layout)
            # We need to store the reference to the path widget
            self._path_widget = self._image_path
            return container

        # Fallback
        w = QLineEdit()
        w.setPlaceholderText(defn.placeholder or "")
        return w

    def _set_image_preview(self, path: str) -> None:
        if self._image_label is None:
            return
        pix = QPixmap(path)
        if not pix.isNull():
            self._image_label.setPixmap(
                pix.scaled(
                    120, 120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._image_label.setText("Invalid image")

    def get_value(self) -> Any:
        """Return the current value of this field."""
        ft = self._def.field_type
        w = self._widget

        if ft == "text":
            return w.text() if isinstance(w, QLineEdit) else ""
        elif ft == "longtext":
            return w.toPlainText() if isinstance(w, QPlainTextEdit) else ""
        elif ft == "number":
            return w.value() if isinstance(w, QSpinBox) else 0
        elif ft == "boolean":
            return w.isChecked() if isinstance(w, QCheckBox) else False
        elif ft == "date":
            if isinstance(w, QDateEdit):
                return w.date().toString("yyyy-MM-dd") if w.date().isValid() else ""
            return ""
        elif ft == "select":
            return w.currentText() if isinstance(w, QComboBox) else ""
        elif ft == "image":
            return self._image_path.text() if hasattr(self, "_image_path") else ""
        return ""


# ---------------------------------------------------------------------------
#  DynamicForm (scrollable collection of field widgets)
# ---------------------------------------------------------------------------

class DynamicForm(QScrollArea):
    """Scrollable form that renders editable fields from an ArticleTemplate."""

    value_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)

        self.setWidget(self._container)

        self._field_widgets: list[FormFieldWidget] = []

    def load_template(
        self,
        template: Optional[ArticleTemplate],
        current_values: dict[str, Any] | None = None,
    ) -> None:
        """Clear the form and rebuild widgets from a template."""
        self.clear()

        if template is None:
            placeholder = QLabel("Select an article type to see template fields.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #adb5bd; padding: 40px;")
            self._layout.insertWidget(0, placeholder)
            return

        self._field_widgets = []
        values = current_values or {}

        for fd in template.field_definitions:
            fw = FormFieldWidget(fd, values.get(fd.name))
            fw.value_changed.connect(self.value_changed.emit)
            self._field_widgets.append(fw)
            # Insert before the stretch
            self._layout.insertWidget(self._layout.count() - 1, fw)

    def clear(self) -> None:
        """Remove all field widgets."""
        for fw in self._field_widgets:
            self._layout.removeWidget(fw)
            fw.deleteLater()
        self._field_widgets.clear()

        # Remove any placeholder label
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, QLabel):
                    self._layout.removeWidget(w)
                    w.deleteLater()
                    break

    def get_values(self) -> dict[str, Any]:
        """Collect all field values into a dictionary keyed by field name."""
        result: dict[str, Any] = {}
        for fw in self._field_widgets:
            result[fw._def.name] = fw.get_value()
        return result

    @property
    def field_count(self) -> int:
        return len(self._field_widgets)