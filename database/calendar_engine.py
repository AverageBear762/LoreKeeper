"""
World Garden — Calendar Engine.

Handles calendar definitions, date calculations, and the absolute_day system.
Supports custom months, weekdays, eras, and leap year rules.

All dates are stored as absolute_day (integer) where day 0 = 1-01-01 00:00:00
of the calendar's epoch. This enables date comparison across calendars.
"""

from __future__ import annotations

from typing import Any, Optional

from database import crud
from database.manager import DatabaseManager
from database.models import (
    Calendar,
    CalendarMonth,
    CalendarWeekday,
    CalendarEra,
    LeapYearRule,
    _now,
)


# ======================================================================
# CalendarEngine
# ======================================================================

class CalendarEngine:
    """Core calendar engine for date calculations."""

    # Common month lengths for the default Earth calendar
    EARTH_MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    EARTH_MONTH_NAMES = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    EARTH_WEEKDAYS = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday",
    ]

    def __init__(self, calendar_id: Optional[str] = None) -> None:
        self._calendar_id = calendar_id
        self._calendar: Optional[Calendar] = None
        self._months: list[CalendarMonth] = []
        self._weekdays: list[CalendarWeekday] = []
        self._eras: list[CalendarEra] = []
        self._leap_rules: list[LeapYearRule] = []

        if calendar_id:
            self.load(calendar_id)

    # ------------------------------------------------------------------
    # Loading / persistence
    # ------------------------------------------------------------------

    def load(self, calendar_id: str) -> bool:
        """Load a calendar and all its data from the database."""
        cal = crud.get_calendar(calendar_id)
        if not cal:
            return False
        self._calendar = cal
        self._calendar_id = cal.id
        self._months = crud.list_calendar_months(cal.id)
        self._weekdays = crud.list_calendar_weekdays(cal.id)
        self._eras = crud.list_calendar_eras(cal.id)
        self._leap_rules = crud.list_leap_year_rules(cal.id)
        self._months.sort(key=lambda m: m.position)
        self._weekdays.sort(key=lambda w: w.position)
        self._eras.sort(key=lambda e: e.start_year)
        return True

    def save(self) -> None:
        """Save the current calendar and all its data to the database."""
        if self._calendar:
            crud.update_calendar(self._calendar)
            # Persist months/weekdays/eras/rules through CRUD
            for m in self._months:
                crud.create_or_update_month(m)
            for w in self._weekdays:
                crud.create_or_update_weekday(w)
            for e in self._eras:
                crud.create_or_update_era(e)
            for r in self._leap_rules:
                crud.create_or_update_leap_rule(r)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def calendar(self) -> Optional[Calendar]:
        return self._calendar

    @property
    def calendar_id(self) -> Optional[str]:
        return self._calendar_id

    @property
    def months(self) -> list[CalendarMonth]:
        return self._months

    @property
    def weekdays(self) -> list[CalendarWeekday]:
        return self._weekdays

    @property
    def eras(self) -> list[CalendarEra]:
        return self._eras

    @property
    def leap_rules(self) -> list[LeapYearRule]:
        return self._leap_rules

    @property
    def days_in_year(self) -> int:
        """Return the total number of days in a standard (non-leap) year."""
        return sum(m.days for m in self._months)

    # ------------------------------------------------------------------
    # Date calculations
    # ------------------------------------------------------------------

    def is_leap_year(self, year: int) -> bool:
        """Check if a given year is a leap year according to the rules."""
        extra_days = 0
        for rule in self._leap_rules:
            if rule.rule_type == "interval":
                # Every N years starting at offset
                if (year - rule.offset) % rule.interval == 0:
                    extra_days += rule.days_to_add
            elif rule.rule_type == "exception":
                # Exception: when year matches this interval, apply the modifier
                if (year - rule.offset) % rule.interval == 0:
                    extra_days += rule.days_to_add
        return extra_days > 0

    def get_days_in_year(self, year: int) -> int:
        """Return the total days in a given year (accounting for leap years)."""
        base = self.days_in_year
        for rule in self._leap_rules:
            if self.is_leap_affected(rule, year):
                base += rule.days_to_add
        return base

    def is_leap_affected(self, rule: LeapYearRule, year: int) -> bool:
        """Check if a leap year rule applies to a given year."""
        if rule.rule_type == "interval":
            return (year - rule.offset) % rule.interval == 0
        elif rule.rule_type == "exception":
            return (year - rule.offset) % rule.interval == 0
        return False

    def year_to_absolute_day(self, year: int) -> int:
        """Calculate the absolute_day for the first day of a given year.

        Absolute day 0 = first day of year 1.
        """
        days = 0
        start_era_year = 1
        for era in self._eras:
            if era.start_year <= year:
                start_era_year = era.start_year

        for y in range(start_era_year, year):
            days += self.get_days_in_year(y)
        return days

    def date_to_absolute_day(self, year: int, month: int, day: int) -> int:
        """Convert a calendar date to absolute_day.

        Args:
            year: Year number (1-based, uses era starting year)
            month: Month number (1-based)
            day: Day of month (1-based)

        Returns:
            Absolute day (integer). Day 0 = first day of year 1.
        """
        abs_day = self.year_to_absolute_day(year)

        # Add days for months before the given month
        for i, m in enumerate(self._months):
            if i < month - 1:
                days_in_this_month = m.days
                # Check if this month gets extra leap days
                for rule in self._leap_rules:
                    if rule.month == (i + 1) and self.is_leap_affected(rule, year):
                        days_in_this_month += rule.days_to_add
                abs_day += days_in_this_month
            else:
                break

        # Add days in the current month (1-based to 0-based)
        abs_day += (day - 1)
        return abs_day

    def absolute_day_to_date(self, abs_day: int) -> dict[str, Any]:
        """Convert an absolute_day to (year, month, day, weekday, era).

        Returns:
            dict with keys: year, month, day, weekday_name, weekday_index,
                            era_name, era_abbr, era_year, is_leap
        """
        if abs_day < 0:
            return {"year": 0, "month": 1, "day": 1, "error": "negative days"}

        remaining = abs_day

        # Find the era
        current_era = self._eras[0] if self._eras else None
        era_start_abs = 0

        # Find year
        year = 1
        for era in self._eras:
            era_start = self.year_to_absolute_day(era.start_year)
            if era_start > remaining:
                break
            current_era = era
            era_start_abs = era_start
            year = era.start_year

        remaining -= era_start_abs

        # Walk through years
        while True:
            days_this_year = self.get_days_in_year(year)
            if remaining < days_this_year:
                break
            remaining -= days_this_year
            year += 1

        # Find month
        is_leap = self.is_leap_year(year)
        month_idx = 0
        for i, m in enumerate(self._months):
            days_this_month = m.days
            for rule in self._leap_rules:
                if rule.month == (i + 1) and self.is_leap_affected(rule, year):
                    days_this_month += rule.days_to_add
            if remaining < days_this_month:
                month_idx = i
                break
            remaining -= days_this_month
            month_idx = i + 1  # Last month if we exhaust all

        month_num = month_idx + 1
        day_num = int(remaining) + 1

        # Get weekday
        weekday_idx = abs_day % len(self._weekdays) if self._weekdays else 0
        weekday_name = self._weekdays[weekday_idx].name if self._weekdays else ""

        # Era year
        era_year = year
        if current_era:
            era_year = year - current_era.start_year + 1

        return {
            "year": year,
            "month": month_num,
            "day": day_num,
            "month_name": self._months[month_idx].name if month_idx < len(self._months) else "",
            "weekday_name": weekday_name,
            "weekday_index": weekday_idx,
            "era_name": current_era.name if current_era else "",
            "era_abbr": current_era.abbreviation if current_era else "",
            "era_year": era_year,
            "is_leap": is_leap,
            "absolute_day": abs_day,
        }

    def format_date(self, abs_day: int) -> str:
        """Format an absolute_day as a human-readable date string."""
        d = self.absolute_day_to_date(abs_day)
        if "error" in d:
            return f"Day {abs_day}"
        return (
            f"{d['weekday_name']}, {d['month_name']} {d['day']}, "
            f"{d['era_year']} {d['era_abbr']}".strip()
        )

    # ------------------------------------------------------------------
    # Default calendar seeding
    # ------------------------------------------------------------------

    @staticmethod
    def seed_default_earth_calendar() -> str:
        """Create and return the default Earth-like calendar.

        Returns the calendar ID.
        """
        now = _now()

        cal = Calendar(
            name="Gregorian",
            description="The standard Earth Gregorian calendar with 12 months, "
                        "7-day weeks, and BC/AD eras.",
            epoch="Traditional Gregorian epoch",
            created_at=now,
            updated_at=now,
        )
        crud.create_calendar(cal)
        cid = cal.id

        # Create months
        for i, (name, days) in enumerate(
            zip(CalendarEngine.EARTH_MONTH_NAMES, CalendarEngine.EARTH_MONTH_DAYS)
        ):
            crud.create_calendar_month(CalendarMonth(
                calendar_id=cid, name=name, days=days, position=i + 1,
                created_at=now,
            ))

        # Create weekdays
        for i, name in enumerate(CalendarEngine.EARTH_WEEKDAYS):
            crud.create_calendar_weekday(CalendarWeekday(
                calendar_id=cid, name=name, position=i + 1,
                created_at=now,
            ))

        # Create eras
        crud.create_calendar_era(CalendarEra(
            calendar_id=cid, name="Before Christ", abbreviation="BC",
            start_year=1, is_primary=False, created_at=now,
        ))
        crud.create_calendar_era(CalendarEra(
            calendar_id=cid, name="Anno Domini", abbreviation="AD",
            start_year=1, is_primary=True, created_at=now,
        ))

        # Leap year rule: Gregorian (every 4 years, except centuries, except 400-year centuries)
        crud.create_leap_year_rule(LeapYearRule(
            calendar_id=cid, rule_type="interval", interval=4, offset=0,
            month=2, days_to_add=1,
            description="Every 4 years",
        ))
        crud.create_leap_year_rule(LeapYearRule(
            calendar_id=cid, rule_type="exception", interval=100, offset=0,
            month=2, days_to_add=-1,
            description="Except century years",
        ))
        crud.create_leap_year_rule(LeapYearRule(
            calendar_id=cid, rule_type="interval", interval=400, offset=0,
            month=2, days_to_add=1,
            description="Except 400-year centuries",
        ))

        return cid