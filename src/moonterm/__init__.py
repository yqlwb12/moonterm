"""moonterm -- a moon phase for your terminal.

    >>> from moonterm import moon_phase
    >>> phase = moon_phase()
    >>> phase.name
    'Waxing Gibbous'
    >>> 0.0 <= phase.illumination <= 1.0
    True

The interesting pieces are exposed here; everything else lives in
:mod:`moonterm.astro` and :mod:`moonterm.render`.
"""

from .astro import (
    SYNODIC_MONTH,
    MoonPhase,
    elongation,
    illumination,
    moon_distance,
    moon_phase,
    next_full_moon,
    next_new_moon,
    phase_name,
)
from .render import moon_lines

__version__ = "0.1.0"

__all__ = [
    "MoonPhase",
    "SYNODIC_MONTH",
    "__version__",
    "elongation",
    "illumination",
    "moon_distance",
    "moon_lines",
    "moon_phase",
    "next_full_moon",
    "next_new_moon",
    "phase_name",
]
