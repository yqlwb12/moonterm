"""Tests for the ASCII renderer."""

import re
import unittest

from moonterm.render import RAMP, SIZES, moon_lines, shade

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LIT_CHARS = set(RAMP[2:])  # everything brighter than the earthshine dot


def lit_count(lines):
    """How many cells are lit, using the ramp index as a brightness value."""
    total = 0.0
    for line in lines:
        for char in line:
            if char in RAMP:
                total += RAMP.index(char) / (len(RAMP) - 1)
    return total


class GeometryTest(unittest.TestCase):
    def test_row_count_follows_terminal_aspect(self):
        for width in (11, 25, 43, 71):
            lines = moon_lines(0.5, width, color=False)
            self.assertEqual(len(lines), round(width / 2))

    def test_width_is_respected(self):
        for width in (10, 11, 40):
            lines = moon_lines(0.3, width, color=False)
            self.assertLessEqual(max(len(line) for line in lines), width + 1)

    def test_even_widths_are_made_odd(self):
        self.assertEqual(len(moon_lines(0.5, 26, color=False)), len(moon_lines(0.5, 27, color=False)))

    def test_new_moon_is_empty_without_earthshine(self):
        lines = moon_lines(0.0, 31, color=False, earthshine=False)
        self.assertTrue(all(line.strip() == "" for line in lines))

    def test_new_moon_shows_earthshine(self):
        lines = moon_lines(0.0, 31, color=False, earthshine=True)
        self.assertTrue(any("." in line for line in lines))
        self.assertFalse(any(char in LIT_CHARS for line in lines for char in line))

    def test_full_moon_is_bright(self):
        lines = moon_lines(0.5, 41, color=False)
        chars = [char for line in lines for char in line if char.strip()]
        bright = [char for char in chars if char in LIT_CHARS]
        self.assertGreater(len(bright) / len(chars), 0.9)

    def test_brightness_grows_from_new_to_full(self):
        counts = [lit_count(moon_lines(p, 41, color=False)) for p in (0.05, 0.15, 0.25, 0.35, 0.45, 0.5)]
        self.assertEqual(counts, sorted(counts))
        self.assertLess(counts[0], counts[-1])

    def test_quarter_moons_are_mirror_images(self):
        waxing = [line.ljust(31) for line in moon_lines(0.25, 31, color=False, texture=False)]
        waning = [line.ljust(31) for line in moon_lines(0.75, 31, color=False, texture=False)]
        for left, right in zip(waxing, waning):
            self.assertEqual(left, right[::-1])

    def test_southern_hemisphere_mirrors(self):
        north = [line.ljust(31) for line in moon_lines(0.2, 31, color=False)]
        south = [line.ljust(31) for line in moon_lines(0.2, 31, color=False, south=True)]
        for a, b in zip(north, south):
            self.assertEqual(a, b[::-1])

    def test_texture_darkens_the_disc(self):
        flat = lit_count(moon_lines(0.5, 41, color=False, texture=False))
        textured = lit_count(moon_lines(0.5, 41, color=False))
        self.assertLess(textured, flat)
        self.assertGreater(textured, flat * 0.6)

    def test_sizes_are_sane(self):
        self.assertEqual(sorted(SIZES), ["large", "medium", "small"])
        self.assertTrue(all(width % 2 for width in SIZES.values()))


class ColourTest(unittest.TestCase):
    def test_plain_output_is_ascii(self):
        for phase in (0.0, 0.25, 0.5, 0.75):
            for line in moon_lines(phase, 25, color=False):
                line.encode("ascii")  # raises if not pure ASCII

    def test_colour_output_has_ansi_and_same_geometry(self):
        plain = moon_lines(0.3, 25, color=False)
        fancy = moon_lines(0.3, 25, color=True)
        self.assertTrue(any("\x1b[38;2;" in line for line in fancy))
        self.assertEqual(
            [ANSI.sub("", line).rstrip() for line in fancy],
            [line.rstrip() for line in plain],
        )

    def test_no_colour_leaks_without_cells(self):
        empty = moon_lines(0.0, 25, color=True, earthshine=False)
        self.assertFalse(any("\x1b" in line for line in empty))


class ShadeTest(unittest.TestCase):
    def test_cells_carry_colour_or_none(self):
        rows = shade(0.4, 21)
        for row in rows:
            self.assertEqual(len(row), 21)
            for char, rgb in row:
                self.assertEqual(len(char), 1)
                self.assertTrue(rgb is None or len(rgb) == 3)

    def test_earthshine_off_leaves_blanks(self):
        rows = shade(0.0, 21, earthshine=False)
        self.assertTrue(all(char == " " for row in rows for char, _ in row))


if __name__ == "__main__":
    unittest.main()
