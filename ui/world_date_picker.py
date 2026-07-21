"""
World Garden — WorldDatePicker Widget.

A reusable QWidget for picking dates using a specific calendar.
All conversions use CalendarEngine — no duplicate date logic.

Features:
- Calendar selector dropdown (defaults to first available)
- Era-based year control (hides astronomical year 0)
- Month and day controls that auto-update valid ranges
- Leap day support
- Forward and backward-counting eras
- Signals (calendar_id, absolute_day, formatted_date) when date changes
- Validation state — rejects invalid dates
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.calendar_engine import CalendarEngine
from database.models import CalendarEra


class WorldDatePicker(QWidget):
    """A calendar-aware date picker that uses CalendarEngine for all date math."""

    # Emitted when the selected date changes
    date_changed = Signal(str, int, str)  # (calendar_id, absolute_day, formatted_date)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._engine: Optional[CalendarEngine] = None
        self._current_era: Optional[CalendarEra] = None
        self._valid: bool = False
        self._block_signals: bool = False

        self._build_ui()
        self._refresh_calendar_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        # Row 1: Calendar selector
        cal_row = QHBoxLayout()
        cal_row.addWidget(QLabel("Calendar:"))
        self._cal_combo = QComboBox()
        self._cal_combo.currentIndexChanged.connect(self._on_calendar_changed)
        cal_row.addWidget(self._cal_combo, stretch=1)
        main.addLayout(cal_row)

        # Row 2: Year, Era, Month, Day
        date_row = QHBoxLayout()

        date_row.addWidget(QLabel("Year:"))
        self._year_spin = QSpinBox()
        self._year_spin.setMinimum(-999999)
        self._year_spin.setMaximum(999999)
        self._year_spin.setValue(1)
        self._year_spin.valueChanged.connect(self._on_date_component_changed)
        date_row.addWidget(self._year_spin)

        date_row.addWidget(QLabel("Era:"))
        self._era_combo = QComboBox()
        self._era_combo.currentIndexChanged.connect(self._on_era_changed)
        date_row.addWidget(self._era_combo)

        date_row.addWidget(QLabel("Month:"))
        self._month_combo = QComboBox()
        self._month_combo.currentIndexChanged.connect(self._on_date_component_changed)
        date_row.addWidget(self._month_combo)

        date_row.addWidget(QLabel("Day:"))
        self._day_spin = QSpinBox()
        self._day_spin.setMinimum(1)
        self._day_spin.setMaximum(31)
        self._day_spin.setValue(1)
        self._day_spin.valueChanged.connect(self._on_date_component_changed)
        date_row.addWidget(self._day_spin)

        main.addLayout(date_row)

        # Row 3: Formatted preview
        self._formatted_label = QLabel("")
        self._formatted_label.setStyleSheet("color: gray; font-style: italic;")
        main.addWidget(self._formatted_label)

    # ------------------------------------------------------------------
    # Calendar list
    # ------------------------------------------------------------------

    def _refresh_calendar_list(self) -> None:
        self._cal_combo.blockSignals(True)
        self._cal_combo.clear()
        for cal in crud.list_calendars():
            self._cal_combo.addItem(cal.name, cal.id)
        self._cal_combo.blockSignals(False)

        if self._cal_combo.count() > 0:
            self._on_calendar_changed(0)

    # ------------------------------------------------------------------
    # Calendar change
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_calendar_changed(self, index: int) -> None:
        if index < 0:
            return
        cal_id = self._cal_combo.currentData()
        if not cal_id:
            return

        engine = CalendarEngine(cal_id)
        if not engine.calendar:
            return
        self._engine = engine

        # Populate months
        self._month_combo.blockSignals(True)
        self._month_combo.clear()
        for m in engine.months:
            self._month_combo.addItem(m.name, m.position)
        self._month_combo.blockSignals(False)

        # Populate eras
        self._era_combo.blockSignals(True)
        self._era_combo.clear()
        for era in engine.eras:
            self._era_combo.addItem(f"{era.name} ({era.abbreviation})", era.id)
        self._era_combo.blockSignals(False)

        if self._era_combo.count() > 0:
            self._on_era_changed(0)
        else:
            self._current_era = None
            self._year_spin.setValue(1)
            self._update_day_range()
            self._emit_date()

    @Slot(int)
    def _on_era_changed(self, index: int) -> None:
        if not self._engine or index < 0:
            return
        era_id = self._era_combo.currentData()
        for era in self._engine.eras:
            if era.id == era_id:
                self._current_era = era
                # Set year to era's start if this is a new era selection
                self._set_era_year(self._current_era.start_year if self._current_era.is_primary else 1)
                self._update_day_range()
                self._emit_date()
                return

    # ------------------------------------------------------------------
    # Date components changed
    # ------------------------------------------------------------------

    @Slot()
    def _on_date_component_changed(self) -> None:
        self._update_day_range()
        self._emit_date()

    def _update_day_range(self) -> None:
        """Update the day spin box range based on selected year/month and leap rules."""
        if not self._engine or not self._engine.months:
            return

        year = self._current_astronomical_year()
        month_idx = self._month_combo.currentIndex()
        if month_idx < 0 or month_idx >= len(self._engine.months):
            return

        max_days = self._engine.months[month_idx].days
        for rule in self._engine.leap_rules:
            if rule.month == (month_idx + 1) and self._engine.is_leap_affected(rule, year):
                max_days += rule.days_to_add

        self._day_spin.blockSignals(True)
        old_day = self._day_spin.value()
        self._day_spin.setMaximum(max_days)
        if old_day > max_days:
            self._day_spin.setValue(max_days)
        self._day_spin.blockSignals(False)

    # ------------------------------------------------------------------
    # Year conversion helpers
    # ------------------------------------------------------------------

    def _current_astronomical_year(self) -> int:
        """Convert the displayed era year to astronomical year."""
        era_year = self._year_spin.value()
        if not self._current_era:
            return era_year

        if self._current_era.is_primary:
            # Forward-counting: astro_year = era_year + start_year - 1
            return era_year + self._current_era.start_year - 1
        else:
            # Backward-counting: astro_year = start_year - era_year + 1
            return self._current_era.start_year - era_year + 1

    def _set_era_year(self, era_year: int) -> None:
        """Set the displayed era year in the spin box."""
        self._year_spin.blockSignals(True)
        self._year_spin.setValue(era_year)
        self._year_spin.blockSignals(False)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def _emit_date(self) -> None:
        if self._block_signals or not self._engine or not self._engine.months:
            return

        year = self._current_astronomical_year()
        month = self._month_combo.currentIndex() + 1
        day = self._day_spin.value()

        try:
            abs_day = self._engine.date_to_absolute_day(year, month, day)
            fmt = self._engine.format_date(abs_day)
            self._valid = True
            self._formatted_label.setText(fmt)
            self._formatted_label.setStyleSheet("")
            self.date_changed.emit(self._engine.calendar_id, abs_day, fmt)
        except (ValueError, IndexError):
            self._valid = False
            self._formatted_label.setText("Invalid date")
            self._formatted_label.setStyleSheet("color: red;")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_absolute_day(self, calendar_id: str, abs_day: int) -> None:
        """Set the widget to display a specific absolute_day."""
        self._block_signals = True

        # Select the calendar
        idx = self._cal_combo.findData(calendar_id)
        if idx >= 0 and idx != self._cal_combo.currentIndex():
            self._cal_combo.setCurrentIndex(idx)
            # This triggers _on_calendar_changed which resets values

        if not self._engine:
            self._block_signals = False
            return

        # Convert to date
        d = self._engine.absolute_day_to_date(abs_day)
        year = d["year"]

        # Find matching era
        best_era: Optional[CalendarEra] = None
        best_era_year: int = year
        for era in self._engine.eras:
            if era.start_year <= year:
                best_era = era

        if best_era is None and self._engine.eras:
            best_era = self._engine.eras[0]

        self._current_era = best_era

        # Set era combo
        if best_era:
            for i in range(self._era_combo.count()):
                if self._era_combo.itemData(i) == best_era.id:
                    self._era_combo.setCurrentIndex(i)
                    break

        # Set era year
        if best_era:
            if best_era.is_primary:
                era_year = year - best_era.start_year + 1
            else:
                era_year = best_era.start_year - year + 1
        else:
            era_year = year
        self._set_era_year(era_year)

        # Set month
        if d["month"] - 1 < self._month_combo.count():
            self._month_combo.setCurrentIndex(d["month"] - 1)

        # Set day
        self._day_spin.blockSignals(True)
        self._update_day_range()
        self._day_spin.setValue(d["day"])
        self._day_spin.blockSignals(False)

        self._block_signals = False
        self._emit_date()

    @property
    def is_valid(self) -> bool:
        return self._valid

    @property
    def absolute_day(self) -> Optional[int]:
        if not self._engine or not self._valid:
            return None
        year = self._current_astronomical_year()
        month = self._month_combo.currentIndex() + 1
        day = self._day_spin.value()
        try:
            return self._engine.date_to_absolute_day(year, month, day)
        except (ValueError, IndexError):
            return None

    @property
    def calendar_id(self) -> Optional[str]:
        if not self._engine:
            return None
        return self._engine.calendar_id

    @property
    def formatted_date(self) -> str:
        return self._formatted_label.text()

    def refresh_calendars(self) -> None:
        """Refresh the calendar dropdown (call after calendars changed)."""
        self._refresh_calendar_list()