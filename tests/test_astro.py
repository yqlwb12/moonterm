"""Tests for the ephemeris.

Reference values come from Meeus, *Astronomical Algorithms* (2nd ed.)
examples, and from published new/full moon times from the Astronomical
Almanac (to the minute).
"""

import unittest
from datetime import datetime, timedelta, timezone

from moonterm import astro


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class JulianDayTest(unittest.TestCase):
    def test_j2000(self):
        self.assertAlmostEqual(astro.julian_day(utc(2000, 1, 1, 12)), 2451545.0, places=9)

    def test_known_date(self):
        # 1957 October 4.81 UT, the launch of Sputnik 1.
        self.assertAlmostEqual(astro.julian_day(utc(1957, 10, 4, 19, 26, 24)), 2436116.31, places=2)

    def test_round_trip(self):
        for when in (utc(1900, 1, 1), utc(2026, 10, 31, 12, 23, 45), utc(2099, 12, 31, 23, 59)):
            back = astro.julian_day_to_datetime(astro.julian_day(when))
            self.assertLess(abs((back - when).total_seconds()), 0.002)

    def test_naive_is_utc(self):
        naive = datetime(2026, 10, 31, 12, 0)
        self.assertAlmostEqual(astro.julian_day(naive), astro.julian_day(utc(2026, 10, 31, 12)), places=9)


class AgainstMeeusTest(unittest.TestCase):
    """Meeus example 47.a: 1992 April 12.0 TD."""

    jd = 2448724.5

    def test_moon_longitude(self):
        # Published apparent longitude is 133.162655 deg; we work without
        # nutation, hence the slightly looser bound.
        self.assertAlmostEqual(astro.moon_longitude(self.jd), 133.1627, delta=0.02)

    def test_moon_distance(self):
        self.assertAlmostEqual(astro.moon_distance(self.jd), 368410.0, delta=50.0)

    def test_sun_longitude(self):
        # Example 25.b: 1992 October 13.0 TD, true longitude 199.90988 deg.
        self.assertAlmostEqual(astro.sun_longitude(2448908.5), 199.90988, delta=0.002)


class PhaseTimesTest(unittest.TestCase):
    """Published phase times, UT.  We allow ten minutes."""

    NEW_MOONS = (
        utc(2017, 8, 21, 18, 30),
        utc(2024, 1, 11, 11, 57),
        utc(2024, 4, 8, 18, 21),
        utc(2026, 8, 12, 17, 37),
    )
    FULL_MOONS = (
        utc(2019, 1, 21, 5, 16),
        utc(2023, 8, 31, 1, 35),
        utc(2024, 4, 23, 23, 49),
        utc(2024, 9, 18, 2, 34),
    )

    def test_new_moons(self):
        for expected in self.NEW_MOONS:
            got = astro.next_new_moon(expected - timedelta(hours=12))
            self.assertLess(abs((got - expected).total_seconds()), 600, msg=str(expected))

    def test_full_moons(self):
        for expected in self.FULL_MOONS:
            got = astro.next_full_moon(expected - timedelta(hours=12))
            self.assertLess(abs((got - expected).total_seconds()), 600, msg=str(expected))

    def test_new_moon_is_dark(self):
        when = astro.next_new_moon(utc(2026, 5, 1))
        phase = astro.moon_phase(when)
        self.assertLess(phase.illumination, 1e-4)
        self.assertLess(abs(phase.elongation), 0.5)
        self.assertIn(phase.name, ("New Moon", "Waxing Crescent", "Waning Crescent"))

    def test_full_moon_is_bright(self):
        when = astro.next_full_moon(utc(2026, 5, 1))
        phase = astro.moon_phase(when)
        self.assertGreater(phase.illumination, 0.9999)
        self.assertGreater(abs(phase.elongation), 179.5)

    def test_search_is_strictly_in_the_future(self):
        now = utc(2026, 10, 31, 12, 0)
        for finder in (astro.next_new_moon, astro.next_full_moon):
            self.assertGreater(finder(now), now)
            self.assertLess(finder(now) - now, timedelta(days=30))


class MoonPhaseTest(unittest.TestCase):
    def test_phase_wraps_through_a_lunation(self):
        start = utc(2026, 1, 1)
        previous = astro.moon_phase(start).phase
        for hours in range(24, 24 * 32, 24):
            current = astro.moon_phase(start + timedelta(hours=hours)).phase
            step = (current - previous) % 1.0
            self.assertGreater(step, 0.0)
            self.assertLess(step, 0.1)
            previous = current

    def test_age_tracks_phase(self):
        phase = astro.moon_phase(utc(2026, 10, 31, 4))
        self.assertAlmostEqual(phase.age_days, phase.phase * astro.SYNODIC_MONTH, places=9)

    def test_waxing_flag(self):
        self.assertTrue(astro.moon_phase(utc(2024, 4, 20)).waxing)
        self.assertFalse(astro.moon_phase(utc(2024, 4, 27)).waxing)

    def test_illumination_matches_phase(self):
        for day in range(0, 40, 3):
            phase = astro.moon_phase(utc(2026, 3, 1) + timedelta(days=day))
            self.assertGreaterEqual(phase.illumination, 0.0)
            self.assertLessEqual(phase.illumination, 1.0)
            self.assertAlmostEqual(phase.percent, phase.illumination * 100.0, places=9)

    def test_distance_is_plausible(self):
        for day in range(0, 400, 7):
            distance = astro.moon_distance(astro.julian_day(utc(2026, 1, 1)) + day)
            self.assertGreater(distance, 356000.0)
            self.assertLess(distance, 407000.0)

    def test_phase_names(self):
        cases = {0.0: "New Moon", 0.1: "Waxing Crescent", 0.25: "First Quarter",
                 0.4: "Waxing Gibbous", 0.5: "Full Moon", 0.6: "Waning Gibbous",
                 0.75: "Last Quarter", 0.9: "Waning Crescent"}
        for value, expected in cases.items():
            self.assertEqual(astro.phase_name(value), expected, msg=str(value))


if __name__ == "__main__":
    unittest.main()
