"""Tests for the command line interface."""

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

from moonterm import cli


def run(*argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = cli.main(list(argv))
    return code, buffer.getvalue()


class DateParsingTest(unittest.TestCase):
    def test_relative_offsets(self):
        now = datetime.now(timezone.utc)
        for text, expected_days in (("+3d", 3), ("-12h", -0.5), ("+1w", 7), ("+90m", 90 / 1440)):
            parsed = cli.parse_when(text)
            delta = (parsed - now).total_seconds() / 86400
            self.assertAlmostEqual(delta, expected_days, delta=0.01, msg=text)

    def test_iso_dates(self):
        self.assertEqual(cli.parse_when("2026-05-01T21:30").strftime("%H:%M"), "21:30")
        self.assertEqual(cli.parse_when("2026-05-01 21:30").strftime("%H:%M"), "21:30")

    def test_zulu_suffix(self):
        parsed = cli.parse_when("2026-05-01T00:00:00Z")
        self.assertEqual(parsed.astimezone(timezone.utc).hour, 0)

    def test_naive_means_local(self):
        parsed = cli.parse_when("2026-05-01T21:30")
        self.assertIsNotNone(parsed.tzinfo)
        self.assertAlmostEqual(parsed.utcoffset(), datetime.now().astimezone().utcoffset())

    def test_now(self):
        parsed = cli.parse_when("now")
        self.assertLess(abs((datetime.now(timezone.utc) - parsed).total_seconds()), 5)

    def test_garbage_is_rejected(self):
        with self.assertRaises(ValueError):
            cli.parse_when("the next full moon please")


class OutputTest(unittest.TestCase):
    def test_plain_output_has_no_ansi(self):
        code, out = run("--plain", "-d", "2026-10-31T12:23")
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertIn("Gibbous", out)

    def test_colour_can_be_forced(self):
        code, out = run("--color", "-d", "2026-10-31T12:23")
        self.assertEqual(code, 0)
        self.assertIn("\x1b[38;2;", out)

    def test_art_only_hides_the_panel(self):
        code, out = run("--plain", "--art-only", "-s", "small", "-d", "2026-05-01")
        self.assertEqual(code, 0)
        self.assertNotIn("age", out)
        self.assertEqual(len(out.strip().splitlines()), 12)

    def test_json_payload(self):
        code, out = run("--json", "-d", "2026-10-31T12:23")
        self.assertEqual(code, 0)
        payload = json.loads(out)

        self.assertEqual(
            sorted(payload),
            sorted([
                "age_days", "distance_km", "elongation_deg", "illumination", "local",
                "next_full_moon", "next_new_moon", "percent", "phase", "phase_name",
                "utc", "waxing",
            ]),
        )
        self.assertGreaterEqual(payload["percent"], 0)
        self.assertLessEqual(payload["percent"], 100)
        self.assertGreater(payload["distance_km"], 356000)
        self.assertLess(payload["distance_km"], 407000)
        self.assertEqual(payload["phase_name"], "Waning Gibbous")
        self.assertFalse(payload["waxing"])

    def test_next_phases_are_sorted(self):
        _, out = run("--json", "-d", "2026-10-31T12:23")
        payload = json.loads(out)
        now = datetime.strptime(payload["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        for key in ("next_new_moon", "next_full_moon"):
            when = datetime.strptime(payload[key], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            self.assertGreater(when, now)
            self.assertLess(when - now, timedelta(days=30))

    def test_narrow_moon_keeps_the_whole_panel(self):
        code, out = run("--plain", "-w", "9", "-d", "2026-10-31T12:23")
        self.assertEqual(code, 0)
        self.assertIn("new", out)
        self.assertIn("full", out)
        self.assertEqual(len(out.strip().splitlines()), 6)

    def test_compose_pads_the_shorter_side(self):
        self.assertEqual(len(cli.compose(["a"] * 3, ["p"] * 6, gap=2, columns=200)), 6)
        self.assertEqual(len(cli.compose(["a"] * 7, ["p"] * 2, gap=2, columns=200)), 7)

    def test_narrow_terminal_stacks_the_panel(self):
        old = cli.shutil.get_terminal_size

        def narrow(fallback=(80, 24)):
            return cli.shutil.os.terminal_size((40, 24))

        cli.shutil.get_terminal_size = narrow
        try:
            code, out = run("--plain", "-d", "2026-10-31T12:23")
        finally:
            cli.shutil.get_terminal_size = old
        self.assertEqual(code, 0)
        lines = out.splitlines()
        moon_rows = len(lines) - 8
        self.assertGreater(moon_rows, 10)
        self.assertTrue(any("Gibbous" in line for line in lines[-6:]))


class ArgparseTest(unittest.TestCase):
    def test_bad_date_exits_two(self):
        with self.assertRaises(SystemExit) as caught:
            run("-d", "not-a-date")
        self.assertEqual(caught.exception.code, 2)

    def test_version_exits_zero(self):
        with self.assertRaises(SystemExit) as caught:
            run("--version")
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
