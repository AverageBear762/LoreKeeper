"""
World Garden — Calendar Engine Tests.

Tests the CalendarEngine, calendar CRUD, and the default Earth calendar.
"""

import os
import sys
import tempfile
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.manager import DatabaseManager
from database.crud import (
    create_calendar, get_calendar, get_calendar_by_name,
    list_calendars, delete_calendar,
    create_calendar_month, list_calendar_months,
    create_calendar_weekday, list_calendar_weekdays,
    create_calendar_era, list_calendar_eras,
    create_leap_year_rule, list_leap_year_rules,
)
from database.models import Calendar, CalendarMonth, CalendarWeekday, CalendarEra, LeapYearRule
from database.calendar_engine import CalendarEngine


class TestCalendarEngine(unittest.TestCase):
    """Test the calendar engine with a temporary in-memory database."""

    @classmethod
    def setUpClass(cls):
        """Set up a fresh database for all tests."""
        cls._db_path = tempfile.mktemp(suffix=".db")
        db = DatabaseManager()
        db.open(cls._db_path, migrate=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary database."""
        db = DatabaseManager()
        db.close()
        try:
            os.unlink(cls._db_path)
        except OSError:
            pass

    def setUp(self):
        """Reset database state before each test."""
        db = DatabaseManager()
        # Clean all calendar data
        for cal in list_calendars():
            delete_calendar(cal.id)

    # ------------------------------------------------------------------
    # CRUD tests
    # ------------------------------------------------------------------

    def test_create_calendar(self):
        """Test creating a calendar definition."""
        cal = Calendar(name="Test Calendar", description="A test calendar")
        create_calendar(cal)
        fetched = get_calendar(cal.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Test Calendar")
        self.assertEqual(fetched.description, "A test calendar")
        self.assertEqual(fetched.days_in_week, 7)

    def test_get_calendar_by_name(self):
        """Test fetching a calendar by name."""
        cal = Calendar(name="TestByName", description="Test")
        create_calendar(cal)
        fetched = get_calendar_by_name("TestByName")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, cal.id)

    def test_list_calendars(self):
        """Test listing all calendars."""
        for i in range(3):
            create_calendar(Calendar(name=f"Cal{i}"))
        cals = list_calendars()
        self.assertEqual(len(cals), 3)

    def test_delete_calendar_cascades(self):
        """Test deleting a calendar removes its months, weekdays, eras, rules."""
        cal = Calendar(name="CascadeTest")
        create_calendar(cal)
        cid = cal.id

        # Add child data
        create_calendar_month(CalendarMonth(calendar_id=cid, name="Jan", days=31, position=1))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="Mon", position=1))
        create_calendar_era(CalendarEra(calendar_id=cid, name="Test Era", start_year=1))
        create_leap_year_rule(LeapYearRule(calendar_id=cid, interval=4))

        delete_calendar(cid)

        self.assertIsNone(get_calendar(cid))
        self.assertEqual(list_calendar_months(cid), [])
        self.assertEqual(list_calendar_weekdays(cid), [])
        self.assertEqual(list_calendar_eras(cid), [])
        self.assertEqual(list_leap_year_rules(cid), [])

    def test_calendar_month_crud(self):
        """Test creating and listing calendar months."""
        cal = Calendar(name="MonthTest")
        create_calendar(cal)
        cid = cal.id

        for i, (name, days) in enumerate(
            [("Jan", 31), ("Feb", 28), ("Mar", 31)], start=1
        ):
            create_calendar_month(CalendarMonth(
                calendar_id=cid, name=name, days=days, position=i,
            ))

        months = list_calendar_months(cid)
        self.assertEqual(len(months), 3)
        self.assertEqual(months[0].name, "Jan")
        self.assertEqual(months[0].days, 31)
        self.assertEqual(months[0].position, 1)
        self.assertEqual(months[2].name, "Mar")

    # ------------------------------------------------------------------
    # CalendarEngine tests
    # ------------------------------------------------------------------

    def test_engine_load_and_properties(self):
        """Test loading a calendar into the engine."""
        cal = Calendar(name="EngineTest")
        create_calendar(cal)
        cid = cal.id

        create_calendar_month(CalendarMonth(calendar_id=cid, name="M1", days=30, position=1))
        create_calendar_month(CalendarMonth(calendar_id=cid, name="M2", days=30, position=2))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="D1", position=1))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="D2", position=2))

        engine = CalendarEngine(cid)
        self.assertIsNotNone(engine.calendar)
        self.assertEqual(engine.calendar.name, "EngineTest")
        self.assertEqual(len(engine.months), 2)
        self.assertEqual(len(engine.weekdays), 2)
        self.assertEqual(engine.days_in_year, 60)

    def test_is_leap_year_interval(self):
        """Test leap year detection with interval rules."""
        cal = Calendar(name="LeapTest")
        create_calendar(cal)
        cid = cal.id

        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        create_leap_year_rule(LeapYearRule(
            calendar_id=cid, rule_type="interval", interval=4, offset=0,
            month=1, days_to_add=1,
        ))

        engine = CalendarEngine(cid)
        self.assertTrue(engine.is_leap_year(4))
        self.assertTrue(engine.is_leap_year(8))
        self.assertFalse(engine.is_leap_year(1))
        self.assertFalse(engine.is_leap_year(2))
        self.assertFalse(engine.is_leap_year(3))

    def test_gregorian_leap_year(self):
        """Test the full Gregorian leap year logic."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Standard leap years
        self.assertTrue(engine.is_leap_year(2024))
        self.assertTrue(engine.is_leap_year(2000))
        self.assertTrue(engine.is_leap_year(2400))

        # Non-leap years
        self.assertFalse(engine.is_leap_year(2023))
        self.assertFalse(engine.is_leap_year(2025))

        # Century exceptions
        self.assertFalse(engine.is_leap_year(1900))
        self.assertFalse(engine.is_leap_year(2100))
        self.assertFalse(engine.is_leap_year(2200))
        self.assertFalse(engine.is_leap_year(2300))

        # 400-year exception
        self.assertTrue(engine.is_leap_year(2000))
        self.assertTrue(engine.is_leap_year(2400))

    def test_days_in_year(self):
        """Test days_in_year calculation."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Non-leap year
        self.assertEqual(engine.get_days_in_year(2023), 365)

        # Leap year (February has 29 days)
        self.assertEqual(engine.get_days_in_year(2024), 366)

    def test_absolute_day_calculation(self):
        """Test absolute_day calculation."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Day 0 = Jan 1, year 1
        d = engine.absolute_day_to_date(0)
        self.assertEqual(d["year"], 1)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)
        self.assertEqual(d["month_name"], "January")
        self.assertEqual(d["weekday_name"], "Monday")

        # Day 364 = Dec 31, year 1 (365th day of year 1, 0-indexed)
        d = engine.absolute_day_to_date(364)
        self.assertEqual(d["year"], 1)
        self.assertEqual(d["month"], 12)
        self.assertEqual(d["day"], 31)
        self.assertEqual(d["weekday_name"], "Monday")  # 365 mod 7 = 1, so day 364 = Monday

        # Day 365 = Jan 1, year 2
        d = engine.absolute_day_to_date(365)
        self.assertEqual(d["year"], 2)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)
        self.assertEqual(d["weekday_name"], "Tuesday")

    def test_roundtrip_date(self):
        """Test date -> absolute_day -> date roundtrip."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Test a few dates
        test_cases = [
            (2024, 1, 1),    # Jan 1, 2024
            (2024, 2, 29),   # Feb 29, 2024 (leap day)
            (2024, 12, 31),  # Dec 31, 2024
            (2023, 3, 15),   # Mar 15, 2023
            (2000, 1, 1),    # Jan 1, 2000 (leap year)
            (1900, 1, 1),    # Jan 1, 1900 (not a leap year)
        ]

        for year, month, day in test_cases:
            abs_day = engine.date_to_absolute_day(year, month, day)
            d = engine.absolute_day_to_date(abs_day)
            self.assertEqual(d["year"], year, f"Year mismatch for {year}-{month}-{day}")
            self.assertEqual(d["month"], month, f"Month mismatch for {year}-{month}-{day}")
            self.assertEqual(d["day"], day, f"Day mismatch for {year}-{month}-{day}")

    def test_weekday_cycle(self):
        """Test that weekdays cycle correctly."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Jan 1, 2024 = Monday
        abs_day = engine.date_to_absolute_day(2024, 1, 1)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["weekday_name"], "Monday")

        # Jan 8, 2024 = Monday (7 days later)
        abs_day = engine.date_to_absolute_day(2024, 1, 8)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["weekday_name"], "Monday")

        # Jan 7, 2024 = Sunday
        abs_day = engine.date_to_absolute_day(2024, 1, 7)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["weekday_name"], "Sunday")

    def test_format_date(self):
        """Test date formatting."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        abs_day = engine.date_to_absolute_day(2024, 7, 4)
        formatted = engine.format_date(abs_day)
        # Should contain month, day, year info
        self.assertIn("July", formatted)
        self.assertIn("4", formatted)
        self.assertIn("2024", formatted)

    def test_default_earth_calendar_seeded(self):
        """Test that the default Earth calendar is correctly seeded."""
        cid = CalendarEngine.seed_default_earth_calendar()
        self.assertIsNotNone(cid)

        cal = get_calendar(cid)
        self.assertEqual(cal.name, "Gregorian")

        months = list_calendar_months(cid)
        self.assertEqual(len(months), 12)
        self.assertEqual(months[0].name, "January")
        self.assertEqual(months[0].days, 31)
        self.assertEqual(months[1].name, "February")
        self.assertEqual(months[1].days, 28)

        weekdays = list_calendar_weekdays(cid)
        self.assertEqual(len(weekdays), 7)
        self.assertEqual(weekdays[0].name, "Monday")

        eras = list_calendar_eras(cid)
        self.assertEqual(len(eras), 2)
        self.assertEqual(eras[0].name, "Before Christ")
        self.assertEqual(eras[0].abbreviation, "BC")

        rules = list_leap_year_rules(cid)
        self.assertEqual(len(rules), 3)

    def test_era_year_calculation(self):
        """Test that era year is calculated correctly."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Year 1 AD = absolute day 0
        d = engine.absolute_day_to_date(0)
        self.assertEqual(d["era_year"], 1)

        # Year 2024 AD
        abs_day = engine.date_to_absolute_day(2024, 1, 1)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["era_year"], 2024)
        self.assertEqual(d["era_abbr"], "AD")


if __name__ == "__main__":
    unittest.main()