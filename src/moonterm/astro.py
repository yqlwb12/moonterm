"""Lunar phase astronomy, in pure Python.

The Moon's geocentric ecliptic longitude is evaluated with the truncated
ELP-2000/82 series given in Meeus, *Astronomical Algorithms* (2nd ed.),
chapter 47 -- the fifty largest periodic terms, every one of them still
worth more than about 1.7 arcseconds.  The Sun's longitude comes from the
low-precision solar theory of chapter 25.

Since both longitudes are *mean* longitudes, the nutation terms cancel in
their difference: the elongation psi = lambda_moon - lambda_sun does not
need them.  Aberration (~20" on the Sun) is also left out, which is worth
less than 0.001 in the illuminated fraction.

Accuracy, measured against Meeus' worked examples in the test suite:

    lunar longitude    ~ 0.01 deg
    distance           ~ 20 km
    new/full moon      ~ 3 minutes

That is far better than a terminal moon needs, and it costs 50 lines of
tables.  The alternative -- an average synodic month from one epoch -- is
off by up to 14 hours on any given night, which is very visible when you
draw the thing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

__all__ = [
    "SYNODIC_MONTH",
    "MoonPhase",
    "julian_day",
    "julian_day_to_datetime",
    "sun_longitude",
    "moon_longitude",
    "moon_distance",
    "elongation",
    "illumination",
    "moon_phase",
    "next_new_moon",
    "next_full_moon",
    "phase_name",
]

#: Mean synodic month, in days (Meeus 49.1).
SYNODIC_MONTH = 29.530588853

#: Julian Day of the J2000.0 epoch, 2000-01-01 12:00 TT.
J2000 = 2451545.0

# Keplerian mean motions, degrees per Julian century (Meeus 47, argument D
# is the mean elongation, M the Sun's mean anomaly, M' the Moon's, F the
# argument of latitude).
_ARC = 360.0


# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------
def _as_utc(when: datetime) -> datetime:
    """Return *when* as an aware UTC datetime; naive input is assumed UTC."""
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def julian_day(when: datetime) -> float:
    """Julian Day for *when* (Gregorian calendar)."""
    when = _as_utc(when)
    year, month = when.year, when.month
    day = (
        when.day
        + (when.hour + (when.minute + (when.second + when.microsecond / 1e6) / 60.0) / 60.0)
        / 24.0
    )
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5


def julian_day_to_datetime(jd: float) -> datetime:
    """Inverse of :func:`julian_day`, as an aware UTC datetime."""
    jd = jd + 0.5
    z = math.floor(jd)
    f = jd - z
    if z < 2299161:
        a = z
    else:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4)
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)

    day_fraction = b - d - math.floor(30.6001 * e) + f
    day = int(math.floor(day_fraction))
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715

    seconds = (day_fraction - day) * 86400.0
    # Round to the nearest millisecond so callers get tidy timestamps.
    micro = int(round(seconds * 1e6))
    return datetime(year, month, day, tzinfo=timezone.utc) + timedelta(microseconds=micro)


def _centuries(jd: float) -> float:
    """Julian centuries since J2000.0."""
    return (jd - J2000) / 36525.0


def _sin(deg: float) -> float:
    return math.sin(math.radians(deg))


def _cos(deg: float) -> float:
    return math.cos(math.radians(deg))


def _wrap180(deg: float) -> float:
    """Fold an angle into (-180, 180]."""
    return (deg + 180.0) % _ARC - 180.0


# --------------------------------------------------------------------------
# Sun and Moon
# --------------------------------------------------------------------------
def sun_longitude(jd: float) -> float:
    """Geometric geocentric longitude of the Sun, degrees in [0, 360)."""
    t = _centuries(jd)
    mean_long = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    mean_anom = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    centre = (
        (1.914602 - 0.004817 * t - 0.000014 * t * t) * _sin(mean_anom)
        + (0.019993 - 0.000101 * t) * _sin(2 * mean_anom)
        + 0.000289 * _sin(3 * mean_anom)
    )
    return (mean_long + centre) % _ARC


# Each row is (D, M, M', F, coefficient of longitude in 1e-6 deg,
# coefficient of distance in 1e-3 km).  Table 47.A, truncated after the
# terms that still contribute more than ~1.7 arcseconds.
_TERMS = (
    (0, 0, 1, 0, 6288774, -20905355),
    (2, 0, -1, 0, 1274027, -3699111),
    (2, 0, 0, 0, 658314, -2955968),
    (0, 0, 2, 0, 213618, -569925),
    (0, 1, 0, 0, -185116, 48888),
    (0, 0, 0, 2, -114332, -3149),
    (2, 0, -2, 0, 58793, 246158),
    (2, -1, -1, 0, 57066, -152138),
    (2, 0, 1, 0, 53322, -170733),
    (2, -1, 0, 0, 45758, -204586),
    (0, 1, -1, 0, -40923, -129620),
    (1, 0, 0, 0, -34720, 108743),
    (0, 1, 1, 0, -30383, 104755),
    (2, 0, 0, -2, 15327, 10321),
    (0, 0, 1, 2, -12528, 0),
    (0, 0, 1, -2, 10980, 79661),
    (4, 0, -1, 0, 10675, -34782),
    (0, 0, 3, 0, 10034, -23210),
    (4, 0, -2, 0, 8548, -21636),
    (2, 1, -1, 0, -7888, 24208),
    (2, 1, 0, 0, -6766, 30824),
    (1, 0, -1, 0, -5163, -8379),
    (1, 1, 0, 0, 4987, -16675),
    (2, -1, 1, 0, 4036, -12831),
    (2, 0, 2, 0, 3994, -10445),
    (4, 0, 0, 0, 3861, -11650),
    (2, 0, -3, 0, 3665, 14403),
    (0, 1, -2, 0, -2689, -7003),
    (2, 0, -1, 2, -2602, 0),
    (2, -1, -2, 0, 2390, 10056),
    (1, 0, 1, 0, -2348, 6322),
    (2, -2, 0, 0, 2236, -9884),
    (0, 1, 2, 0, -2120, 5751),
    (0, 2, 0, 0, -2069, -4950),
    (2, -2, -1, 0, 2048, 4130),
    (2, 0, 1, -2, -1773, 0),
    (2, 0, 0, 2, -1595, -3958),
    (4, -1, -1, 0, 1215, 3258),
    (0, 0, 2, 2, -1110, 2616),
    (3, 0, -1, 0, -892, -1897),
    (2, 1, 1, 0, -810, -2117),
    (4, -1, -2, 0, 759, 2354),
    (0, 2, -1, 0, -713, 0),
    (2, 2, -1, 0, -700, -1423),
    (2, 1, -2, 0, 691, -1117),
    (2, -1, 0, -2, 596, -1571),
    (4, 0, 1, 0, 549, -1739),
    (0, 0, 4, 0, 537, 0),
    (4, -1, 0, 0, 520, -4421),
    (1, 0, -2, 0, -487, 0),
)


def _lunar_arguments(jd: float):
    """Return (L', D, M, M', F) in degrees."""
    t = _centuries(jd)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    mean_long = 218.3164477 + 481267.88123421 * t - 0.0015786 * t2 + t3 / 538841.0 - t4 / 65194000.0
    elongation_d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t2 + t3 / 545868.0 - t4 / 113065000.0
    sun_anom = 357.5291092 + 35999.0502909 * t - 0.0001536 * t2 + t3 / 24490000.0
    moon_anom = 134.9633964 + 477198.8675055 * t + 0.0087414 * t2 + t3 / 69699.0 - t4 / 14712000.0
    arg_lat = 93.272095 + 483202.0175233 * t - 0.0036539 * t2 - t3 / 3526000.0 + t4 / 863310000.0
    return mean_long, elongation_d, sun_anom, moon_anom, arg_lat


def _longitude_and_distance(jd: float):
    mean_long, d, m, mp, f = _lunar_arguments(jd)
    total_l = 0.0
    total_r = 0.0
    for cd, cm, cmp, cf, cl, cr in _TERMS:
        arg = cd * d + cm * m + cmp * mp + cf * f
        total_l += cl * _sin(arg)
        if cr:
            total_r += cr * _cos(arg)
    return (mean_long + total_l / 1e6) % _ARC, total_r


def moon_longitude(jd: float) -> float:
    """Geocentric ecliptic longitude of the Moon, degrees in [0, 360)."""
    return _longitude_and_distance(jd)[0]


def moon_distance(jd: float) -> float:
    """Distance from the centre of the Earth to the centre of the Moon, km."""
    return 385000.56 + _longitude_and_distance(jd)[1] / 1000.0


def elongation(jd: float) -> float:
    """Signed elongation, Moon minus Sun, in degrees, folded to (-180, 180].

    Positive values mean the Moon is east of the Sun: waxing, lit on the
    right as seen from the northern hemisphere.  Zero is new moon, 180 is
    full moon.
    """
    return _wrap180(moon_longitude(jd) - sun_longitude(jd))


def illumination(jd: float) -> float:
    """Illuminated fraction of the disc, 0.0 (new) to 1.0 (full)."""
    return (1.0 - _cos(elongation(jd))) / 2.0


# --------------------------------------------------------------------------
# Phase names
# --------------------------------------------------------------------------
_PHASES = (
    ("New Moon", 0.00, 0.02),
    ("Waxing Crescent", 0.02, 0.23),
    ("First Quarter", 0.23, 0.27),
    ("Waxing Gibbous", 0.27, 0.48),
    ("Full Moon", 0.48, 0.52),
    ("Waning Gibbous", 0.52, 0.73),
    ("Last Quarter", 0.73, 0.77),
    ("Waning Crescent", 0.77, 0.98),
    ("New Moon", 0.98, 1.01),
)


def phase_name(phase: float) -> str:
    """Human name for a phase index in [0, 1)."""
    p = phase % 1.0
    for name, lo, hi in _PHASES:
        if lo <= p < hi:
            return name
    return "New Moon"


# --------------------------------------------------------------------------
# The one object callers actually want
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MoonPhase:
    """Everything a terminal moon needs to know about one instant."""

    when: datetime
    jd: float
    elongation: float
    illumination: float
    phase: float
    distance_km: float

    @property
    def waxing(self) -> bool:
        """True while the Moon is growing (new -> full)."""
        return self.elongation > 0

    @property
    def age_days(self) -> float:
        """Days since the last new moon, on the mean synodic month."""
        return self.phase * SYNODIC_MONTH

    @property
    def name(self) -> str:
        return phase_name(self.phase)

    @property
    def percent(self) -> float:
        """Illumination as a percentage, 0..100."""
        return self.illumination * 100.0

    def next_new_moon(self) -> datetime:
        return next_new_moon(self.when)

    def next_full_moon(self) -> datetime:
        return next_full_moon(self.when)


def moon_phase(when: datetime | None = None) -> MoonPhase:
    """Phase data for *when* (defaults to now, UTC)."""
    if when is None:
        when = datetime.now(timezone.utc)
    when = _as_utc(when)
    jd = julian_day(when)
    psi = elongation(jd)
    return MoonPhase(
        when=when,
        jd=jd,
        elongation=psi,
        illumination=(1.0 - _cos(psi)) / 2.0,
        # Phase index: fraction of the synodic month since the last new moon,
        # i.e. the elongation measured eastward, normalised to [0, 1).
        phase=(psi % _ARC) / _ARC,
        distance_km=moon_distance(jd),
    )


# --------------------------------------------------------------------------
# Root finding: the next new or full moon
# --------------------------------------------------------------------------
def _solve(jd_start: float, target: float, max_days: float = 32.0) -> float:
    """Find the first jd > jd_start where elongation(djd) == target (mod 360)."""

    def residual(jd: float) -> float:
        # Distance travelled past *target*, in (-180, 180].
        return _wrap180(elongation(jd) - target)

    step = 0.25
    lo = jd_start
    f_lo = residual(lo)
    while lo - jd_start < max_days:
        hi = lo + step
        f_hi = residual(hi)
        # A jump of roughly a full turn means we sailed over the 180-wrap
        # rather than across the target; keep walking.
        if abs(f_hi - f_lo) < 90.0 and f_lo * f_hi <= 0.0:
            for _ in range(80):
                mid = (lo + hi) / 2.0
                f_mid = residual(mid)
                if abs(hi - lo) < 1e-6 or f_mid == 0.0:
                    break
                if f_lo * f_mid <= 0.0:
                    hi = mid
                else:
                    lo, f_lo = mid, f_mid
            return (lo + hi) / 2.0
        lo, f_lo = hi, f_hi
    raise RuntimeError("no lunar phase found within %.0f days" % max_days)


def _tidy(dt: datetime) -> datetime:
    """Round to the nearest second: phase times are good to minutes, and
    ``17:26:16.649599`` is nobody's idea of a nice timestamp."""
    return (dt + timedelta(microseconds=500000)).replace(microsecond=0)


def next_new_moon(when: datetime) -> datetime:
    """The next new moon strictly after *when*."""
    when = _as_utc(when)
    return _tidy(julian_day_to_datetime(_solve(julian_day(when) + 0.02, 0.0)))


def next_full_moon(when: datetime) -> datetime:
    """The next full moon strictly after *when*."""
    when = _as_utc(when)
    return _tidy(julian_day_to_datetime(_solve(julian_day(when) + 0.02, 180.0)))
