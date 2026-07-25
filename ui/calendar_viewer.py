"""
World Garden — CalendarViewer Widget.

A reusable QWidget that renders a live month-by-month calendar grid
for any calendar loaded from the database, with prev/next year navigation.

Adapts to any custom month structure, weekday definitions, leap year rules,
and era-based year display.

Usage:
    viewer = CalendarViewer()
    viewer.set_calendar(calendar_id)
    viewer.set_year(2024)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database.calendar_engine import CalendarEngine


class CalendarViewer(QWidget):
    """Renders a scrollable, month-by-month calendar grid for any calendar."""

    year_changed = Signal(int)           # emitted when the displayed year changes
    date_clicked = Signal(int)           # emitted with absolute_day when a day is clicked
    calendar_loaded = Signal(str)        # emitted with calendar_id after successful load

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._engine: Optional[CalendarEngine] = None
        self._year: int = 1

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        # -- Navigation bar --
        nav = QHBoxLayout()

        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedWidth(40)
        self._btn_prev.clicked.connect(self.prev_year)
        nav.addWidget(self._btn_prev)

        self._lbl_year = QLabel("No calendar loaded")
        self._lbl_year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_year.setStyleSheet("font-size: 16px; font-weight: bold;")
        nav.addWidget(self._lbl_year, stretch=1)

        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedWidth(40)
        self._btn_next.clicked.connect(self.next_year)
        nav.addWidget(self._btn_next)

        main.addLayout(nav)

        # -- Scrollable grid area --
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(3)
        scroll.setWidget(self._grid_container)

        main.addWidget(scroll, stretch=1)

        # Status label for errors
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: gray; font-style: italic; padding: 4px;")
        self._lbl_status.setVisible(False)
        main.addWidget(self._lbl_status)

        self.setMinimumHeight(200)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_calendar(self, calendar_id: str) -> None:
        """Load a calendar by ID and render it at the current year."""
        try:
            self._engine = CalendarEngine(calendar_id)
        except Exception:
            self._show_error(f"Failed to load calendar")
            return

        if not self._engine.calendar:
            self._show_error("Calendar not found")
            return

        self._lbl_status.setVisible(False)
        self.calendar_loaded.emit(calendar_id)
        self.render()

    def set_year(self, year: int) -> None:
        """Navigate to a specific year and re-render."""
        self._year = year
        if self._engine and self._engine.calendar:
            self.render()
            self.year_changed.emit(year)

    def prev_year(self) -> None:
        """Move to the previous year."""
        self.set_year(self._year - 1)

    def next_year(self) -> None:
        """Move to the next year."""
        self.set_year(self._year + 1)

    @property
    def year(self) -> int:
        return self._year

    @property
    def is_loaded(self) -> bool:
        return self._engine is not None and self._engine.calendar is not None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Render the full year calendar grid."""
        if not self._engine or not self._engine.months:
            self._show_error("No months defined")
            return

        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        year = self._year
        months = self._engine.months
        weekdays = self._engine.weekdays
        leap_rules = self._engine.leap_rules
        nwd = len(weekdays) if weekdays else 7

        self._render_header_row(weekdays, nwd)

        row = 1
        for mi, month in enumerate(months):
            row = self._render_month(mi, month, year, weekdays, leap_rules, nwd, row)

        # Year label
        self._update_year_label(year)
        self._lbl_status.setVisible(False)

    def _render_header_row(self, weekdays, nwd: int) -> None:
        if weekdays:
            for c, wd in enumerate(weekdays):
                lbl = QLabel(wd.name[:3])
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("font-weight: bold; padding: 3px; background-color: palette(alternate-base);")
                self._grid.addWidget(lbl, 0, c)

    def _render_month(
        self, mi: int, month, year: int, weekdays, leap_rules, nwd: int, start_row: int,
    ) -> int:
        """Render one month block. Returns next available row."""
        # Month header
        md = month.days
        for rule in leap_rules:
            if rule.month == mi + 1 and self._engine.is_leap_affected(rule, year):
                md += rule.days_to_add

        hdr = QLabel(f"<b>{month.name} ({md})</b>")
        hdr.setStyleSheet("background-color: palette(alternate-base); padding: 3px; margin-top: 6px;")
        self._grid.addWidget(hdr, start_row, 0, 1, nwd)
        start_row += 1

        # First-day offset
        try:
            woff = self._engine.date_to_absolute_day(year, mi + 1, 1) % nwd
        except Exception:
            woff = 0

        # Day cells
        day = 1
        rows_needed = ((woff + md) + nwd - 1) // nwd if nwd > 0 else md
        for rr in range(rows_needed):
            for cc in range(nwd):
                if rr == 0 and cc < woff:
                    self._grid.addWidget(QLabel(""), start_row + rr, cc)
                elif day <= md:
                    self._render_day_cell(mi, month, year, day, start_row + rr, cc)
                    day += 1
                else:
                    self._grid.addWidget(QLabel(""), start_row + rr, cc)

        return start_row + rows_needed + 1  # +1 gap between months

    def _render_day_cell(self, mi: int, month, year: int, day: int, r: int, c: int) -> None:
        """Render a single day cell with leap-day highlighting."""
        is_leap = False
        for rule in self._engine.leap_rules:
            if (rule.month == mi + 1 and
                self._engine.is_leap_affected(rule, year) and
                    day > self._engine.months[mi].days):
                is_leap = True

        # Create clickable label
        btn = QPushButton(str(day))
        btn.setFlat(True)
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_leap:
            btn.setStyleSheet("color: #0d6efd; font-weight: bold; border: none; padding: 0px;")
        else:
            btn.setStyleSheet("border: none; padding: 0px;")

        # Connect click signal
        abs_day = self._engine.date_to_absolute_day(year, mi + 1, day)
        btn.clicked.connect(lambda checked=False, ad=abs_day: self.date_clicked.emit(ad))

        # Tooltip
        fmt = self._engine.format_date(abs_day)
        btn.setToolTip(fmt)

        self._grid.addWidget(btn, r, c)

    def _update_year_label(self, year: int) -> None:
        """Set the year label with era formatting."""
        if self._engine and self._engine.eras:
            era = None
            for e in self._engine.eras:
                if e.start_year <= year:
                    era = e
            if era is None and self._engine.eras:
                era = self._engine.eras[0]
            if era:
                ey = year - era.start_year + 1 if era.is_primary else era.start_year - year + 1
                self._lbl_year.setText(f"Year {ey} {era.abbreviation}")
                return
        self._lbl_year.setText(f"Year {year}")

    def _show_error(self, msg: str) -> None:
        """Show an error message in the status area."""
        self._lbl_status.setText(msg)
        self._lbl_status.setVisible(True)
        self._lbl_year.setText("—")