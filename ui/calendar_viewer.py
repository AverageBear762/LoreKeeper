"""
World Garden — CalendarViewer Widget.

A reusable QWidget that renders a single-month calendar grid for any
custom calendar configuration. Accepts raw data (months, weekdays,
eras, leap rules) — no DB connection required — so it can show
live, unsaved previews.

API:
    viewer.set_calendar_data(months, weekdays, eras, leap_rules, calendar)
    viewer.set_year(2024)
    viewer.set_month(0)
    viewer.goto_prev_month() / goto_next_month()
    viewer.goto_prev_year() / goto_next_year()

Signals:
    date_clicked(int) — emits absolute_day of clicked day cell
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from database.calendar_engine import CalendarEngine
from database.models import Calendar, CalendarMonth, CalendarWeekday, CalendarEra, LeapYearRule


class CalendarViewer(QWidget):
    """Single-month calendar grid viewer. Adapts to any calendar structure."""

    date_clicked = Signal(int)  # absolute_day

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._engine = CalendarEngine()
        self._year: int = 1
        self._month_index: int = 0  # 0-based index into months list
        self._has_data: bool = False

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)

        # ------- Navigation bar: ◀ year spinner ▶ | ◀◀ month ◀▶ ▶▶ -------
        nav = QHBoxLayout()

        self._btn_prev_year = QPushButton("◀◀")
        self._btn_prev_year.setFixedWidth(36)
        self._btn_prev_year.setToolTip("Previous year")
        self._btn_prev_year.clicked.connect(self.goto_prev_year)
        nav.addWidget(self._btn_prev_year)

        self._year_spin = QSpinBox()
        self._year_spin.setRange(-999999, 999999)
        self._year_spin.setValue(1)
        self._year_spin.setToolTip("Year (astronomical)")
        self._year_spin.valueChanged.connect(self._on_year_spin)
        nav.addWidget(self._year_spin)

        self._btn_next_year = QPushButton("▶▶")
        self._btn_next_year.setFixedWidth(36)
        self._btn_next_year.setToolTip("Next year")
        self._btn_next_year.clicked.connect(self.goto_next_year)
        nav.addWidget(self._btn_next_year)

        nav.addSpacing(12)

        self._btn_prev_month = QPushButton("◀")
        self._btn_prev_month.setFixedWidth(30)
        self._btn_prev_month.setToolTip("Previous month")
        self._btn_prev_month.clicked.connect(self.goto_prev_month)
        nav.addWidget(self._btn_prev_month)

        self._lbl_month = QLabel("—")
        self._lbl_month.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_month.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._lbl_month.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        nav.addWidget(self._lbl_month, stretch=1)

        self._btn_next_month = QPushButton("▶")
        self._btn_next_month.setFixedWidth(30)
        self._btn_next_month.setToolTip("Next month")
        self._btn_next_month.clicked.connect(self.goto_next_month)
        nav.addWidget(self._btn_next_month)

        main.addLayout(nav)

        # ------- Era-formatted year label -------
        self._lbl_era = QLabel("")
        self._lbl_era.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_era.setStyleSheet("font-size: 12px; color: gray; font-style: italic;")
        main.addWidget(self._lbl_era)

        # ------- Grid -------
        self._grid = QGridLayout()
        self._grid.setSpacing(1)
        main.addLayout(self._grid)

        main.addStretch()

        # ------- Status -------
        self._lbl_status = QLabel("No calendar data loaded")
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.setStyleSheet("color: gray; padding: 20px;")
        main.addWidget(self._lbl_status)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_calendar_data(
        self,
        months: list[CalendarMonth],
        weekdays: list[CalendarWeekday],
        eras: list[CalendarEra],
        leap_rules: list[LeapYearRule],
        calendar: Optional[Calendar] = None,
    ) -> None:
        """Load raw calendar configuration without a DB connection."""
        self._engine.load_from_data(months, weekdays, eras, leap_rules, calendar)
        self._has_data = bool(months)

        if not months:
            self._show_status("No months defined")
            return

        # Clamp month index
        if self._month_index >= len(months):
            self._month_index = 0

        self._lbl_status.setVisible(False)
        self._render()

    def set_year(self, year: int) -> None:
        self._year = year
        self._year_spin.blockSignals(True)
        self._year_spin.setValue(year)
        self._year_spin.blockSignals(False)
        if self._has_data:
            self._render()

    def set_month(self, month_index: int) -> None:
        months = self._engine.months
        if not months:
            return
        self._month_index = max(0, min(month_index, len(months) - 1))
        if self._has_data:
            self._render()

    def goto_prev_month(self) -> None:
        months = self._engine.months
        if not months:
            return
        self._month_index = (self._month_index - 1) % len(months)
        if self._month_index == len(months) - 1:
            self._year -= 1
            self._year_spin.blockSignals(True)
            self._year_spin.setValue(self._year)
            self._year_spin.blockSignals(False)
        if self._has_data:
            self._render()

    def goto_next_month(self) -> None:
        months = self._engine.months
        if not months:
            return
        self._month_index = (self._month_index + 1) % len(months)
        if self._month_index == 0:
            self._year += 1
            self._year_spin.blockSignals(True)
            self._year_spin.setValue(self._year)
            self._year_spin.blockSignals(False)
        if self._has_data:
            self._render()

    def goto_prev_year(self) -> None:
        self._year -= 1
        self._year_spin.blockSignals(True)
        self._year_spin.setValue(self._year)
        self._year_spin.blockSignals(False)
        if self._has_data:
            self._render()

    def goto_next_year(self) -> None:
        self._year += 1
        self._year_spin.blockSignals(True)
        self._year_spin.setValue(self._year)
        self._year_spin.blockSignals(False)
        if self._has_data:
            self._render()

    @property
    def year(self) -> int:
        return self._year

    @property
    def month_index(self) -> int:
        return self._month_index

    @property
    def is_loaded(self) -> bool:
        return self._has_data

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _on_year_spin(self, value: int) -> None:
        self._year = value
        if self._has_data:
            self._render()

    def _render(self) -> None:
        """Render the current month as a grid."""
        months = self._engine.months
        if not months or self._month_index >= len(months):
            return

        # Clear old grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        month = months[self._month_index]
        weekdays = self._engine.weekdays

        # Determine group size: named weekdays take priority, otherwise use
        # the calendar's days_in_week field (default 7 for plain numbered groups).
        # This supports calendars with tendays, decades, or other numbered-group systems.
        if weekdays:
            nwd = len(weekdays)
            use_numbered_groups = False
        else:
            cal = self._engine.calendar
            nwd = cal.days_in_week if cal and cal.days_in_week else 7
            use_numbered_groups = True

        # Days in this month (with leap rules)
        md = month.days
        for rule in self._engine.leap_rules:
            if rule.month == self._month_index + 1 and self._engine.is_leap_affected(rule, self._year):
                md += rule.days_to_add

        # Month label
        self._lbl_month.setText(f"{month.name} ({md} days)")

        # Era label
        self._lbl_era.setText("")
        if self._engine.eras:
            era = None
            for e in self._engine.eras:
                if e.start_year <= self._year:
                    era = e
            if era is None and self._engine.eras:
                era = self._engine.eras[0]
            if era:
                ey = self._year - era.start_year + 1 if era.is_primary else era.start_year - self._year + 1
                self._lbl_era.setText(f"{ey} {era.abbreviation}")

        # Header row (row 0)
        if use_numbered_groups:
            for c in range(nwd):
                lbl = QLabel(str(c + 1))
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("font-weight: bold; padding: 3px; background-color: palette(alternate-base); color: gray;")
                self._grid.addWidget(lbl, 0, c)
        else:
            for c, wd in enumerate(weekdays):
                lbl = QLabel(wd.name[:3])
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("font-weight: bold; padding: 3px; background-color: palette(alternate-base);")
                self._grid.addWidget(lbl, 0, c)

        # First-day offset
        try:
            woff = self._engine.date_to_absolute_day(self._year, self._month_index + 1, 1) % nwd
        except Exception:
            woff = 0

        # Day grid
        day = 1
        rows_needed = ((woff + md) + nwd - 1) // nwd if nwd > 0 else md
        for r in range(rows_needed):
            for c in range(nwd):
                grid_row = r + 1  # row 0 is header
                if r == 0 and c < woff:
                    self._grid.addWidget(QLabel(""), grid_row, c)
                elif day <= md:
                    self._render_day_cell(month, day, grid_row, c, md)
                    day += 1
                else:
                    self._grid.addWidget(QLabel(""), grid_row, c)

    def _render_day_cell(self, month: CalendarMonth, day: int, r: int, c: int, total_days: int) -> None:
        """Render a clickable day cell."""
        # Determine if this is a leap day
        is_leap = day > month.days  # extra days beyond base month length are leap days

        btn = QPushButton(str(day))
        btn.setFlat(True)
        btn.setFixedSize(32, 26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_leap:
            btn.setStyleSheet("color: #0d6efd; font-weight: bold; border: 1px solid #0d6efd; border-radius: 2px; padding: 0px;")
        else:
            btn.setStyleSheet("border: none; padding: 0px;")

        # Emit date_clicked with absolute_day
        abs_day = self._engine.date_to_absolute_day(self._year, self._month_index + 1, day)
        btn.clicked.connect(lambda checked=False, ad=abs_day: self.date_clicked.emit(ad))

        # Tooltip: absolute day + formatted date
        fmt = self._engine.format_date(abs_day)
        btn.setToolTip(f"Day {abs_day} — {fmt}")

        self._grid.addWidget(btn, r, c)

    def _show_status(self, msg: str) -> None:
        self._lbl_status.setText(msg)
        self._lbl_status.setVisible(True)
        self._lbl_month.setText("—")
        self._lbl_era.setText("")