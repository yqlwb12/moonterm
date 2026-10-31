"""Command line interface for moonterm."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

from . import __version__, astro
from .render import SIZES, moon_lines

_PANEL_WIDTH = 30

_DIM = (118, 124, 148)
_LABEL = (140, 146, 172)
_VALUE = (214, 218, 234)
_ACCENT = (247, 243, 232)
_ART_WIDTH = 3  # left margin in front of the moon

_RELATIVE = re.compile(r"^([+-])(\d+(?:\.\d+)?)([smhdw])$")
_UNIT_DAYS = {"s": 1 / 86400, "m": 1 / 1440, "h": 1 / 24, "d": 1.0, "w": 7.0}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _paint(text: str, rgb: tuple[int, int, int], enabled: bool) -> str:
    if not enabled:
        return text
    return "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (rgb[0], rgb[1], rgb[2], text)


def _visible(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def parse_when(text: str | None) -> datetime:
    """Turn ``--date`` text into an aware datetime.

    Accepts ``now``, an ISO date or datetime (naive means local time), and
    relative offsets such as ``+3d``, ``-12h`` or ``+90m``.
    """
    if text is None or text.strip() == "" or text.strip().lower() == "now":
        return datetime.now(timezone.utc).astimezone()

    raw = text.strip()
    relative = _RELATIVE.match(raw)
    if relative:
        sign, amount, unit = relative.groups()
        delta = float(amount) * _UNIT_DAYS[unit] * (1 if sign == "+" else -1)
        return (datetime.now(timezone.utc) + timedelta(days=delta)).astimezone()

    cleaned = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(
            "%r is not a date I understand; try 2026-05-01, "
            "2026-05-01T21:30, now, or +3d" % text
        ) from exc
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def _offset(dt: datetime) -> str:
    offset = dt.strftime("%z")
    if offset:
        return "%s:%s" % (offset[:3], offset[3:])
    return "UTC"


def _age(days: float) -> str:
    whole = int(days)
    hours = int(round((days - whole) * 24))
    if hours == 24:
        whole, hours = whole + 1, 0
    return "%dd %2dh" % (whole, hours)


def _relative(when: datetime, now: datetime) -> str:
    seconds = (when - now).total_seconds()
    future = seconds >= 0
    seconds = abs(seconds)
    if seconds < 3600:
        span = "%dm" % max(1, int(round(seconds / 60)))
    elif seconds < 86400:
        span = "%dh" % int(round(seconds / 3600))
    else:
        days = int(seconds // 86400)
        hours = int(round((seconds % 86400) / 3600))
        span = "%dd %dh" % (days, hours) if days < 10 else "%dd" % days
    return ("in " if future else "") + span + ("" if future else " ago")


# --------------------------------------------------------------------------
# the info panel
# --------------------------------------------------------------------------
def panel_lines(phase: astro.MoonPhase, *, color: bool, now: datetime | None = None):
    """Rows of styled segments describing *phase*, plus a plain-text twin.

    Relative times ("in 9d") are measured from the instant being displayed,
    not from the wall clock, so ``moonterm -d 2026-05-01`` still reads
    sensibly.
    """
    now = now or phase.when
    local = phase.when.astimezone()
    stamp = "%s %s" % (local.strftime("%Y-%m-%d %H:%M"), _offset(local))

    pct = "%d%%" % round(phase.percent)
    title = "%-*s%5s" % (_PANEL_WIDTH - 5, phase.name, pct)

    new_moon = phase.next_new_moon()
    full_moon = phase.next_full_moon()
    new_local = new_moon.astimezone()
    full_local = full_moon.astimezone()

    rows = [
        [(title, _ACCENT)],
        [(stamp, _VALUE)],
        [
            ("age ", _DIM),
            (_age(phase.age_days), _VALUE),
            ("   ", None),
            ("{:,} km".format(int(round(phase.distance_km))), _VALUE),
        ],
        [("-" * (_PANEL_WIDTH - 2), _DIM)],
        [
            ("new  ", _LABEL),
            (new_local.strftime("%d %b %H:%M"), _VALUE),
            ("  " + _relative(new_moon, now), _DIM),
        ],
        [
            ("full ", _LABEL),
            (full_local.strftime("%d %b %H:%M"), _VALUE),
            ("  " + _relative(full_moon, now), _DIM),
        ],
    ]

    rendered = []
    for row in rows:
        text = "".join(
            _paint(segment, rgb, color) if rgb else segment for segment, rgb in row
        )
        rendered.append("  " + text)
    return rendered


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------
def compose(art: list[str], panel: list[str], *, gap: int, columns: int) -> list[str]:
    """Place the panel beside the moon when it fits, below it when it does not."""
    art_width = max((len(_visible(line)) for line in art), default=0)
    panel_width = max((len(_visible(line)) for line in panel), default=0)
    art = [" " * _ART_WIDTH + line for line in art]
    art_width += _ART_WIDTH

    if panel and art_width + gap + panel_width <= columns:
        offset = max(0, (len(art) - len(panel)) // 2)
        lines = []
        for index in range(max(len(art), len(panel))):
            left = art[index] if index < len(art) else ""
            panel_index = index - offset
            if 0 <= panel_index < len(panel):
                pad = art_width - len(_visible(left))
                lines.append(left + " " * (pad + gap) + panel[panel_index])
            else:
                lines.append(left)
        return lines

    if not panel:
        return art
    return art + [""] + panel


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moonterm",
        description="Draw tonight's moon in your terminal.",
        epilog=(
            "examples:\n"
            "  moonterm\n"
            "  moonterm --date 2026-05-01 --size large\n"
            "  moonterm -d +3d --south\n"
            "  moonterm --json | jq .illumination\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-d", "--date", metavar="WHEN",
        help="date or offset: 2026-05-01, 2026-05-01T21:30, now, +3d, -12h",
    )
    parser.add_argument(
        "-s", "--size", choices=sorted(SIZES), default="medium",
        help="moon size preset (default: medium)",
    )
    parser.add_argument(
        "-w", "--width", type=int, metavar="COLS",
        help="override the moon width in columns",
    )
    parser.add_argument(
        "--south", action="store_true",
        help="view from the southern hemisphere (moon is mirrored)",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine readable output",
    )
    parser.add_argument(
        "--plain", "--no-color", dest="plain", action="store_true",
        help="never emit ANSI colour",
    )
    parser.add_argument(
        "--color", dest="force_color", action="store_true",
        help="emit colour even when stdout is not a terminal",
    )
    parser.add_argument(
        "--no-earthshine", dest="earthshine", action="store_false",
        help="leave the unlit limb empty",
    )
    parser.add_argument(
        "--no-texture", dest="texture", action="store_false",
        help="smooth moon, no maria",
    )
    parser.add_argument(
        "--art-only", action="store_true", help="print the moon and nothing else",
    )
    parser.add_argument(
        "--watch", nargs="?", type=float, const=2.0, default=None, metavar="SECONDS",
        help="redraw every SECONDS (default 2); ctrl-c to stop",
    )
    parser.add_argument("--version", action="version", version="moonterm " + __version__)
    return parser


def _payload(phase: astro.MoonPhase) -> dict:
    return {
        "utc": phase.when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local": phase.when.astimezone().isoformat(timespec="seconds"),
        "phase_name": phase.name,
        "phase": round(phase.phase, 6),
        "illumination": round(phase.illumination, 6),
        "percent": round(phase.percent, 2),
        "age_days": round(phase.age_days, 3),
        "waxing": phase.waxing,
        "elongation_deg": round(phase.elongation, 4),
        "distance_km": round(phase.distance_km, 1),
        "next_new_moon": phase.next_new_moon().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_full_moon": phase.next_full_moon().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _render(args, when: datetime, *, color: bool, columns: int) -> str:
    phase = astro.moon_phase(when)
    if args.json:
        return json.dumps(_payload(phase), indent=2)

    width = args.width if args.width else SIZES[args.size]
    panel = [] if args.art_only else panel_lines(phase, color=color)
    art = moon_lines(
        phase.phase,
        width,
        south=args.south,
        color=color,
        earthshine=args.earthshine,
        texture=args.texture,
    )
    return "\n".join(compose(art, panel, gap=4, columns=columns))


def _emit(text: str) -> None:
    """Write and flush, so a closed pipe fails here rather than at exit."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _silence_stdout() -> None:
    """Point stdout at the void so the interpreter's final flush cannot fail.

    Without this, ``moonterm | head`` ends with an "Exception ignored ...
    BrokenPipeError" traceback sprayed over the user's terminal.
    """
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except (AttributeError, OSError, ValueError):
        pass


def _watch(args, *, color: bool, columns: int) -> None:
    delay = max(0.2, float(args.watch))
    while True:
        frame = _render(args, parse_when(args.date), color=color, columns=columns)
        # Home the cursor and clear, which avoids flicker on most terminals
        # and keeps the scrollback clean.
        _emit("\x1b[H\x1b[2J" if color else "\x1b[H")
        _emit(frame + "\n")
        time.sleep(delay)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        when = parse_when(args.date)
    except ValueError as exc:
        parser.error(str(exc))

    columns = shutil.get_terminal_size((80, 24)).columns
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    color = args.force_color or (is_tty and not args.plain)

    try:
        if args.watch is not None:
            _watch(args, color=color, columns=columns)
        else:
            _emit(_render(args, when, color=color, columns=columns) + "\n")
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return 0
    except BrokenPipeError:
        # The reader went away (head, less, a closed pty). Nothing is wrong
        # with what we computed, so exit quietly and successfully.
        _silence_stdout()
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
