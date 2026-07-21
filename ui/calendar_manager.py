"""
World Garden — Calendar Manager Window.

Provides a dialog for creating, editing, and deleting calendars.
Each calendar has configurable months, weekdays, eras, and leap year rules
with drag-and-drop reordering and inline editing.

Layout:
  ┌────────────┬──────────────────────────────────────────┐
  │  Calendar  │  Tab Widget                              │
  │  List      │  ┌───────┬──────┬──────┬──────────┐     │
  │            │  │Months │Days  │Eras  │Leap Rules│     │
  │  ┌──────┐  │  ├───────┴──────┴──────┴──────────┤     │
  │  │ Cal1 │  │  │  Editable list / form area      │     │
  │  │ Cal2 │  │  │  (depends on selected tab)      │     │
  │  └──────┘  │  │                                  │     │
  │ +Add       │  │                                  │     │
  │ -Delete    │  │                                  │     │
  └────────────┴──────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QAction, QKeySequence, QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.calendar_engine import CalendarEngine
from database.models import (
    Calendar,
    CalendarMonth,
    CalendarWeekday,
    CalendarEra,
    LeapYearRule,
    _now,
    _uuid,
)


# ======================================================================
# Reorderable table widget
# ======================================================================

class ReorderableTableWidget(QTableWidget):
    """A QTableWidget with drag-and-drop row reordering enabled."""

    row_order_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDropIndicatorShown(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.verticalHeader().setSectionsMovable(True)
        self.verticalHeader().setDragEnabled(True)
        self.verticalHeader().setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dropEvent(self, event: Any) -> None:
        super().dropEvent(event)
        self.row_order_changed.emit()


# ======================================================================
# Calendar Manager Dialog
# ======================================================================

class CalendarManagerDialog(QDialog):
    """Main Calendar Manager dialog."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📅 Calendar Manager")
        self.setMinimumSize(900, 600)
        self.resize(1000, 650)

        self._calendars: list[Calendar] = []
        self._current_calendar_id: Optional[str] = None
        self._dirty: bool = False

        self._build_ui()
        self._refresh_calendar_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build left/right splitter layout."""
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # -- Left panel: calendar list --
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("<b>Calendars</b>"))

        self._cal_list = QListWidget()
        self._cal_list.currentRowChanged.connect(self._on_calendar_selected)
        left_layout.addWidget(self._cal_list, stretch=1)

        btn_layout = QHBoxLayout()
        self._btn_add_cal = QPushButton("➕ New")
        self._btn_add_cal.clicked.connect(self._on_add_calendar)
        btn_layout.addWidget(self._btn_add_cal)

        self._btn_rename_cal = QPushButton("✏️ Rename")
        self._btn_rename_cal.clicked.connect(self._on_rename_calendar)
        self._btn_rename_cal.setEnabled(False)
        btn_layout.addWidget(self._btn_rename_cal)

        self._btn_delete_cal = QPushButton("🗑 Delete")
        self._btn_delete_cal.clicked.connect(self._on_delete_calendar)
        self._btn_delete_cal.setEnabled(False)
        btn_layout.addWidget(self._btn_delete_cal)

        left_layout.addLayout(btn_layout)
        splitter.addWidget(left_widget)

        # -- Right panel: tabbed settings --
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # General settings area
        self._gen_group = QGroupBox("General")
        gen_form = QFormLayout(self._gen_group)
        self._edit_cal_name = QLineEdit()
        self._edit_cal_name.setPlaceholderText("Calendar name")
        self._edit_cal_name.textChanged.connect(self._mark_dirty)
        gen_form.addRow("Name:", self._edit_cal_name)

        self._edit_cal_desc = QPlainTextEdit()
        self._edit_cal_desc.setMaximumHeight(80)
        self._edit_cal_desc.setPlaceholderText("Description (optional)")
        self._edit_cal_desc.textChanged.connect(self._mark_dirty)
        gen_form.addRow("Description:", self._edit_cal_desc)

        self._edit_cal_epoch = QLineEdit()
        self._edit_cal_epoch.setPlaceholderText("e.g. Traditional Gregorian epoch")
        self._edit_cal_epoch.textChanged.connect(self._mark_dirty)
        gen_form.addRow("Epoch:", self._edit_cal_epoch)

        right_layout.addWidget(self._gen_group)

        # Settings tabs
        self._settings_tabs = QTabWidget()

        self._build_months_tab()
        self._build_weekdays_tab()
        self._build_eras_tab()
        self._build_leap_rules_tab()

        right_layout.addWidget(self._settings_tabs, stretch=1)

        # Bottom buttons
        btn_box = QDialogButtonBox()
        self._btn_seed_default = QPushButton("🌍 Seed Gregorian Calendar")
        self._btn_seed_default.clicked.connect(self._on_seed_default)
        btn_box.addButton(self._btn_seed_default, btn_box.ButtonRole.ActionRole)
        btn_box.addButton(self._btn_revert, btn_box.ButtonRole.ResetRole)
        btn_box.addButton(self._btn_save, btn_box.ButtonRole.AcceptRole)
        btn_box.addButton(self._btn_close, btn_box.ButtonRole.RejectRole)
        right_layout.addWidget(btn_box)

        self._btn_save = btn_box.button(btn_box.StandardButton.Save)
        self._btn_revert = btn_box.button(btn_box.StandardButton.Reset)
        self._btn_close = btn_box.button(btn_box.StandardButton.Close)

        self._btn_save.clicked.connect(self._on_save)
        self._btn_revert.clicked.connect(self._on_revert)
        self._btn_close.clicked.connect(self._on_close)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)

        self._set_right_enabled(False)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_months_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._months_table = ReorderableTableWidget()
        self._months_table.setColumnCount(3)
        self._months_table.setHorizontalHeaderLabels(["Name", "Days", ""])
        self._months_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._months_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._months_table.horizontalHeader().resizeSection(1, 60)
        self._months_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._months_table.horizontalHeader().resizeSection(2, 80)
        layout.addWidget(self._months_table)

        btn_row = QHBoxLayout()
        self._btn_add_month = QPushButton("➕ Add Month")
        self._btn_add_month.clicked.connect(self._on_add_month)
        btn_row.addWidget(self._btn_add_month)

        self._btn_remove_month = QPushButton("➖ Remove Selected")
        self._btn_remove_month.clicked.connect(self._on_remove_month)
        btn_row.addWidget(self._btn_remove_month)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._settings_tabs.addTab(tab, "Months")

    def _build_weekdays_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._weekdays_table = ReorderableTableWidget()
        self._weekdays_table.setColumnCount(2)
        self._weekdays_table.setHorizontalHeaderLabels(["Name", ""])
        self._weekdays_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._weekdays_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._weekdays_table.horizontalHeader().resizeSection(1, 80)
        layout.addWidget(self._weekdays_table)

        btn_row = QHBoxLayout()
        self._btn_add_weekday = QPushButton("➕ Add Weekday")
        self._btn_add_weekday.clicked.connect(self._on_add_weekday)
        btn_row.addWidget(self._btn_add_weekday)

        self._btn_remove_weekday = QPushButton("➖ Remove Selected")
        self._btn_remove_weekday.clicked.connect(self._on_remove_weekday)
        btn_row.addWidget(self._btn_remove_weekday)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._settings_tabs.addTab(tab, "Weekdays")

    def _build_eras_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._eras_table = QTableWidget()
        self._eras_table.setColumnCount(5)
        self._eras_table.setHorizontalHeaderLabels(["Name", "Abbr", "Start Year", "Primary", ""])
        self._eras_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._eras_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._eras_table.horizontalHeader().resizeSection(1, 60)
        self._eras_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._eras_table.horizontalHeader().resizeSection(2, 80)
        self._eras_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._eras_table.horizontalHeader().resizeSection(3, 60)
        self._eras_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._eras_table.horizontalHeader().resizeSection(4, 80)
        layout.addWidget(self._eras_table)

        btn_row = QHBoxLayout()
        self._btn_add_era = QPushButton("➕ Add Era")
        self._btn_add_era.clicked.connect(self._on_add_era)
        btn_row.addWidget(self._btn_add_era)

        self._btn_remove_era = QPushButton("➖ Remove Selected")
        self._btn_remove_era.clicked.connect(self._on_remove_era)
        btn_row.addWidget(self._btn_remove_era)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._settings_tabs.addTab(tab, "Eras")

    def _build_leap_rules_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._leap_table = QTableWidget()
        self._leap_table.setColumnCount(6)
        self._leap_table.setHorizontalHeaderLabels(["Type", "Interval", "Month", "Days ±", "Description", ""])
        self._leap_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._leap_table.horizontalHeader().resizeSection(0, 80)
        self._leap_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._leap_table.horizontalHeader().resizeSection(1, 70)
        self._leap_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._leap_table.horizontalHeader().resizeSection(2, 60)
        self._leap_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._leap_table.horizontalHeader().resizeSection(3, 60)
        self._leap_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._leap_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._leap_table.horizontalHeader().resizeSection(5, 80)
        layout.addWidget(self._leap_table)

        btn_row = QHBoxLayout()
        self._btn_add_leap = QPushButton("➕ Add Leap Rule")
        self._btn_add_leap.clicked.connect(self._on_add_leap_rule)
        btn_row.addWidget(self._btn_add_leap)

        self._btn_remove_leap = QPushButton("➖ Remove Selected")
        self._btn_remove_leap.clicked.connect(self._on_remove_leap_rule)
        btn_row.addWidget(self._btn_remove_leap)

        self._btn_verify_leap = QPushButton("🔍 Verify Rules")
        self._btn_verify_leap.clicked.connect(self._on_verify_leap_rules)
        btn_row.addWidget(self._btn_verify_leap)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._settings_tabs.addTab(tab, "Leap Rules")

    # ------------------------------------------------------------------
    # Calendar list management
    # ------------------------------------------------------------------

    def _refresh_calendar_list(self) -> None:
        """Reload the calendar list from the database."""
        self._calendars = crud.list_calendars()
        self._cal_list.blockSignals(True)
        self._cal_list.clear()
        for cal in self._calendars:
            item = QListWidgetItem(cal.name)
            item.setData(Qt.ItemDataRole.UserRole, cal.id)
            self._cal_list.addItem(item)
        self._cal_list.blockSignals(False)

    def _set_right_enabled(self, enabled: bool) -> None:
        self._gen_group.setEnabled(enabled)
        self._settings_tabs.setEnabled(enabled)
        self._btn_seed_default.setEnabled(enabled)
        self._btn_save.setEnabled(enabled)
        self._btn_revert.setEnabled(enabled)
        self._btn_rename_cal.setEnabled(enabled)
        self._btn_delete_cal.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Calendar selection
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_calendar_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._calendars):
            self._current_calendar_id = None
            self._set_right_enabled(False)
            return

        cal = self._calendars[row]
        self._current_calendar_id = cal.id
        self._set_right_enabled(True)
        self._load_calendar(cal)

    def _load_calendar(self, cal: Calendar) -> None:
        """Load a calendar's data into the right panel fields."""
        self._edit_cal_name.blockSignals(True)
        self._edit_cal_name.setText(cal.name)
        self._edit_cal_name.blockSignals(False)

        self._edit_cal_desc.blockSignals(True)
        self._edit_cal_desc.setPlainText(cal.description)
        self._edit_cal_desc.blockSignals(False)

        self._edit_cal_epoch.blockSignals(True)
        self._edit_cal_epoch.setText(cal.epoch)
        self._edit_cal_epoch.blockSignals(False)

        self._dirty = False
        self._load_months(cal.id)
        self._load_weekdays(cal.id)
        self._load_eras(cal.id)
        self._load_leap_rules(cal.id)

    # ------------------------------------------------------------------
    # Load sub-entities
    # ------------------------------------------------------------------

    def _load_months(self, calendar_id: str) -> None:
        months = crud.list_calendar_months(calendar_id)
        months.sort(key=lambda m: m.position)

        self._months_table.setRowCount(len(months))
        for i, m in enumerate(months):
            name_item = QTableWidgetItem(m.name)
            self._months_table.setItem(i, 0, name_item)

            days_item = QTableWidgetItem()
            days_item.setData(Qt.ItemDataRole.DisplayRole, m.days)
            self._months_table.setItem(i, 1, days_item)

            remove_btn = QPushButton("🗑")
            remove_btn.clicked.connect(lambda checked=False, r=i: self._remove_month_at(r))
            self._months_table.setCellWidget(i, 2, remove_btn)

    def _load_weekdays(self, calendar_id: str) -> None:
        days = crud.list_calendar_weekdays(calendar_id)
        days.sort(key=lambda d: d.position)

        self._weekdays_table.setRowCount(len(days))
        for i, d in enumerate(days):
            name_item = QTableWidgetItem(d.name)
            self._weekdays_table.setItem(i, 0, name_item)

            remove_btn = QPushButton("🗑")
            remove_btn.clicked.connect(lambda checked=False, r=i: self._remove_weekday_at(r))
            self._weekdays_table.setCellWidget(i, 1, remove_btn)

    def _load_eras(self, calendar_id: str) -> None:
        eras = crud.list_calendar_eras(calendar_id)
        eras.sort(key=lambda e: e.start_year)

        self._eras_table.setRowCount(len(eras))
        for i, e in enumerate(eras):
            self._eras_table.setItem(i, 0, QTableWidgetItem(e.name))
            self._eras_table.setItem(i, 1, QTableWidgetItem(e.abbreviation))
            year_item = QTableWidgetItem()
            year_item.setData(Qt.ItemDataRole.DisplayRole, e.start_year)
            self._eras_table.setItem(i, 2, year_item)

            primary_cb = QCheckBox()
            primary_cb.setChecked(e.is_primary)
            primary_cb.toggled.connect(self._mark_dirty)
            self._eras_table.setCellWidget(i, 3, primary_cb)

            remove_btn = QPushButton("🗑")
            remove_btn.clicked.connect(lambda checked=False, r=i: self._remove_era_at(r))
            self._eras_table.setCellWidget(i, 4, remove_btn)

    def _load_leap_rules(self, calendar_id: str) -> None:
        rules = crud.list_leap_year_rules(calendar_id)

        self._leap_table.setRowCount(len(rules))
        for i, r in enumerate(rules):
            type_combo = QComboBox()
            type_combo.addItems(["interval", "exception"])
            type_combo.setCurrentText(r.rule_type)
            self._leap_table.setCellWidget(i, 0, type_combo)

            int_item = QTableWidgetItem()
            int_item.setData(Qt.ItemDataRole.DisplayRole, r.interval)
            self._leap_table.setItem(i, 1, int_item)

            month_item = QTableWidgetItem()
            month_item.setData(Qt.ItemDataRole.DisplayRole, r.month)
            self._leap_table.setItem(i, 2, month_item)

            days_item = QTableWidgetItem()
            days_item.setData(Qt.ItemDataRole.DisplayRole, r.days_to_add)
            self._leap_table.setItem(i, 3, days_item)

            self._leap_table.setItem(i, 4, QTableWidgetItem(r.description))

            remove_btn = QPushButton("🗑")
            remove_btn.clicked.connect(lambda checked=False, r=i: self._remove_leap_at(r))
            self._leap_table.setCellWidget(i, 5, remove_btn)

    # ------------------------------------------------------------------
    # Mark dirty
    # ------------------------------------------------------------------

    def _mark_dirty(self, *args: Any) -> None:
        self._dirty = True

    # ------------------------------------------------------------------
    # Calendar CRUD actions
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_calendar(self) -> None:
        name, ok = QInputDialog.getText(self, "New Calendar", "Calendar name:")
        if not ok or not name.strip():
            return
        cal = Calendar(name=name.strip())
        crud.create_calendar(cal)
        self._refresh_calendar_list()
        idx = self._cal_list.findText(cal.name, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            self._cal_list.setCurrentRow(idx)

    @Slot()
    def _on_rename_calendar(self) -> None:
        if not self._current_calendar_id:
            return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal:
            return
        name, ok = QInputDialog.getText(self, "Rename Calendar", "New name:", text=cal.name)
        if not ok or not name.strip():
            return
        cal.name = name.strip()
        cal.updated_at = _now()
        crud.update_calendar(cal)
        self._refresh_calendar_list()
        idx = self._cal_list.findText(cal.name, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            self._cal_list.setCurrentRow(idx)

    @Slot()
    def _on_delete_calendar(self) -> None:
        if not self._current_calendar_id:
            return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal:
            return
        reply = QMessageBox.question(
            self, "Delete Calendar",
            f"Delete calendar '{cal.name}' and all its months, weekdays, eras, and leap rules?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        crud.delete_calendar(cal.id)
        self._current_calendar_id = None
        self._set_right_enabled(False)
        self._refresh_calendar_list()

    @Slot()
    def _on_seed_default(self) -> None:
        reply = QMessageBox.question(
            self, "Seed Gregorian Calendar",
            "Add a new Gregorian (Earth) calendar with 12 months, 7-day weeks, and BC/AD eras?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        cid = CalendarEngine.seed_default_earth_calendar()
        self._refresh_calendar_list()
        cal = crud.get_calendar(cid)
        if cal:
            idx = self._cal_list.findText(cal.name, Qt.MatchFlag.MatchExactly)
            if idx >= 0:
                self._cal_list.setCurrentRow(idx)

    # ------------------------------------------------------------------
    # Save / Revert / Close
    # ------------------------------------------------------------------

    @Slot()
    def _on_save(self) -> None:
        if not self._current_calendar_id:
            return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal:
            return

        new_name = self._edit_cal_name.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Validation Error", "Calendar name is required.")
            return

        # Validate sub-entities
        if self._months_table.rowCount() == 0:
            QMessageBox.warning(self, "Validation Error", "Calendar must have at least one month.")
            return

        errors = self._collect_validation_errors()
        if errors:
            QMessageBox.warning(self, "Validation Error",
                                "Please fix these issues:\n\n" + "\n".join(errors))
            return

        cal.name = new_name
        cal.description = self._edit_cal_desc.toPlainText().strip()
        cal.epoch = self._edit_cal_epoch.text().strip()
        cal.updated_at = _now()
        crud.update_calendar(cal)

        self._save_months(cal.id)
        self._save_weekdays(cal.id)
        self._save_eras(cal.id)
        self._save_leap_rules(cal.id)

        self._dirty = False
        self._refresh_calendar_list()
        idx = self._cal_list.findText(cal.name, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            self._cal_list.setCurrentRow(idx)

    def _collect_validation_errors(self) -> list[str]:
        errors: list[str] = []

        # Check months
        if self._months_table.rowCount() == 0:
            errors.append("• At least one month is required.")

        for i in range(self._months_table.rowCount()):
            name_item = self._months_table.item(i, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                errors.append(f"• Month {i + 1}: name is required.")

            days_item = self._months_table.item(i, 1)
            days = int(days_item.data(Qt.ItemDataRole.DisplayRole) or 0)
            if days < 1:
                errors.append(f"• Month '{name}': days must be at least 1.")

        # Check weekdays
        for i in range(self._weekdays_table.rowCount()):
            name_item = self._weekdays_table.item(i, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                errors.append(f"• Weekday {i + 1}: name is required.")

        # Check eras
        primary_count = 0
        for i in range(self._eras_table.rowCount()):
            name_item = self._eras_table.item(i, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                errors.append(f"• Era {i + 1}: name is required.")
            abbr_item = self._eras_table.item(i, 1)
            abbr = abbr_item.text().strip() if abbr_item else ""
            if not abbr:
                errors.append(f"• Era '{name}': abbreviation is required.")
            widget = self._eras_table.cellWidget(i, 3)
            if widget and isinstance(widget, QCheckBox) and widget.isChecked():
                primary_count += 1
        if self._eras_table.rowCount() > 0 and primary_count == 0:
            errors.append("• At least one era must be marked as primary.")

        # Check leap rules
        for i in range(self._leap_table.rowCount()):
            type_widget = self._leap_table.cellWidget(i, 0)
            if type_widget and isinstance(type_widget, QComboBox):
                rule_type = type_widget.currentText()
                if rule_type not in ("interval", "exception"):
                    errors.append(f"• Leap rule {i + 1}: invalid rule type.")

            int_item = self._leap_table.item(i, 1)
            interval = int(int_item.data(Qt.ItemDataRole.DisplayRole) or 0)
            if interval <= 0:
                errors.append(f"• Leap rule {i + 1}: interval must be positive.")

            month_item = self._leap_table.item(i, 2)
            month = int(month_item.data(Qt.ItemDataRole.DisplayRole) or 0)
            if month < 1 or month > self._months_table.rowCount():
                errors.append(f"• Leap rule {i + 1}: month {month} out of range.")

        return errors

    def _save_months(self, calendar_id: str) -> None:
        crud.delete_calendar_months(calendar_id)
        for i in range(self._months_table.rowCount()):
            name_item = self._months_table.item(i, 0)
            name = name_item.text().strip() if name_item else f"Month {i + 1}"
            days_item = self._months_table.item(i, 1)
            days = int(days_item.data(Qt.ItemDataRole.DisplayRole) or 30)
            crud.create_calendar_month(CalendarMonth(
                calendar_id=calendar_id, name=name, days=days, position=i + 1,
            ))

    def _save_weekdays(self, calendar_id: str) -> None:
        crud.delete_calendar_weekdays(calendar_id)
        for i in range(self._weekdays_table.rowCount()):
            name_item = self._weekdays_table.item(i, 0)
            name = name_item.text().strip() if name_item else f"Day {i + 1}"
            crud.create_calendar_weekday(CalendarWeekday(
                calendar_id=calendar_id, name=name, position=i + 1,
            ))

    def _save_eras(self, calendar_id: str) -> None:
        crud.delete_calendar_eras(calendar_id)
        for i in range(self._eras_table.rowCount()):
            name_item = self._eras_table.item(i, 0)
            name = name_item.text().strip() if name_item else f"Era {i + 1}"
            abbr_item = self._eras_table.item(i, 1)
            abbr = abbr_item.text().strip() if abbr_item else name[:3]
            start_item = self._eras_table.item(i, 2)
            start_year = int(start_item.data(Qt.ItemDataRole.DisplayRole) or 1)
            primary = False
            widget = self._eras_table.cellWidget(i, 3)
            if widget and isinstance(widget, QCheckBox):
                primary = widget.isChecked()
            crud.create_calendar_era(CalendarEra(
                calendar_id=calendar_id, name=name, abbreviation=abbr,
                start_year=start_year, is_primary=primary,
            ))

    def _save_leap_rules(self, calendar_id: str) -> None:
        crud.delete_leap_year_rules(calendar_id)
        for i in range(self._leap_table.rowCount()):
            type_widget = self._leap_table.cellWidget(i, 0)
            rule_type = "interval"
            if type_widget and isinstance(type_widget, QComboBox):
                rule_type = type_widget.currentText()

            int_item = self._leap_table.item(i, 1)
            interval = int(int_item.data(Qt.ItemDataRole.DisplayRole) or 4)

            month_item = self._leap_table.item(i, 2)
            month = int(month_item.data(Qt.ItemDataRole.DisplayRole) or 2)

            days_item = self._leap_table.item(i, 3)
            days_to_add = int(days_item.data(Qt.ItemDataRole.DisplayRole) or 1)

            desc_item = self._leap_table.item(i, 4)
            description = desc_item.text().strip() if desc_item else ""

            crud.create_leap_year_rule(LeapYearRule(
                calendar_id=calendar_id, rule_type=rule_type,
                interval=interval, offset=0,
                month=month, days_to_add=days_to_add,
                description=description,
            ))

    @Slot()
    def _on_revert(self) -> None:
        if not self._current_calendar_id:
            return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal:
            return
        self._load_calendar(cal)

    @Slot()
    def _on_close(self) -> None:
        if self._dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self.accept()

    # ------------------------------------------------------------------
    # Month CRUD
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_month(self) -> None:
        row = self._months_table.rowCount()
        self._months_table.insertRow(row)
        self._months_table.setItem(row, 0, QTableWidgetItem("New Month"))
        days_item = QTableWidgetItem()
        days_item.setData(Qt.ItemDataRole.DisplayRole, 30)
        self._months_table.setItem(row, 1, days_item)
        remove_btn = QPushButton("🗑")
        remove_btn.clicked.connect(lambda: self._remove_month_at(
            self._months_table.indexAt(remove_btn.pos()).row()
            if self._months_table.indexAt(remove_btn.pos()).isValid() else row
        ))
        self._months_table.setCellWidget(row, 2, remove_btn)
        self._dirty = True

    @Slot()
    def _on_remove_month(self) -> None:
        rows = set()
        for item in self._months_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._remove_month_at(row)

    def _remove_month_at(self, row: int) -> None:
        if 0 <= row < self._months_table.rowCount():
            self._months_table.removeRow(row)
            self._dirty = True

    # ------------------------------------------------------------------
    # Weekday CRUD
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_weekday(self) -> None:
        row = self._weekdays_table.rowCount()
        self._weekdays_table.insertRow(row)
        self._weekdays_table.setItem(row, 0, QTableWidgetItem("New Day"))
        remove_btn = QPushButton("🗑")
        remove_btn.clicked.connect(lambda: self._remove_weekday_at(
            self._weekdays_table.indexAt(remove_btn.pos()).row()
            if self._weekdays_table.indexAt(remove_btn.pos()).isValid() else row
        ))
        self._weekdays_table.setCellWidget(row, 1, remove_btn)
        self._dirty = True

    @Slot()
    def _on_remove_weekday(self) -> None:
        rows = set()
        for item in self._weekdays_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._remove_weekday_at(row)

    def _remove_weekday_at(self, row: int) -> None:
        if 0 <= row < self._weekdays_table.rowCount():
            self._weekdays_table.removeRow(row)
            self._dirty = True

    # ------------------------------------------------------------------
    # Era CRUD
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_era(self) -> None:
        row = self._eras_table.rowCount()
        self._eras_table.insertRow(row)
        self._eras_table.setItem(row, 0, QTableWidgetItem("New Era"))
        self._eras_table.setItem(row, 1, QTableWidgetItem("NE"))
        year_item = QTableWidgetItem()
        year_item.setData(Qt.ItemDataRole.DisplayRole, 1)
        self._eras_table.setItem(row, 2, year_item)
        cb = QCheckBox()
        self._eras_table.setCellWidget(row, 3, cb)
        remove_btn = QPushButton("🗑")
        self._eras_table.setCellWidget(row, 4, remove_btn)
        self._dirty = True

    @Slot()
    def _on_remove_era(self) -> None:
        rows = set()
        for item in self._eras_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._remove_era_at(row)

    def _remove_era_at(self, row: int) -> None:
        if 0 <= row < self._eras_table.rowCount():
            self._eras_table.removeRow(row)
            self._dirty = True

    # ------------------------------------------------------------------
    # Leap rule CRUD
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_leap_rule(self) -> None:
        row = self._leap_table.rowCount()
        self._leap_table.insertRow(row)

        type_combo = QComboBox()
        type_combo.addItems(["interval", "exception"])
        self._leap_table.setCellWidget(row, 0, type_combo)

        int_item = QTableWidgetItem()
        int_item.setData(Qt.ItemDataRole.DisplayRole, 4)
        self._leap_table.setItem(row, 1, int_item)

        month_item = QTableWidgetItem()
        month_item.setData(Qt.ItemDataRole.DisplayRole, 2)
        self._leap_table.setItem(row, 2, month_item)

        days_item = QTableWidgetItem()
        days_item.setData(Qt.ItemDataRole.DisplayRole, 1)
        self._leap_table.setItem(row, 3, days_item)

        self._leap_table.setItem(row, 4, QTableWidgetItem(""))

        remove_btn = QPushButton("🗑")
        self._leap_table.setCellWidget(row, 5, remove_btn)
        self._dirty = True

    @Slot()
    def _on_remove_leap_rule(self) -> None:
        rows = set()
        for item in self._leap_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._remove_leap_at(row)

    def _remove_leap_at(self, row: int) -> None:
        if 0 <= row < self._leap_table.rowCount():
            self._leap_table.removeRow(row)
            self._dirty = True

    @Slot()
    def _on_verify_leap_rules(self) -> None:
        if not self._current_calendar_id:
            return
        engine = CalendarEngine(self._current_calendar_id)
        result = engine.verify_leap_rules()
        if result["valid"] and not result["warnings"]:
            QMessageBox.information(self, "Leap Rule Verification",
                                    "All leap rules are valid.")
        elif result["valid"]:
            msg = "Leap rules are valid with warnings:\n\n" + "\n".join(result["warnings"])
            QMessageBox.warning(self, "Leap Rule Verification", msg)
        else:
            msg = "Leap rules have errors:\n\n"
            msg += "\n".join(result["errors"])
            if result["warnings"]:
                msg += "\n\nWarnings:\n" + "\n".join(result["warnings"])
            QMessageBox.warning(self, "Leap Rule Verification", msg)

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event: Any) -> None:
        if self._dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()