"""Draw a moon with text characters.

The disc is a unit circle sampled on a grid whose cells are about twice as
tall as they are wide, so a grid of *width* columns needs *width / 2* rows
to look round.

Only the terminator needs real thought.  Projected onto the sky the
boundary between light and shadow is half an ellipse with semi-minor axis
``|cos i|`` (``i`` being the phase angle), so for a point at height *v*
the boundary sits at::

    u_edge = cos(2 * pi * phase) * sqrt(1 - v**2)

with everything to the right of it lit while the Moon is waxing and
everything to the left lit while it is waning.  Sampling that per cell and
counting how many sub-pixels fall inside gives free anti-aliasing, which is
what separates a moon from a blob.

The dark patches are the near-side maria, placed by hand at roughly their
true selenographic positions.  They are not decoration for its own sake:
without them a full moon is a featureless white blob, and the maria are the
one thing that makes the Moon recognisable at a glance.
"""

from __future__ import annotations

import math

__all__ = ["moon_lines", "shade", "SIZES", "RAMP"]

#: Width presets, in columns.  Odd numbers keep the disc symmetric.
SIZES = {"small": 25, "medium": 43, "large": 71}

#: Dark to bright.  Index 0 is "no light at all".
RAMP = " .:-=+*#%@"

# Colours, as (r, g, b).
_LIT_DARK = (86, 92, 124)
_LIT_LIGHT = (250, 248, 238)
_EARTHSHINE = (46, 52, 78)

_RESET = "\x1b[0m"
_SUBSAMPLES = 4

# Near-side maria: (x, y, radius, depth) with x to the right, y up, both in
# disc radii.  The near side always faces us, so these are fixed.
_MARIA = (
    (0.60, 0.44, 0.11, 0.55),  # Mare Crisium
    (0.50, 0.16, 0.15, 0.45),  # Mare Fecunditatis
    (0.30, 0.30, 0.15, 0.50),  # Mare Tranquillitatis
    (0.26, 0.47, 0.12, 0.55),  # Mare Serenitatis
    (-0.06, 0.53, 0.19, 0.50),  # Mare Imbrium
    (-0.42, 0.12, 0.30, 0.40),  # Oceanus Procellarum
    (-0.26, -0.26, 0.14, 0.45),  # Mare Nubium
    (-0.40, -0.38, 0.09, 0.45),  # Mare Humorum
    (0.36, -0.06, 0.08, 0.40),  # Mare Nectaris
    (0.08, -0.10, 0.16, 0.30),  # Sinus Medii / Mare Vaporum
)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _albedo(x: float, y: float) -> float:
    """Relative brightness at (x, y) on the disc, 0.0 to 1.0."""
    level = 1.0
    for mx, my, radius, depth in _MARIA:
        dx = x - mx
        dy = y - my
        d2 = dx * dx + dy * dy
        if d2 < radius * radius:
            # Smooth cosine falloff, so the edges of a mare are soft.
            shade_ = 0.5 + 0.5 * math.cos(math.pi * math.sqrt(d2) / radius)
            level -= depth * shade_
    return max(0.25, level)


def shade(phase: float, width: int = 43, *, south: bool = False, earthshine: bool = True,
          texture: bool = True) -> list[list[tuple[str, tuple[int, int, int] | None]]]:
    """Return the moon as rows of ``(char, rgb_or_None)`` cells.

    ``rgb`` is ``None`` for empty space so callers can decide about colour.
    """
    phase = phase % 1.0
    width = max(9, int(width))
    if width % 2 == 0:
        width += 1
    height = max(5, int(round(width / 2.0)))

    # cos(2*pi*phase) is the terminator's semi-minor axis: +1 at new moon
    # (nothing lit), -1 at full moon (everything lit).
    axis = math.cos(2.0 * math.pi * phase)
    waxing = phase < 0.5
    lit_side = -1.0 if south else 1.0
    total = float(_SUBSAMPLES * _SUBSAMPLES)

    rows = []
    for row in range(height):
        cells = []
        for col in range(width):
            inside = 0
            lit = 0
            albedo_total = 0.0
            for sy in range(_SUBSAMPLES):
                v = ((row + (sy + 0.5) / _SUBSAMPLES) / height) * 2.0 - 1.0
                vv = v * v
                if vv > 1.0:
                    continue
                edge = axis * math.sqrt(1.0 - vv)
                for sx in range(_SUBSAMPLES):
                    u = ((col + (sx + 0.5) / _SUBSAMPLES) / width) * 2.0 - 1.0
                    if u * u + vv > 1.0:
                        continue
                    inside += 1
                    x = u * lit_side
                    if (x > edge) if waxing else (x < -edge):
                        lit += 1
                        if texture:
                            albedo_total += _albedo(x, v)

            coverage = lit / total
            if coverage > 0.0:
                albedo = (albedo_total / lit) if texture else 1.0
                brightness = coverage * albedo
                index = min(len(RAMP) - 1, int(round(brightness * (len(RAMP) - 1))))
                char = RAMP[max(1, index)]
                cells.append((char, _lerp(_LIT_DARK, _LIT_LIGHT, brightness**0.65)))
            elif inside and earthshine:
                cells.append((".", _EARTHSHINE))
            else:
                cells.append((" ", None))
        rows.append(cells)
    return rows


def moon_lines(
    phase: float,
    width: int = 43,
    *,
    south: bool = False,
    color: bool = True,
    earthshine: bool = True,
    texture: bool = True,
) -> list[str]:
    """The moon as a list of text lines, ready to print."""
    out = []
    for row in shade(phase, width, south=south, earthshine=earthshine, texture=texture):
        if not color:
            out.append("".join(char for char, _ in row).rstrip())
            continue
        parts = []
        current = None
        for char, rgb in row:
            if rgb is None:
                if current is not None:
                    parts.append(_RESET)
                    current = None
                parts.append(char)
                continue
            if rgb != current:
                parts.append("\x1b[38;2;%d;%d;%dm" % rgb)
                current = rgb
            parts.append(char)
        if current is not None:
            parts.append(_RESET)
        out.append("".join(parts))
    return out
