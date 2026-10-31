# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0 - 2026-10-31

### Added

- `moonterm` console command: draws the moon for any instant, with a size
  preset, southern-hemisphere orientation, earthshine, and the near-side maria.
- Lunar and solar ephemerides from the truncated ELP-2000/82 and Meeus solar
  series; elongation, illuminated fraction, moon age, and distance.
- `next_new_moon()` / `next_full_moon()` by bracketing and bisection.
- `--json` payload, `--watch` live redraw, `--art-only`, `--plain`.
- Test suite (48 tests) validating the ephemeris against Meeus' worked examples
  and published phase times, and the renderer's geometry.
- CI across Python 3.9–3.13 on Linux, macOS and Windows.
