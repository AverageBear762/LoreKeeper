"""
World Garden — Calendar Engine.

Handles calendar definitions, date calculations, and the absolute_day system.
Supports custom months, weekdays, eras, and leap year rules.

All dates are stored as absolute_day (signed integer) where day 0 = 1-01-01
of the calendar's epoch. Negative absolute days represent dates before year 1.

The engine uses astronomical year numbering internally:
  - Year 1 = 1 AD / 1 CE
  - Year 0 = 1 BC / 1 BCE
  - Year -1 = 2 BC / 2 BCE
  - etc.
This makes date arithmetic simple and continuous across the BC/AD boundary.
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
    # Leap year rules
    # ------------------------------------------------------------------

    def is_leap_affected(self, rule: LeapYearRule, year: int) -> bool:
        """Check if a leap year rule applies to a given year.
        
        Works for any integer year (positive, zero, or negative) because
        Python's modulo always returns a non-negative result.
        """
        if rule.rule_type == "interval":
            return (year - rule.offset) % rule.interval == 0
        elif rule.rule_type == "exception":
            return (year - rule.offset) % rule.interval == 0
        return False

    def is_leap_year(self, year: int) -> bool:
        """Check if a given astronomical year is a leap year.

        Works for positive, zero, and negative years alike.
        """
        extra_days = 0
        for rule in self._leap_rules:
            if rule.rule_type == "interval":
                if (year - rule.offset) % rule.interval == 0:
                    extra_days += rule.days_to_add
            elif rule.rule_type == "exception":
                if (year - rule.offset) % rule.interval == 0:
                    extra_days += rule.days_to_add
        return extra_days > 0

    def get_days_in_year(self, year: int) -> int:
        """Return the total days in a given astronomical year (accounting for leap years)."""
        base = self.days_in_year
        for rule in self._leap_rules:
            if self.is_leap_affected(rule, year):
                base += rule.days_to_add
        return base

    # ------------------------------------------------------------------
    # Leap rule verification
    # ------------------------------------------------------------------

    def verify_leap_rules(self) -> dict[str, Any]:
        """Verify that leap year rules are consistent and sensible.

        Returns a dict with:
          - 'valid': True if rules are consistent
          - 'warnings': list of warning strings
          - 'errors': list of error strings
        """
        warnings: list[str] = []
        errors: list[str] = []

        if not self._leap_rules:
            warnings.append("No leap year rules defined — every year has the same length.")
            return {"valid": True, "warnings": warnings, "errors": errors}

        valid_types = {"interval", "exception"}
        seen_months: set[int] = set()

        for i, rule in enumerate(self._leap_rules):
            if rule.rule_type not in valid_types:
                errors.append(f"Rule {i + 1}: unknown rule_type '{rule.rule_type}'.")

            if rule.interval <= 0:
                errors.append(f"Rule {i + 1}: interval must be positive (got {rule.interval}).")

            if rule.month < 1 or rule.month > len(self._months):
                errors.append(
                    f"Rule {i + 1}: month {rule.month} out of range "
                    f"(calendar has {len(self._months)} months)."
                )

            if rule.days_to_add == 0:
                warnings.append(f"Rule {i + 1}: days_to_add is 0 — rule has no effect.")

            if rule.rule_type == "exception":
                seen_months.add(rule.month)

        # Check for overlapping interval rules that could conflict
        interval_rules = [r for r in self._leap_rules if r.rule_type == "interval"]
        for i, r1 in enumerate(interval_rules):
            for r2 in interval_rules[i + 1:]:
                if r1.interval % r2.interval == 0 or r2.interval % r1.interval == 0:
                    warnings.append(
                        f"Interval rules with periods {r1.interval} and {r2.interval} "
                        f"are multiples — check for unexpected overlaps."
                    )

        # Check sample years for common errors
        for sample in [1, 4, 100, 400, 0, -4, -100, -400]:
            extra = 0
            for rule in self._leap_rules:
                if self.is_leap_affected(rule, sample):
                    extra += rule.days_to_add
            if extra < 0:
                warnings.append(f"Year {sample} has net negative leap days ({extra}).")

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Date calculations
    # ------------------------------------------------------------------

    def year_to_absolute_day(self, year: int) -> int:
        """Return the absolute day of January 1 for a given astronomical year.

        Day 0 = Jan 1, astronomical year 1 (= 1 AD / 1 CE).

        For year >= 1: positive day, counting forward from year 1.
        For year <= 0: negative day, counting backward from year 1.
          - year_to_absolute_day(0)  = -days_in_year(0)   (Jan 1, 1 BC)
          - year_to_absolute_day(-1) = -(days_in_year(-1) + days_in_year(0))
        """
        if year >= 1:
            return sum(self.get_days_in_year(y) for y in range(1, year))
        else:
            return -sum(self.get_days_in_year(y) for y in range(year, 1))

    def date_to_absolute_day(self, year: int, month: int, day: int) -> int:
        """Convert a calendar date to absolute_day (signed integer).

        Args:
            year: Astronomical year (1 = 1 AD, 0 = 1 BC, -1 = 2 BC, etc.)
            month: Month number (1-based)
            day: Day of month (1-based)

        Returns:
            Signed absolute day. Day 0 = first day of astronomical year 1.
        """
        abs_day = self.year_to_absolute_day(year)

        # Add days for months before the given month
        for i in range(month - 1):
            days_in_this_month = self._months[i].days
            # Check if this month gets extra leap days
            for rule in self._leap_rules:
                if rule.month == (i + 1) and self.is_leap_affected(rule, year):
                    days_in_this_month += rule.days_to_add
            abs_day += days_in_this_month

        # Add days in the current month (1-based to 0-based)
        abs_day += (day - 1)
        return abs_day

    def absolute_day_to_date(self, abs_day: int) -> dict[str, Any]:
        """Convert an absolute_day to (year, month, day, weekday, era).

        Works for any signed integer absolute_day (including negative).

        Returns:
            dict with keys: year (astronomical), month, day, weekday_name,
                            weekday_index, era_name, era_abbr, era_year,
                            is_leap, absolute_day
        """
        original_abs_day = abs_day

        # ---------------------------------------------------------------
        # Walk forward (abs_day >= 0) or backward (abs_day < 0) to find year
        # ---------------------------------------------------------------
        if abs_day >= 0:
            remaining = abs_day
            year = 1
            while True:
                days_this_year = self.get_days_in_year(year)
                if remaining < days_this_year:
                    break
                remaining -= days_this_year
                year += 1
        else:
            remaining = abs_day
            year = 0
            while True:
                days_this_year = self.get_days_in_year(year)
                if remaining + days_this_year >= 0:
                    remaining += days_this_year
                    break
                remaining += days_this_year
                year -= 1

        # ---------------------------------------------------------------
        # Find month within the year
        # ---------------------------------------------------------------
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
            month_idx = i + 1  # Fall through to last month

        month_num = month_idx + 1
        day_num = int(remaining) + 1

        # ---------------------------------------------------------------
        # Weekday (Python's modulo handles negative numbers correctly)
        # ---------------------------------------------------------------
        weekday_idx = original_abs_day % len(self._weekdays) if self._weekdays else 0
        weekday_name = self._weekdays[weekday_idx].name if self._weekdays else ""

        # ---------------------------------------------------------------
        # Era
        # ---------------------------------------------------------------
        current_era: Optional[CalendarEra] = None
        for era in self._eras:
            if era.start_year <= year:
                current_era = era

        # If no era matches (year before all eras), use the first era
        if current_era is None and self._eras:
            current_era = self._eras[0]

        # Era year
        era_year = year
        if current_era:
            if current_era.is_primary:
                # Forward-counting era (AD/CE): era_year = year - start_year + 1
                era_year = year - current_era.start_year + 1
            else:
                # Backward-counting era (BC/BCE): era_year = start_year - year + 1
                era_year = current_era.start_year - year + 1

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
            "absolute_day": original_abs_day,
        }

    # ------------------------------------------------------------------
    # Date manipulation
    # ------------------------------------------------------------------

    def add_days(self, year: int, month: int, day: int, days: int) -> dict[str, Any]:
        """Add a number of days to a date and return the resulting date.

        Args:
            year: Astronomical year
            month: Month (1-based)
            day: Day (1-based)
            days: Number of days to add (can be negative)

        Returns:
            dict with the same structure as absolute_day_to_date
        """
        abs_day = self.date_to_absolute_day(year, month, day)
        return self.absolute_day_to_date(abs_day + days)

    def days_between(
        self, year1: int, month1: int, day1: int,
        year2: int, month2: int, day2: int,
    ) -> int:
        """Calculate the number of days between two dates.

        Returns (date2 - date1) in days. Result is negative if date2 < date1.
        """
        abs1 = self.date_to_absolute_day(year1, month1, day1)
        abs2 = self.date_to_absolute_day(year2, month2, day2)
        return abs2 - abs1

    # ------------------------------------------------------------------
    # Date validation
    # ------------------------------------------------------------------

    def validate_date(self, year: int, month: int, day: int) -> dict[str, Any]:
        """Validate a calendar date.

        Args:
            year: Astronomical year
            month: Month (1-based)
            day: Day (1-based)

        Returns:
            dict with 'valid' (bool) and optionally 'error' (str).
        """
        if not self._months:
            return {"valid": False, "error": "Calendar has no months defined."}

        if month < 1 or month > len(self._months):
            return {
                "valid": False,
                "error": f"Month {month} out of range (1-{len(self._months)}).",
            }

        max_days = self._months[month - 1].days
        for rule in self._leap_rules:
            if rule.month == month and self.is_leap_affected(rule, year):
                max_days += rule.days_to_add

        if max_days < 1:
            return {
                "valid": False,
                "error": f"Month {month} has no days in year {year} "
                         f"(leap rule reduced days to {max_days}).",
            }

        if day < 1 or day > max_days:
            return {
                "valid": False,
                "error": f"Day {day} out of range for month {month}, year {year} "
                         f"(1-{max_days}).",
            }

        return {"valid": True}

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_date(self, abs_day: int) -> str:
        """Format an absolute_day as a human-readable date string.

        Examples:
            format_date(0)       → "Monday, January 1, 1 AD"
            format_date(-1)      → "Sunday, December 31, 1 BC"
            format_date(738889)  → "Thursday, July 4, 2024 AD"
        """
        d = self.absolute_day_to_date(abs_day)
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

        Uses astronomical year numbering:
          - Year 1 AD = astronomical year 1
          - Year 1 BC = astronomical year 0

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

        # Create eras using astronomical year numbering:
        #   BC era starts at year 0 (astronomical) = 1 BC
        #   AD era starts at year 1 (astronomical) = 1 AD
        crud.create_calendar_era(CalendarEra(
            calendar_id=cid, name="Before Christ", abbreviation="BC",
            start_year=0, is_primary=False, created_at=now,
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