"""
World Garden — Calendar Manager Window.

Provides a dialog for creating, editing, and deleting calendars.
Each calendar has configurable months, weekdays, eras, leap year rules,
a live preview, drag-and-drop reordering, and default calendar support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
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
    Calendar, CalendarMonth, CalendarWeekday, CalendarEra, LeapYearRule, _now,
)

DEFAULT_CALENDAR_PATH = Path.home() / ".worldgarden" / "default_calendar.json"


def _get_default_calendar_id() -> Optional[str]:
    try:
        if DEFAULT_CALENDAR_PATH.exists():
            return json.loads(DEFAULT_CALENDAR_PATH.read_text()).get("calendar_id")
    except Exception:
        pass
    return None


def _set_default_calendar_id(calendar_id: str) -> None:
    DEFAULT_CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CALENDAR_PATH.write_text(json.dumps({"calendar_id": calendar_id}))


# ======================================================================
# ReorderableTableWidget
# ======================================================================

class ReorderableTableWidget(QTableWidget):
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
# CalendarManagerDialog
# ======================================================================

class CalendarManagerDialog(QDialog):

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📅 Calendar Manager")
        self.setMinimumSize(950, 620)
        self.resize(1050, 680)

        self._calendars: list[Calendar] = []
        self._current_calendar_id: Optional[str] = None
        self._dirty: bool = False
        self._default_cal_id: Optional[str] = _get_default_calendar_id()
        self._preview_year: int = 1

        self._build_ui()
        self._refresh_calendar_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # -- Left --
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        ll.addWidget(QLabel("<b>Calendars</b>"))
        self._cal_list = QListWidget()
        self._cal_list.currentRowChanged.connect(self._on_calendar_selected)
        ll.addWidget(self._cal_list, stretch=1)

        r1 = QHBoxLayout()
        self._btn_add = QPushButton("➕ New")
        self._btn_add.clicked.connect(self._on_add)
        r1.addWidget(self._btn_add)
        self._btn_dup = QPushButton("📋 Duplicate")
        self._btn_dup.clicked.connect(self._on_duplicate)
        self._btn_dup.setEnabled(False)
        r1.addWidget(self._btn_dup)
        ll.addLayout(r1)

        r2 = QHBoxLayout()
        self._btn_ren = QPushButton("✏️ Rename")
        self._btn_ren.clicked.connect(self._on_rename)
        self._btn_ren.setEnabled(False)
        r2.addWidget(self._btn_ren)
        self._btn_del = QPushButton("🗑 Delete")
        self._btn_del.clicked.connect(self._on_delete)
        self._btn_del.setEnabled(False)
        r2.addWidget(self._btn_del)
        ll.addLayout(r2)

        self._btn_def = QPushButton("⭐ Set as Default")
        self._btn_def.clicked.connect(self._on_set_default)
        self._btn_def.setEnabled(False)
        ll.addWidget(self._btn_def)

        self._btn_seed = QPushButton("🌍 Seed Gregorian")
        self._btn_seed.clicked.connect(self._on_seed)
        ll.addWidget(self._btn_seed)

        splitter.addWidget(left)

        # -- Right --
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self._gen = QGroupBox("General")
        gf = QFormLayout(self._gen)
        self._edit_name = QLineEdit()
        self._edit_name.setPlaceholderText("Calendar name")
        self._edit_name.textChanged.connect(self._mark_dirty)
        gf.addRow("Name:", self._edit_name)
        self._edit_desc = QPlainTextEdit()
        self._edit_desc.setMaximumHeight(80)
        self._edit_desc.setPlaceholderText("Description (optional)")
        self._edit_desc.textChanged.connect(self._mark_dirty)
        gf.addRow("Description:", self._edit_desc)
        self._edit_epoch = QLineEdit()
        self._edit_epoch.setPlaceholderText("e.g. Traditional Gregorian epoch")
        self._edit_epoch.textChanged.connect(self._mark_dirty)
        gf.addRow("Epoch:", self._edit_epoch)
        rl.addWidget(self._gen)

        self._tabs = QTabWidget()
        self._build_months_tab()
        self._build_weekdays_tab()
        self._build_eras_tab()
        self._build_leap_tab()
        self._build_preview_tab()
        rl.addWidget(self._tabs, stretch=1)

        bb = QDialogButtonBox()
        self._btn_rev = bb.addButton("↩ Revert", bb.ButtonRole.ResetRole)
        self._btn_sav = bb.addButton("💾 Save", bb.ButtonRole.AcceptRole)
        self._btn_cls = bb.addButton("Close", bb.ButtonRole.RejectRole)
        self._btn_sav.clicked.connect(self._on_save)
        self._btn_rev.clicked.connect(self._on_revert)
        self._btn_cls.clicked.connect(self._on_close)
        rl.addWidget(bb)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main = QVBoxLayout(self)
        main.addWidget(splitter)
        self._set_right_enabled(False)

    def _build_months_tab(self) -> None:
        t = QWidget()
        l = QVBoxLayout(t)
        self._mt = ReorderableTableWidget()
        self._mt.setColumnCount(3)
        self._mt.setHorizontalHeaderLabels(["Name", "Days", ""])
        self._mt.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._mt.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._mt.horizontalHeader().resizeSection(1, 60)
        self._mt.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._mt.horizontalHeader().resizeSection(2, 80)
        l.addWidget(self._mt)
        r = QHBoxLayout()
        r.addWidget(self._bma := QPushButton("➕ Add"))
        r.addWidget(self._bmr := QPushButton("➖ Remove"))
        r.addStretch()
        l.addLayout(r)
        self._bma.clicked.connect(self._on_add_month)
        self._bmr.clicked.connect(self._on_rem_month)
        self._tabs.addTab(t, "Months")

    def _build_weekdays_tab(self) -> None:
        t = QWidget()
        l = QVBoxLayout(t)
        self._wt = ReorderableTableWidget()
        self._wt.setColumnCount(2)
        self._wt.setHorizontalHeaderLabels(["Name", ""])
        self._wt.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._wt.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._wt.horizontalHeader().resizeSection(1, 80)
        l.addWidget(self._wt)
        r = QHBoxLayout()
        r.addWidget(self._bwa := QPushButton("➕ Add"))
        r.addWidget(self._bwr := QPushButton("➖ Remove"))
        r.addStretch()
        l.addLayout(r)
        self._bwa.clicked.connect(self._on_add_wd)
        self._bwr.clicked.connect(self._on_rem_wd)
        self._tabs.addTab(t, "Weekdays")

    def _build_eras_tab(self) -> None:
        t = QWidget()
        l = QVBoxLayout(t)
        self._et = QTableWidget()
        self._et.setColumnCount(5)
        self._et.setHorizontalHeaderLabels(["Name", "Abbr", "Start Year", "Primary", ""])
        self._et.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._et.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._et.horizontalHeader().resizeSection(1, 60)
        self._et.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._et.horizontalHeader().resizeSection(2, 80)
        self._et.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._et.horizontalHeader().resizeSection(3, 60)
        self._et.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._et.horizontalHeader().resizeSection(4, 80)
        l.addWidget(self._et)
        r = QHBoxLayout()
        r.addWidget(self._bea := QPushButton("➕ Add"))
        r.addWidget(self._ber := QPushButton("➖ Remove"))
        r.addStretch()
        l.addLayout(r)
        self._bea.clicked.connect(self._on_add_era)
        self._ber.clicked.connect(self._on_rem_era)
        self._tabs.addTab(t, "Eras")

    def _build_leap_tab(self) -> None:
        t = QWidget()
        l = QVBoxLayout(t)
        self._lt = QTableWidget()
        self._lt.setColumnCount(6)
        self._lt.setHorizontalHeaderLabels(["Type", "Interval", "Month", "Days ±", "Desc", ""])
        self._lt.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._lt.horizontalHeader().resizeSection(0, 80)
        self._lt.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._lt.horizontalHeader().resizeSection(1, 60)
        self._lt.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._lt.horizontalHeader().resizeSection(2, 60)
        self._lt.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._lt.horizontalHeader().resizeSection(3, 60)
        self._lt.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._lt.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._lt.horizontalHeader().resizeSection(5, 80)
        l.addWidget(self._lt)
        r = QHBoxLayout()
        r.addWidget(self._bla := QPushButton("➕ Add"))
        r.addWidget(self._blr := QPushButton("➖ Remove"))
        r.addWidget(self._bvf := QPushButton("🔍 Verify"))
        r.addStretch()
        l.addLayout(r)
        self._bla.clicked.connect(self._on_add_leap)
        self._blr.clicked.connect(self._on_rem_leap)
        self._bvf.clicked.connect(self._on_verify)
        self._tabs.addTab(t, "Leap Rules")

    def _build_preview_tab(self) -> None:
        t = QWidget()
        l = QVBoxLayout(t)
        nav = QHBoxLayout()
        self._bpr = QPushButton("◀")
        self._bpr.clicked.connect(lambda: self._shift_preview(-1))
        nav.addWidget(self._bpr)
        self._lbl_yr = QLabel("Year 1")
        self._lbl_yr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_yr.setStyleSheet("font-size: 16px; font-weight: bold;")
        nav.addWidget(self._lbl_yr, stretch=1)
        self._bnx = QPushButton("▶")
        self._bnx.clicked.connect(lambda: self._shift_preview(1))
        nav.addWidget(self._bnx)
        l.addLayout(nav)
        self._pg = QGridLayout()
        self._pg.setSpacing(2)
        l.addLayout(self._pg)
        l.addStretch()
        self._tabs.addTab(t, "Preview")

    # ------------------------------------------------------------------
    # Enable/disable
    # ------------------------------------------------------------------

    def _set_right_enabled(self, on: bool) -> None:
        self._gen.setEnabled(on)
        self._tabs.setEnabled(on)
        self._btn_sav.setEnabled(on)
        self._btn_rev.setEnabled(on)
        self._btn_ren.setEnabled(on)
        self._btn_del.setEnabled(on)
        self._btn_dup.setEnabled(on)
        self._btn_def.setEnabled(on)

    # ------------------------------------------------------------------
    # Calendar list
    # ------------------------------------------------------------------

    def _refresh_calendar_list(self) -> None:
        self._default_cal_id = _get_default_calendar_id()
        self._calendars = crud.list_calendars()
        self._cal_list.blockSignals(True)
        self._cal_list.clear()
        for cal in self._calendars:
            label = f"⭐ {cal.name}" if cal.id == self._default_cal_id else cal.name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cal.id)
            self._cal_list.addItem(item)
        self._cal_list.blockSignals(False)
        self._update_def_btn()

    def _update_def_btn(self) -> None:
        if self._current_calendar_id == self._default_cal_id:
            self._btn_def.setText("⭐ Default (current)")
            self._btn_def.setEnabled(False)
        else:
            self._btn_def.setText("⭐ Set as Default")
            self._btn_def.setEnabled(self._current_calendar_id is not None)

    # ------------------------------------------------------------------
    # Selection
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
        self._update_def_btn()
        self._load(cal)

    def _load(self, cal: Calendar) -> None:
        for w, t in [(self._edit_name, cal.name), (self._edit_desc, cal.description), (self._edit_epoch, cal.epoch)]:
            w.blockSignals(True)
            if isinstance(w, QPlainTextEdit):
                w.setPlainText(t)
            else:
                w.setText(t)
            w.blockSignals(False)
        self._dirty = False
        self._load_months(cal.id)
        self._load_weekdays(cal.id)
        self._load_eras(cal.id)
        self._load_leaps(cal.id)
        self._load_preview(cal.id)

    def _load_months(self, cid: str) -> None:
        months = sorted(crud.list_calendar_months(cid), key=lambda m: m.position)
        self._mt.setRowCount(len(months))
        for i, m in enumerate(months):
            self._mt.setItem(i, 0, QTableWidgetItem(m.name))
            di = QTableWidgetItem(); di.setData(Qt.ItemDataRole.DisplayRole, m.days)
            self._mt.setItem(i, 1, di)
            b = QPushButton("🗑"); b.clicked.connect(lambda c, r=i: self._del_month(r))
            self._mt.setCellWidget(i, 2, b)

    def _load_weekdays(self, cid: str) -> None:
        days = sorted(crud.list_calendar_weekdays(cid), key=lambda d: d.position)
        self._wt.setRowCount(len(days))
        for i, d in enumerate(days):
            self._wt.setItem(i, 0, QTableWidgetItem(d.name))
            b = QPushButton("🗑"); b.clicked.connect(lambda c, r=i: self._del_wd(r))
            self._wt.setCellWidget(i, 1, b)

    def _load_eras(self, cid: str) -> None:
        eras = sorted(crud.list_calendar_eras(cid), key=lambda e: e.start_year)
        self._et.setRowCount(len(eras))
        for i, e in enumerate(eras):
            self._et.setItem(i, 0, QTableWidgetItem(e.name))
            self._et.setItem(i, 1, QTableWidgetItem(e.abbreviation))
            yi = QTableWidgetItem(); yi.setData(Qt.ItemDataRole.DisplayRole, e.start_year)
            self._et.setItem(i, 2, yi)
            cb = QCheckBox(); cb.setChecked(e.is_primary); cb.toggled.connect(self._mark_dirty)
            self._et.setCellWidget(i, 3, cb)
            b = QPushButton("🗑"); b.clicked.connect(lambda c, r=i: self._del_era(r))
            self._et.setCellWidget(i, 4, b)

    def _load_leaps(self, cid: str) -> None:
        rules = crud.list_leap_year_rules(cid)
        self._lt.setRowCount(len(rules))
        for i, r in enumerate(rules):
            tc = QComboBox(); tc.addItems(["interval", "exception"]); tc.setCurrentText(r.rule_type)
            self._lt.setCellWidget(i, 0, tc)
            ni = QTableWidgetItem(); ni.setData(Qt.ItemDataRole.DisplayRole, r.interval)
            self._lt.setItem(i, 1, ni)
            mi = QTableWidgetItem(); mi.setData(Qt.ItemDataRole.DisplayRole, r.month)
            self._lt.setItem(i, 2, mi)
            di = QTableWidgetItem(); di.setData(Qt.ItemDataRole.DisplayRole, r.days_to_add)
            self._lt.setItem(i, 3, di)
            self._lt.setItem(i, 4, QTableWidgetItem(r.description))
            b = QPushButton("🗑"); b.clicked.connect(lambda c, r=i: self._del_leap(r))
            self._lt.setCellWidget(i, 5, b)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _load_preview(self, cid: str) -> None:
        while self._pg.count():
            w = self._pg.takeAt(0)
            if w.widget(): w.widget().deleteLater()

        try:
            eng = CalendarEngine(cid)
        except Exception:
            self._lbl_yr.setText("(Invalid calendar config)")
            return
        if not eng.months:
            self._lbl_yr.setText("(No months)")
            return

        year = self._preview_year
        wds = eng.weekdays
        nwd = len(wds) if wds else 7
        # Weekday header
        if wds:
            for c, wd in enumerate(wds):
                lbl = QLabel(wd.name[:3]); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("font-weight: bold; padding: 2px;")
                self._pg.addWidget(lbl, 0, c)

        ro = 1
        for mi, mo in enumerate(eng.months):
            md = mo.days
            for r in eng.leap_rules:
                if r.month == mi + 1 and eng.is_leap_affected(r, year):
                    md += r.days_to_add
            hdr = QLabel(f"<b>{mo.name} ({md})</b>")
            hdr.setStyleSheet("background-color: palette(alternate-base); padding: 2px;")
            self._pg.addWidget(hdr, ro, 0, 1, nwd)
            ro += 1

            try:
                woff = eng.date_to_absolute_day(year, mi + 1, 1) % nwd
            except Exception:
                woff = 0

            day = 1
            rn = ((woff + md) + nwd - 1) // nwd
            for rr in range(rn):
                for cc in range(nwd):
                    if rr == 0 and cc < woff:
                        self._pg.addWidget(QLabel(""), ro + rr, cc)
                    elif day <= md:
                        leap = False
                        for r in eng.leap_rules:
                            if r.month == mi + 1 and eng.is_leap_affected(r, year) and day > eng.months[mi].days:
                                leap = True
                        lbl = QLabel(str(day)); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        lbl.setStyleSheet("color: #0d6efd; font-weight: bold; padding: 2px;" if leap else "padding: 2px;")
                        self._pg.addWidget(lbl, ro + rr, cc)
                        day += 1
                    else:
                        self._pg.addWidget(QLabel(""), ro + rr, cc)
            ro += rn + 1
        self._upd_pv_label(year)

    def _upd_pv_label(self, year: int) -> None:
        try:
            eng = CalendarEngine(self._current_calendar_id) if self._current_calendar_id else None
        except Exception:
            eng = None
        if eng and eng.eras:
            era = None
            for e in eng.eras:
                if e.start_year <= year: era = e
            if era is None and eng.eras: era = eng.eras[0]
            if era:
                ey = year - era.start_year + 1 if era.is_primary else era.start_year - year + 1
                self._lbl_yr.setText(f"Year {ey} {era.abbreviation}")
                self._preview_year = year
                return
        self._lbl_yr.setText(f"Year {year}")

    def _shift_preview(self, d: int) -> None:
        self._preview_year += d
        if self._current_calendar_id:
            self._load_preview(self._current_calendar_id)

    # ------------------------------------------------------------------
    # Calendar CRUD
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        name, ok = QInputDialog.getText(self, "New Calendar", "Calendar name:")
        if not ok or not name.strip(): return
        crud.create_calendar(Calendar(name=name.strip()))
        self._refresh_calendar_list()
        self._select_by_name(name.strip())

    def _on_duplicate(self) -> None:
        if not self._current_calendar_id: return
        src = crud.get_calendar(self._current_calendar_id)
        if not src: return
        name, ok = QInputDialog.getText(self, "Duplicate", "Name:", text=f"{src.name} (copy)")
        if not ok or not name.strip(): return
        new = Calendar(name=name.strip(), description=src.description, epoch=src.epoch)
        crud.create_calendar(new)
        cid = new.id
        for m in crud.list_calendar_months(src.id):
            crud.create_calendar_month(CalendarMonth(calendar_id=cid, name=m.name, days=m.days, position=m.position))
        for w in crud.list_calendar_weekdays(src.id):
            crud.create_calendar_weekday(CalendarWeekday(calendar_id=cid, name=w.name, position=w.position))
        for e in crud.list_calendar_eras(src.id):
            crud.create_calendar_era(CalendarEra(calendar_id=cid, name=e.name, abbreviation=e.abbreviation, start_year=e.start_year, is_primary=e.is_primary))
        for r in crud.list_leap_year_rules(src.id):
            crud.create_leap_year_rule(LeapYearRule(calendar_id=cid, rule_type=r.rule_type, interval=r.interval, offset=r.offset, month=r.month, days_to_add=r.days_to_add, description=r.description))
        self._refresh_calendar_list()
        self._select_by_name(name.strip())

    def _on_rename(self) -> None:
        if not self._current_calendar_id: return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal: return
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=cal.name)
        if not ok or not name.strip(): return
        cal.name = name.strip(); cal.updated_at = _now()
        crud.update_calendar(cal)
        self._refresh_calendar_list()
        self._select_by_name(name.strip())

    def _on_delete(self) -> None:
        if not self._current_calendar_id: return
        if len(self._calendars) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the last calendar. At least one must exist.")
            return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal: return
        extra = ""
        if self._current_calendar_id == self._default_cal_id:
            extra = "\n\n⚠️ This is the DEFAULT calendar."
        reply = QMessageBox.question(self, "Delete Calendar",
            f"Delete '{cal.name}' and all its months, weekdays, eras, and leap rules?{extra}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        if self._current_calendar_id == self._default_cal_id:
            DEFAULT_CALENDAR_PATH.unlink(missing_ok=True)
            self._default_cal_id = None
        crud.delete_calendar(cal.id)
        self._current_calendar_id = None
        self._set_right_enabled(False)
        self._refresh_calendar_list()

    def _on_set_default(self) -> None:
        if not self._current_calendar_id: return
        _set_default_calendar_id(self._current_calendar_id)
        self._default_cal_id = self._current_calendar_id
        self._refresh_calendar_list()
        self._select_by_id(self._current_calendar_id)

    def _on_seed(self) -> None:
        if QMessageBox.question(self, "Seed Gregorian", "Add a Gregorian (Earth) calendar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        cid = CalendarEngine.seed_default_earth_calendar()
        self._refresh_calendar_list()
        cal = crud.get_calendar(cid)
        if cal: self._select_by_name(cal.name)

    def _select_by_name(self, name: str) -> None:
        for prefix in ("", "⭐ "):
            idx = self._cal_list.findText(f"{prefix}{name}", Qt.MatchFlag.MatchExactly)
            if idx >= 0: self._cal_list.setCurrentRow(idx); return

    def _select_by_id(self, cid: str) -> None:
        for i in range(self._cal_list.count()):
            if self._cal_list.item(i).data(Qt.ItemDataRole.UserRole) == cid:
                self._cal_list.setCurrentRow(i); return

    # ------------------------------------------------------------------
    # Save / Revert / Close
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if not self._current_calendar_id: return
        cal = crud.get_calendar(self._current_calendar_id)
        if not cal: return
        name = self._edit_name.text().strip()
        if not name: QMessageBox.warning(self, "Error", "Name is required."); return
        if self._mt.rowCount() == 0: QMessageBox.warning(self, "Error", "At least one month required."); return
        errs = self._validate()
        if errs:
            QMessageBox.warning(self, "Validation Errors", "\n".join(f"• {e}" for e in errs))
            return
        cal.name = name; cal.description = self._edit_desc.toPlainText().strip()
        cal.epoch = self._edit_epoch.text().strip(); cal.updated_at = _now()
        crud.update_calendar(cal)
        self._save_months(cal.id); self._save_weekdays(cal.id); self._save_eras(cal.id); self._save_leaps(cal.id)
        self._dirty = False
        self._refresh_calendar_list()
        self._select_by_id(cal.id)
        QMessageBox.information(self, "Saved", f"'{cal.name}' saved.")

    def _validate(self) -> list[str]:
        e: list[str] = []
        if self._mt.rowCount() == 0: e.append("At least one month required.")
        for i in range(self._mt.rowCount()):
            n = self._mt.item(i, 0).text().strip() if self._mt.item(i, 0) else ""
            if not n: e.append(f"Month {i+1}: name required.")
            d = int(self._mt.item(i, 1).data(Qt.ItemDataRole.DisplayRole) or 0) if self._mt.item(i, 1) else 0
            if d < 1: e.append(f"Month '{n or i+1}': days must be ≥1.")
        for i in range(self._wt.rowCount()):
            n = self._wt.item(i, 0).text().strip() if self._wt.item(i, 0) else ""
            if not n: e.append(f"Weekday {i+1}: name required.")
        pc = 0
        for i in range(self._et.rowCount()):
            n = self._et.item(i, 0).text().strip() if self._et.item(i, 0) else ""
            ab = self._et.item(i, 1).text().strip() if self._et.item(i, 1) else ""
            if not n: e.append(f"Era {i+1}: name required.")
            if not ab: e.append(f"Era '{n or i+1}': abbr required.")
            w = self._et.cellWidget(i, 3)
            if w and isinstance(w, QCheckBox) and w.isChecked(): pc += 1
        if self._et.rowCount() > 0 and pc == 0: e.append("At least one era must be primary.")
        for i in range(self._lt.rowCount()):
            w = self._lt.cellWidget(i, 0)
            rt = w.currentText() if w and isinstance(w, QComboBox) else "interval"
            if rt not in ("interval", "exception"): e.append(f"Leap rule {i+1}: invalid type.")
            iv = int(self._lt.item(i, 1).data(Qt.ItemDataRole.DisplayRole) or 0) if self._lt.item(i, 1) else 0
            if iv <= 0: e.append(f"Leap rule {i+1}: interval must be positive.")
            mo = int(self._lt.item(i, 2).data(Qt.ItemDataRole.DisplayRole) or 0) if self._lt.item(i, 2) else 0
            if mo < 1 or mo > self._mt.rowCount(): e.append(f"Leap rule {i+1}: month {mo} out of range.")
        return e

    def _save_months(self, cid: str) -> None:
        crud.delete_calendar_months(cid)
        for i in range(self._mt.rowCount()):
            n = self._mt.item(i, 0).text().strip() if self._mt.item(i, 0) else f"M{i+1}"
            d = int(self._mt.item(i, 1).data(Qt.ItemDataRole.DisplayRole) or 30) if self._mt.item(i, 1) else 30
            crud.create_calendar_month(CalendarMonth(calendar_id=cid, name=n, days=d, position=i+1))

    def _save_weekdays(self, cid: str) -> None:
        crud.delete_calendar_weekdays(cid)
        for i in range(self._wt.rowCount()):
            n = self._wt.item(i, 0).text().strip() if self._wt.item(i, 0) else f"D{i+1}"
            crud.create_calendar_weekday(CalendarWeekday(calendar_id=cid, name=n, position=i+1))

    def _save_eras(self, cid: str) -> None:
        crud.delete_calendar_eras(cid)
        for i in range(self._et.rowCount()):
            n = self._et.item(i, 0).text().strip() if self._et.item(i, 0) else f"Era{i+1}"
            ab = self._et.item(i, 1).text().strip() if self._et.item(i, 1) else n[:3]
            sy = int(self._et.item(i, 2).data(Qt.ItemDataRole.DisplayRole) or 1) if self._et.item(i, 2) else 1
            pr = self._et.cellWidget(i, 3).isChecked() if self._et.cellWidget(i, 3) and isinstance(self._et.cellWidget(i, 3), QCheckBox) else False
            crud.create_calendar_era(CalendarEra(calendar_id=cid, name=n, abbreviation=ab, start_year=sy, is_primary=pr))

    def _save_leaps(self, cid: str) -> None:
        crud.delete_leap_year_rules(cid)
        for i in range(self._lt.rowCount()):
            w = self._lt.cellWidget(i, 0)
            rt = w.currentText() if w and isinstance(w, QComboBox) else "interval"
            iv = int(self._lt.item(i, 1).data(Qt.ItemDataRole.DisplayRole) or 4) if self._lt.item(i, 1) else 4
            mo = int(self._lt.item(i, 2).data(Qt.ItemDataRole.DisplayRole) or 2) if self._lt.item(i, 2) else 2
            da = int(self._lt.item(i, 3).data(Qt.ItemDataRole.DisplayRole) or 1) if self._lt.item(i, 3) else 1
            ds = self._lt.item(i, 4).text().strip() if self._lt.item(i, 4) else ""
            crud.create_leap_year_rule(LeapYearRule(calendar_id=cid, rule_type=rt, interval=iv, offset=0, month=mo, days_to_add=da, description=ds))

    def _on_revert(self) -> None:
        if not self._current_calendar_id: return
        cal = crud.get_calendar(self._current_calendar_id)
        if cal: self._load(cal)

    def _on_close(self) -> None:
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved Changes", "Save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Save: self._on_save()
            elif r == QMessageBox.StandardButton.Cancel: return
        self.accept()

    # ------------------------------------------------------------------
    # Entity CRUD helpers
    # ------------------------------------------------------------------

    def _on_add_month(self) -> None:
        r = self._mt.rowCount(); self._mt.insertRow(r)
        self._mt.setItem(r, 0, QTableWidgetItem("New Month"))
        di = QTableWidgetItem(); di.setData(Qt.ItemDataRole.DisplayRole, 30); self._mt.setItem(r, 1, di)
        b = QPushButton("🗑"); b.clicked.connect(lambda: self._del_month(r)); self._mt.setCellWidget(r, 2, b)
        self._dirty = True

    def _on_rem_month(self) -> None:
        for r in sorted({it.row() for it in self._mt.selectedItems()}, reverse=True): self._del_month(r)

    def _del_month(self, r: int) -> None:
        if 0 <= r < self._mt.rowCount(): self._mt.removeRow(r); self._dirty = True

    def _on_add_wd(self) -> None:
        r = self._wt.rowCount(); self._wt.insertRow(r)
        self._wt.setItem(r, 0, QTableWidgetItem("New Day"))
        b = QPushButton("🗑"); b.clicked.connect(lambda: self._del_wd(r)); self._wt.setCellWidget(r, 1, b)
        self._dirty = True

    def _on_rem_wd(self) -> None:
        for r in sorted({it.row() for it in self._wt.selectedItems()}, reverse=True): self._del_wd(r)

    def _del_wd(self, r: int) -> None:
        if 0 <= r < self._wt.rowCount(): self._wt.removeRow(r); self._dirty = True

    def _on_add_era(self) -> None:
        r = self._et.rowCount(); self._et.insertRow(r)
        self._et.setItem(r, 0, QTableWidgetItem("New Era"))
        self._et.setItem(r, 1, QTableWidgetItem("NE"))
        yi = QTableWidgetItem(); yi.setData(Qt.ItemDataRole.DisplayRole, 1); self._et.setItem(r, 2, yi)
        self._et.setCellWidget(r, 3, QCheckBox())
        b = QPushButton("🗑"); self._et.setCellWidget(r, 4, b)
        self._dirty = True

    def _on_rem_era(self) -> None:
        for r in sorted({it.row() for it in self._et.selectedItems()}, reverse=True): self._del_era(r)

    def _del_era(self, r: int) -> None:
        if 0 <= r < self._et.rowCount(): self._et.removeRow(r); self._dirty = True

    def _on_add_leap(self) -> None:
        r = self._lt.rowCount(); self._lt.insertRow(r)
        tc = QComboBox(); tc.addItems(["interval", "exception"]); self._lt.setCellWidget(r, 0, tc)
        for c, v in [(1, 4), (2, 2), (3, 1)]:
            it = QTableWidgetItem(); it.setData(Qt.ItemDataRole.DisplayRole, v); self._lt.setItem(r, c, it)
        self._lt.setItem(r, 4, QTableWidgetItem(""))
        b = QPushButton("🗑"); self._lt.setCellWidget(r, 5, b)
        self._dirty = True

    def _on_rem_leap(self) -> None:
        for r in sorted({it.row() for it in self._lt.selectedItems()}, reverse=True): self._del_leap(r)

    def _del_leap(self, r: int) -> None:
        if 0 <= r < self._lt.rowCount(): self._lt.removeRow(r); self._dirty = True

    def _on_verify(self) -> None:
        if not self._current_calendar_id: return
        res = CalendarEngine(self._current_calendar_id).verify_leap_rules()
        if res["valid"] and not res["warnings"]:
            QMessageBox.information(self, "Verify", "All leap rules valid.")
        elif res["valid"]:
            QMessageBox.warning(self, "Verify", "Warnings:\n" + "\n".join(res["warnings"]))
        else:
            m = "Errors:\n" + "\n".join(res["errors"])
            if res["warnings"]: m += "\n\nWarnings:\n" + "\n".join(res["warnings"])
            QMessageBox.warning(self, "Verify", m)

    def _mark_dirty(self, *_: Any) -> None: self._dirty = True

    def closeEvent(self, event: Any) -> None:
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved Changes", "Save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Save: self._on_save()
            elif r == QMessageBox.StandardButton.Cancel: event.ignore(); return
        event.accept()