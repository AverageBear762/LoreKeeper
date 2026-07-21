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
    # CRUD tests  (1–5: original, unchanged)
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
    # CalendarEngine tests  (6–15: original, adapted for new API)
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

    def test_days_in_year(self):
        """Test days_in_year calculation."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Non-leap year
        self.assertEqual(engine.get_days_in_year(2023), 365)

        # Leap year (February has 29 days)
        self.assertEqual(engine.get_days_in_year(2024), 366)

    def test_absolute_day_calculation(self):
        """Test absolute_day calculation with forward dates."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Day 0 = Jan 1, year 1 (astronomical = 1 AD)
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
        self.assertEqual(d["weekday_name"], "Monday")

        # Day 365 = Jan 1, year 2
        d = engine.absolute_day_to_date(365)
        self.assertEqual(d["year"], 2)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)
        self.assertEqual(d["weekday_name"], "Tuesday")

    def test_negative_absolute_days(self):
        """Test negative absolute_day values (dates before year 1 / BC)."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Day -1 = Dec 31, year 0 (= 1 BC)
        d = engine.absolute_day_to_date(-1)
        self.assertEqual(d["year"], 0, "Year should be 0 (astronomical = 1 BC)")
        self.assertEqual(d["month"], 12)
        self.assertEqual(d["day"], 31)
        self.assertEqual(d["era_abbr"], "BC")
        self.assertEqual(d["era_year"], 1)  # 1 BC

        # Day -366 = Jan 1, year 0 (year 0 is a leap year = 366 days)
        d = engine.absolute_day_to_date(-366)
        self.assertEqual(d["year"], 0)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)

        # Day -367 = Dec 31, year -1 (= 2 BC)
        d = engine.absolute_day_to_date(-367)
        self.assertEqual(d["year"], -1, "Year should be -1 (astronomical = 2 BC)")
        self.assertEqual(d["month"], 12)
        self.assertEqual(d["day"], 31)
        self.assertEqual(d["era_abbr"], "BC")
        self.assertEqual(d["era_year"], 2)  # 2 BC

    def test_roundtrip_date(self):
        """Test date -> absolute_day -> date roundtrip."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        test_cases = [
            (2024, 1, 1),
            (2024, 2, 29),
            (2024, 12, 31),
            (2023, 3, 15),
            (2000, 1, 1),
            (1900, 1, 1),
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

        abs_day = engine.date_to_absolute_day(2024, 1, 1)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["weekday_name"], "Monday")

        abs_day = engine.date_to_absolute_day(2024, 1, 8)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["weekday_name"], "Monday")

        abs_day = engine.date_to_absolute_day(2024, 1, 7)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["weekday_name"], "Sunday")

    def test_format_date(self):
        """Test date formatting."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        abs_day = engine.date_to_absolute_day(2024, 7, 4)
        formatted = engine.format_date(abs_day)
        self.assertIn("July", formatted)
        self.assertIn("4", formatted)
        self.assertIn("2024", formatted)
        self.assertIn("AD", formatted)

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

        rules = list_leap_year_rules(cid)
        self.assertEqual(len(rules), 3)

    def test_era_year_calculation(self):
        """Test that era year is calculated correctly with astronomical years."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Year 1 AD = absolute day 0
        d = engine.absolute_day_to_date(0)
        self.assertEqual(d["era_year"], 1)
        self.assertEqual(d["era_abbr"], "AD")

        # Year 2024 AD
        abs_day = engine.date_to_absolute_day(2024, 1, 1)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["era_year"], 2024)
        self.assertEqual(d["era_abbr"], "AD")

        # 1 BC = astronomical year 0 (year 0 hidden from user)
        abs_day = engine.date_to_absolute_day(0, 12, 31)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["era_year"], 1, "Dec 31, 1 BC should have era_year=1")
        self.assertEqual(d["era_abbr"], "BC")

        # 2 BC = astronomical year -1
        abs_day = engine.date_to_absolute_day(-1, 7, 15)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["era_year"], 2, "Year -1 should be era_year=2 (2 BC)")
        self.assertEqual(d["era_abbr"], "BC")

        # 100 BC = astronomical year -99
        abs_day = engine.date_to_absolute_day(-99, 3, 15)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["era_year"], 100, "Year -99 should be era_year=100 (100 BC)")
        self.assertEqual(d["era_abbr"], "BC")

    # ------------------------------------------------------------------
    # Negative-day roundtrip  (new)
    # ------------------------------------------------------------------

    def test_negative_roundtrip_bc(self):
        """Test negative absolute-day round trips for BC dates."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        test_cases = [
            (0, 1, 1),     # Jan 1, 1 BC
            (0, 2, 28),    # Feb 28, 1 BC
            (0, 2, 29),    # Feb 29, 1 BC (year 0 is leap!)
            (0, 12, 31),   # Dec 31, 1 BC
            (-1, 1, 1),    # Jan 1, 2 BC
            (-1, 7, 4),    # Jul 4, 2 BC
            (-99, 3, 15),  # Mar 15, 100 BC
            (-100, 12, 1), # Dec 1, 101 BC
        ]

        for year, month, day in test_cases:
            abs_day = engine.date_to_absolute_day(year, month, day)
            self.assertLess(abs_day, 0, f"BC date {year}-{month}-{day} should give negative abs_day")
            d = engine.absolute_day_to_date(abs_day)
            self.assertEqual(d["year"], year, f"Year mismatch for {year}-{month}-{day}")
            self.assertEqual(d["month"], month, f"Month mismatch for {year}-{month}-{day}")
            self.assertEqual(d["day"], day, f"Day mismatch for {year}-{month}-{day}")

    # ------------------------------------------------------------------
    # BC/AD transition — no visible year zero  (new)
    # ------------------------------------------------------------------

    def test_bc_ad_transition_no_year_zero(self):
        """Test that year 0 is never visible in formatted output."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Last day of 1 BC
        d = engine.absolute_day_to_date(-1)
        self.assertEqual(d["era_year"], 1)
        self.assertEqual(d["era_abbr"], "BC")
        self.assertNotEqual(d["era_year"], 0)

        # First day of 1 AD
        d = engine.absolute_day_to_date(0)
        self.assertEqual(d["era_year"], 1)
        self.assertEqual(d["era_abbr"], "AD")
        self.assertNotEqual(d["era_year"], 0)

        # Format them
        self.assertIn("1 BC", engine.format_date(-1))
        self.assertIn("1 AD", engine.format_date(0))

        # The day after "1 BC" is "1 AD" — no year 0 gap
        d1 = engine.absolute_day_to_date(-1)
        d2 = engine.absolute_day_to_date(0)
        self.assertEqual(d1["month"], 12)
        self.assertEqual(d1["day"], 31)
        self.assertEqual(d2["month"], 1)
        self.assertEqual(d2["day"], 1)

    # ------------------------------------------------------------------
    # Date validation — ValueError tests  (new / adapted)
    # ------------------------------------------------------------------

    def test_validate_date_valid(self):
        """Valid dates must not raise ValueError."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # These should all pass without exception
        engine.validate_date(2024, 1, 1)
        engine.validate_date(2024, 2, 29)   # Leap day
        engine.validate_date(2023, 2, 28)   # Non-leap
        engine.validate_date(2024, 12, 31)  # End of year
        engine.validate_date(2000, 2, 29)   # 400-year century leap
        engine.validate_date(1900, 2, 28)   # Century non-leap

    def test_validate_invalid_month_raises(self):
        """Invalid month numbers must raise ValueError."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        with self.assertRaises(ValueError):
            engine.validate_date(2024, 0, 1)
        with self.assertRaises(ValueError):
            engine.validate_date(2024, 13, 1)

    def test_validate_invalid_day_raises(self):
        """Invalid day numbers must raise ValueError."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        with self.assertRaises(ValueError):
            engine.validate_date(2024, 4, 0)
        with self.assertRaises(ValueError):
            engine.validate_date(2024, 4, 31)  # April has 30 days

    def test_validate_invalid_feb29_raises(self):
        """Invalid February 29 must raise ValueError."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # 2023 is not leap → Feb 29 invalid
        with self.assertRaises(ValueError):
            engine.validate_date(2023, 2, 29)

        # 1900 is not leap → Feb 29 invalid
        with self.assertRaises(ValueError):
            engine.validate_date(1900, 2, 29)

        # 2024 IS leap → Feb 29 valid
        engine.validate_date(2024, 2, 29)

    def test_validate_no_calendar_raises(self):
        """Validation with no months defined must raise ValueError."""
        cal = Calendar(name="EmptyCal")
        create_calendar(cal)
        engine = CalendarEngine(cal.id)

        with self.assertRaises(ValueError):
            engine.validate_date(2024, 1, 1)

    # ------------------------------------------------------------------
    # Custom month lengths  (new)
    # ------------------------------------------------------------------

    def test_custom_month_lengths(self):
        """Test that custom month lengths are handled correctly."""
        cal = Calendar(name="CustomMonths")
        create_calendar(cal)
        cid = cal.id

        # Two months: "Long" (45 days) and "Short" (15 days)
        create_calendar_month(CalendarMonth(calendar_id=cid, name="Long", days=45, position=1))
        create_calendar_month(CalendarMonth(calendar_id=cid, name="Short", days=15, position=2))

        engine = CalendarEngine(cid)
        self.assertEqual(engine.days_in_year, 60)

        # Day 0 = Jan 1, year 1 = Long 1
        d = engine.absolute_day_to_date(0)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["month_name"], "Long")
        self.assertEqual(d["day"], 1)

        # Day 44 = Long 45 (last day of Long)
        d = engine.absolute_day_to_date(44)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 45)

        # Day 45 = Short 1 (first day of Short)
        d = engine.absolute_day_to_date(45)
        self.assertEqual(d["month"], 2)
        self.assertEqual(d["month_name"], "Short")
        self.assertEqual(d["day"], 1)

        # Day 59 = Short 15 (last day of year)
        d = engine.absolute_day_to_date(59)
        self.assertEqual(d["month"], 2)
        self.assertEqual(d["day"], 15)

        # Day 60 = Long 1, year 2
        d = engine.absolute_day_to_date(60)
        self.assertEqual(d["year"], 2)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)

    # ------------------------------------------------------------------
    # Custom weekday counts  (new)
    # ------------------------------------------------------------------

    def test_custom_weekday_counts(self):
        """Test calendars with non-7-day week cycles."""
        cal = Calendar(name="CustomWeek")
        create_calendar(cal)
        cid = cal.id

        # 10-day week: Primidi, Duodi, Tridi, Quartidi, Quintidi, Sextidi, Septidi, Octidi, Nonidi, Decadi
        week_names = ["Primidi", "Duodi", "Tridi", "Quartidi", "Quintidi",
                      "Sextidi", "Septidi", "Octidi", "Nonidi", "Decadi"]
        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        for i, name in enumerate(week_names):
            create_calendar_weekday(CalendarWeekday(calendar_id=cid, name=name, position=i + 1))

        engine = CalendarEngine(cid)

        # Day 0 = Primidi
        self.assertEqual(engine.absolute_day_to_date(0)["weekday_name"], "Primidi")
        # Day 10 = Primidi again (cycle of 10)
        self.assertEqual(engine.absolute_day_to_date(10)["weekday_name"], "Primidi")
        # Day 9 = Decadi (last day of week)
        self.assertEqual(engine.absolute_day_to_date(9)["weekday_name"], "Decadi")
        # Negative days
        self.assertEqual(engine.absolute_day_to_date(-1)["weekday_name"], "Decadi")
        self.assertEqual(engine.absolute_day_to_date(-10)["weekday_name"], "Primidi")

    # ------------------------------------------------------------------
    # add_days and days_between — absolute-day-based  (new)
    # ------------------------------------------------------------------

    def test_add_days_absolute(self):
        """Test add_days(absolute_day, days) → int."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # Jan 1, 2024 absolute day
        abs_day = engine.date_to_absolute_day(2024, 1, 1)

        # +1 day
        self.assertEqual(engine.add_days(abs_day, 1), abs_day + 1)

        # +365 days
        self.assertEqual(engine.add_days(abs_day, 365), abs_day + 365)

        # -1 day
        self.assertEqual(engine.add_days(abs_day, -1), abs_day - 1)

    def test_days_between_absolute(self):
        """Test days_between(from_day, to_day) → int."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        day1 = engine.date_to_absolute_day(2024, 1, 1)
        day2 = engine.date_to_absolute_day(2024, 1, 2)

        self.assertEqual(engine.days_between(day1, day2), 1)
        self.assertEqual(engine.days_between(day2, day1), -1)
        self.assertEqual(engine.days_between(day1, day1), 0)

    # ------------------------------------------------------------------
    # add_days_to_date / days_between_dates — date-based  (adapted)
    # ------------------------------------------------------------------

    def test_add_days_to_date_simple(self):
        """Test adding days to a date via add_days_to_date."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        d = engine.add_days_to_date(2024, 1, 1, 1)
        self.assertEqual(d["year"], 2024)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 2)

        d = engine.add_days_to_date(2024, 1, 1, 31)
        self.assertEqual(d["year"], 2024)
        self.assertEqual(d["month"], 2)
        self.assertEqual(d["day"], 1)

        d = engine.add_days_to_date(2024, 12, 31, 1)
        self.assertEqual(d["year"], 2025)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)

    def test_add_days_to_date_negative(self):
        """Test subtracting days from a date."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        d = engine.add_days_to_date(2024, 1, 1, -1)
        self.assertEqual(d["year"], 2023)
        self.assertEqual(d["month"], 12)
        self.assertEqual(d["day"], 31)

        d = engine.add_days_to_date(1, 1, 1, -1)
        self.assertEqual(d["year"], 0)
        self.assertEqual(d["month"], 12)
        self.assertEqual(d["day"], 31)
        self.assertEqual(d["era_abbr"], "BC")
        self.assertEqual(d["era_year"], 1)

    def test_add_days_to_date_cross_era(self):
        """Test adding days that cross the BC/AD boundary."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        d = engine.add_days_to_date(0, 12, 31, 1)
        self.assertEqual(d["year"], 1)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)
        self.assertEqual(d["era_abbr"], "AD")

    def test_days_between_dates(self):
        """Test days_between_dates."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertEqual(engine.days_between_dates(2024, 1, 1, 2024, 1, 2), 1)
        self.assertEqual(engine.days_between_dates(2024, 1, 1, 2024, 1, 1), 0)
        self.assertEqual(engine.days_between_dates(2024, 1, 1, 2024, 2, 1), 31)

    def test_days_between_dates_cross_year(self):
        """Test days_between_dates across year boundaries."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertEqual(engine.days_between_dates(2024, 12, 31, 2025, 1, 1), 1)
        self.assertEqual(engine.days_between_dates(2024, 1, 1, 2025, 1, 1), 366)

    def test_days_between_dates_bc_ad(self):
        """Test days_between_dates across the BC/AD boundary."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertEqual(engine.days_between_dates(0, 12, 31, 1, 1, 1), 1)
        self.assertEqual(engine.days_between_dates(1, 1, 1, 0, 12, 31), -1)

    # ------------------------------------------------------------------
    # Era independence: eras must NOT affect canonical dates  (new)
    # ------------------------------------------------------------------

    def test_eras_do_not_alter_canonical_dates(self):
        """Test that changing eras does not change absolute day ↔ year/month/day mapping."""
        cal = Calendar(name="EraIndependence")
        create_calendar(cal)
        cid = cal.id

        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="D", position=1))

        engine = CalendarEngine(cid)
        # No eras defined yet — canonical dates must still work
        self.assertEqual(engine.date_to_absolute_day(1, 1, 1), 0)
        self.assertEqual(engine.absolute_day_to_date(0)["year"], 1)
        self.assertEqual(engine.absolute_day_to_date(29)["year"], 1)
        self.assertEqual(engine.absolute_day_to_date(30)["year"], 2)

        # Add an era starting at year 5 — should NOT change day 0 → year 1
        create_calendar_era(CalendarEra(
            calendar_id=cid, name="Later Era", abbreviation="LE",
            start_year=5, is_primary=True,
        ))
        engine2 = CalendarEngine(cid)

        # Canonical dates unchanged
        self.assertEqual(engine2.date_to_absolute_day(1, 1, 1), 0)
        self.assertEqual(engine2.absolute_day_to_date(0)["year"], 1)
        self.assertEqual(engine2.absolute_day_to_date(29)["year"], 1)
        self.assertEqual(engine2.absolute_day_to_date(30)["year"], 2)

        # Only era display metadata changed
        d = engine2.absolute_day_to_date(0)
        self.assertEqual(d["era_abbr"], "LE")  # Later Era starts at year 5, but year 1 < 5, so last matching era is none → first era
        # Actually let me check: eras sorted by start_year = [Later Era]. For year=1, era.start_year=5 <= 1? No. So current_era=None, then set to self._eras[0] = Later Era.
        # era_year = year - 5 + 1 = 1 - 5 + 1 = -3. Hmm, that's odd display but mathematically correct.
        # The key test: canonical date (year=1, month=1, day=1) is UNCHANGED.

    def test_no_eras_still_works(self):
        """Test that a calendar with no eras still produces correct canonical dates."""
        cal = Calendar(name="NoEras")
        create_calendar(cal)
        cid = cal.id
        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="D", position=1))

        engine = CalendarEngine(cid)
        self.assertEqual(len(engine.eras), 0)

        # Canonical dates work without eras
        d = engine.absolute_day_to_date(0)
        self.assertEqual(d["year"], 1)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 1)

        abs_day = engine.date_to_absolute_day(5, 1, 15)
        d = engine.absolute_day_to_date(abs_day)
        self.assertEqual(d["year"], 5)
        self.assertEqual(d["month"], 1)
        self.assertEqual(d["day"], 15)

    # ------------------------------------------------------------------
    # Leap rule verification tests  (kept)
    # ------------------------------------------------------------------

    def test_verify_leap_rules_valid(self):
        """Test leap rule verification for the default Gregorian rules."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        result = engine.verify_leap_rules()
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_verify_leap_rules_no_rules(self):
        """Test leap rule verification with no rules defined."""
        cal = Calendar(name="NoRules")
        create_calendar(cal)
        cid = cal.id
        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        engine = CalendarEngine(cid)

        result = engine.verify_leap_rules()
        self.assertTrue(result["valid"])
        self.assertGreaterEqual(len(result["warnings"]), 1)

    def test_verify_leap_rules_bad_month(self):
        """Test leap rule verification detects out-of-range months."""
        cal = Calendar(name="BadMonth")
        create_calendar(cal)
        cid = cal.id
        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        create_leap_year_rule(LeapYearRule(
            calendar_id=cid, rule_type="interval", interval=4, month=5, days_to_add=1,
        ))
        engine = CalendarEngine(cid)

        result = engine.verify_leap_rules()
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(len(result["errors"]), 1)

    # ------------------------------------------------------------------
    # Leap year rules for negative years  (kept)
    # ------------------------------------------------------------------

    def test_leap_year_negative(self):
        """Test leap year detection for negative years."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertTrue(engine.is_leap_year(0))
        self.assertFalse(engine.is_leap_year(-1))
        self.assertTrue(engine.is_leap_year(-4))

    def test_leap_year_negative_century(self):
        """Test century exception for negative years."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertFalse(engine.is_leap_year(-100))
        self.assertTrue(engine.is_leap_year(-400))

    def test_days_in_year_negative(self):
        """Test get_days_in_year for negative years."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertEqual(engine.get_days_in_year(0), 366)
        self.assertEqual(engine.get_days_in_year(-1), 365)
        self.assertEqual(engine.get_days_in_year(-100), 365)

    # ------------------------------------------------------------------
    # Additional edge cases  (new)
    # ------------------------------------------------------------------

    def test_weekday_negative(self):
        """Test weekday cycle works for negative absolute days."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        self.assertEqual(engine.absolute_day_to_date(0)["weekday_name"], "Monday")
        self.assertEqual(engine.absolute_day_to_date(-1)["weekday_name"], "Sunday")
        self.assertEqual(engine.absolute_day_to_date(-2)["weekday_name"], "Saturday")
        self.assertEqual(engine.absolute_day_to_date(-7)["weekday_name"], "Monday")
        self.assertEqual(engine.absolute_day_to_date(-8)["weekday_name"], "Sunday")

    def test_format_date_bc(self):
        """Test date formatting for BC dates."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        abs_day = engine.date_to_absolute_day(0, 12, 31)
        formatted = engine.format_date(abs_day)
        self.assertIn("December", formatted)
        self.assertIn("31", formatted)
        self.assertIn("1 BC", formatted)

        abs_day = engine.date_to_absolute_day(-1, 1, 1)
        formatted = engine.format_date(abs_day)
        self.assertIn("January", formatted)
        self.assertIn("1", formatted)
        self.assertIn("2 BC", formatted)

    def test_validate_date_valid_bc(self):
        """Test validation for valid BC dates."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        # These should not raise
        engine.validate_date(0, 2, 29)    # 1 BC is leap year
        engine.validate_date(-1, 2, 28)   # 2 BC is not leap, Feb has 28
        engine.validate_date(-100, 1, 1)  # 101 BC, Jan 1

    # ------------------------------------------------------------------
    # Phase 2: WorldDatePicker tests (test engine logic backing the picker)
    # ------------------------------------------------------------------

    def test_calendar_switching_roundtrip(self):
        """Test date round-trips correctly when switching between calendars."""
        # Create two different calendars
        cal1 = Calendar(name="CalA")
        create_calendar(cal1)
        cid1 = cal1.id
        # 10 months of 36 days each, 5-day weekdays
        for i in range(10):
            create_calendar_month(CalendarMonth(calendar_id=cid1, name=f"Month{i+1}", days=36, position=i+1))
        for i, name in enumerate(["A", "B", "C", "D", "E"]):
            create_calendar_weekday(CalendarWeekday(calendar_id=cid1, name=name, position=i+1))

        cal2 = Calendar(name="CalB")
        create_calendar(cal2)
        cid2 = cal2.id
        for i in range(4):
            create_calendar_month(CalendarMonth(calendar_id=cid2, name=f"Q{i+1}", days=91, position=i+1))
        for i, name in enumerate(["Alpha", "Beta", "Gamma"]):
            create_calendar_weekday(CalendarWeekday(calendar_id=cid2, name=name, position=i+1))

        engine1 = CalendarEngine(cid1)
        engine2 = CalendarEngine(cid2)

        # Date in CalA
        abs1 = engine1.date_to_absolute_day(5, 3, 15)
        d = engine1.absolute_day_to_date(abs1)
        self.assertEqual(d["year"], 5)
        self.assertEqual(d["month"], 3)
        self.assertEqual(d["day"], 15)

        # Same absolute_day in CalB should decode to different date
        d2 = engine2.absolute_day_to_date(abs1)
        self.assertIsInstance(d2["year"], int)
        self.assertIsInstance(d2["month"], int)
        self.assertIsInstance(d2["day"], int)

        # Switching back to CalA preserves original
        d3 = engine1.absolute_day_to_date(abs1)
        self.assertEqual(d3["year"], 5)
        self.assertEqual(d3["month"], 3)
        self.assertEqual(d3["day"], 15)

    def test_forward_and_backward_counting_eras(self):
        """Test both forward-counting (AD) and backward-counting (BC) eras."""
        cal = Calendar(name="DualEra")
        create_calendar(cal)
        cid = cal.id
        create_calendar_month(CalendarMonth(calendar_id=cid, name="M", days=30, position=1))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="D", position=1))
        # Forward era starting at year 100
        create_calendar_era(CalendarEra(calendar_id=cid, name="Post", abbreviation="P",
                                        start_year=100, is_primary=True))
        # Backward era starting at year 99
        create_calendar_era(CalendarEra(calendar_id=cid, name="Ante", abbreviation="A",
                                        start_year=99, is_primary=False))

        engine = CalendarEngine(cid)

        # Year 100 = era_year 1 Post (forward)
        d = engine.date_to_absolute_day(100, 1, 1)
        date = engine.absolute_day_to_date(d)
        self.assertEqual(date["era_abbr"], "P")
        self.assertEqual(date["era_year"], 1)

        # Year 99 = era_year 1 Ante (backward)
        d = engine.date_to_absolute_day(99, 1, 1)
        date = engine.absolute_day_to_date(d)
        self.assertEqual(date["era_abbr"], "A")
        self.assertEqual(date["era_year"], 1)

        # Year 90 = era_year 10 Ante (backward: 99 - 90 + 1 = 10)
        d = engine.date_to_absolute_day(90, 1, 1)
        date = engine.absolute_day_to_date(d)
        self.assertEqual(date["era_abbr"], "A")
        self.assertEqual(date["era_year"], 10)

        # Year 105 = era_year 6 Post (forward: 105 - 100 + 1 = 6)
        d = engine.date_to_absolute_day(105, 1, 1)
        date = engine.absolute_day_to_date(d)
        self.assertEqual(date["era_abbr"], "P")
        self.assertEqual(date["era_year"], 6)

    def test_era_display_no_year_zero(self):
        """Test that year 0 is never visible in any era display."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        for abs_day in range(-10, 11):
            d = engine.absolute_day_to_date(abs_day)
            self.assertNotEqual(d["era_year"], 0, f"era_year=0 at abs_day={abs_day}")
            # BC/AD boundary: -1 is 1 BC, 0 is 1 AD
            if abs_day < 0:
                self.assertEqual(d["era_abbr"], "BC")
            else:
                self.assertEqual(d["era_abbr"], "AD")

    def test_leap_day_feb29_valid_leap(self):
        """Feb 29 is valid in leap years."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        engine.validate_date(2024, 2, 29)  # Should not raise
        engine.validate_date(2000, 2, 29)  # 400-year exception
        engine.validate_date(0, 2, 29)     # Year 0 (1 BC) is leap

    def test_leap_day_feb29_invalid_non_leap(self):
        """Feb 29 raises ValueError in non-leap years."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        with self.assertRaises(ValueError):
            engine.validate_date(2023, 2, 29)   # Not leap
        with self.assertRaises(ValueError):
            engine.validate_date(1900, 2, 29)   # Century exception
        with self.assertRaises(ValueError):
            engine.validate_date(-1, 2, 29)     # 2 BC not leap

    def test_invalid_month_13_rejected(self):
        """Month 13 raises ValueError."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)
        with self.assertRaises(ValueError):
            engine.validate_date(2024, 13, 1)

    def test_invalid_day_32_rejected(self):
        """Day 32 raises ValueError."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)
        with self.assertRaises(ValueError):
            engine.validate_date(2024, 1, 32)

    def test_negative_absolute_day_roundtrip(self):
        """Negative absolute_day round-trips correctly."""
        cid = CalendarEngine.seed_default_earth_calendar()
        engine = CalendarEngine(cid)

        for abs_day in [0, -1, -365, -366, -731, -1000]:
            d = engine.absolute_day_to_date(abs_day)
            back = engine.date_to_absolute_day(d["year"], d["month"], d["day"])
            self.assertEqual(back, abs_day, f"Round-trip failed for abs_day={abs_day}")

    def test_era_change_preserves_canonical_dates(self):
        """Adding, modifying, or removing eras does NOT change absolute_day→date mapping."""
        cal = Calendar(name="EraTest")
        create_calendar(cal)
        cid = cal.id
        for i in range(3):
            create_calendar_month(CalendarMonth(calendar_id=cid, name=f"M{i+1}", days=30, position=i+1))
        create_calendar_weekday(CalendarWeekday(calendar_id=cid, name="D", position=1))

        engine = CalendarEngine(cid)
        # No eras
        d0 = engine.absolute_day_to_date(0)
        self.assertEqual(d0["year"], 1)

        # Add eras
        create_calendar_era(CalendarEra(calendar_id=cid, name="Old", abbreviation="O",
                                        start_year=0, is_primary=False))
        create_calendar_era(CalendarEra(calendar_id=cid, name="New", abbreviation="N",
                                        start_year=10, is_primary=True))
        engine2 = CalendarEngine(cid)

        # Canonical date unchanged regardless of eras
        d1 = engine2.absolute_day_to_date(0)
        self.assertEqual(d1["year"], 1)
        self.assertEqual(d1["month"], 1)
        self.assertEqual(d1["day"], 1)

        # Test at a year within the New era
        abs10 = engine2.date_to_absolute_day(15, 1, 1)
        d2 = engine2.absolute_day_to_date(abs10)
        self.assertEqual(d2["year"], 15)
        self.assertEqual(d2["era_abbr"], "N")
        self.assertEqual(d2["era_year"], 6)  # 15 - 10 + 1 = 6


if __name__ == "__main__":
    unittest.main()