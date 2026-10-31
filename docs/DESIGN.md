# Design notes

Two problems, one obvious and one not: *what is the moon doing right now*, and
*how do you draw it with characters*. They have nothing to do with each other,
which is why they live in separate modules.

## 1. Getting the phase right

### The tempting wrong answer

One epoch (say a new moon in 2000) plus the mean synodic month, 29.530588853
days, gives the phase in one line of arithmetic. It is also wrong by up to 14
hours: the Moon's orbit is an ellipse, perturbed mostly by the Sun, and the
interval between consecutive new moons swings between about 29.27 and 29.83
days. Fourteen hours is 7° of phase — a visibly different crescent.

So: compute the two longitudes and subtract.

### The two longitudes

**Sun.** Meeus ch. 25: mean longitude, mean anomaly, an equation of centre with
three periodic terms. Good to 0.01° for the era we care about.

**Moon.** Meeus ch. 47, which is ELP-2000/82 truncated to the fifty largest
periodic terms. Each term is a small correction with an argument built from five
fundamental angles — mean elongation `D`, the Sun's mean anomaly `M`, the Moon's
mean anomaly `M'`, the argument of latitude `F`, and the mean longitude `L'`:

    Σl = Σ k_i · sin(c1·D + c2·M + c3·M' + c4·F)

The first term, `6288774 · sin(M')` in units of 10⁻⁶ degrees, is about 6.3° on
its own — that is the equation of centre, and skipping it is how you get a moon
that is a day off. The rest are perturbations down to fractions of an arcsecond.
The fifty rows cover everything above roughly 1.7″, which leaves the longitude
within 0.01° of the full theory at about 50 µs per call.

The distance series is the same shape, with cosines instead of sines, and lands
within 20 km of the full theory — irrelevant for drawing, but it lets
`moonterm` tell you whether tonight's full moon is a perigean one.

### Why nutation never appears

Both longitudes are *mean* longitudes. The physical nutation Δψ is the same for
the Sun and the Moon as seen from Earth, so

    ψ = λ_moon − λ_sun

loses it in the subtraction. Aberration (about 20″ on the Sun) is left in, which
costs 0.02° — under a minute of phase angle. This is the sort of thing worth
being explicit about, because "why is nutation missing" is the first question a
reader will have.

### From elongation to illumination

With ψ the geocentric elongation, the phase angle `i` between Sun and Earth as
seen from the Moon satisfies `i = 180° − ψ`, and the illuminated fraction of a
Lambertian sphere is

    k = (1 + cos i) / 2 = (1 − cos ψ) / 2

which is nice because it needs neither the Moon's distance nor any trigonometry
beyond one cosine. ψ = 0 gives k = 0 (new), ψ = 180 gives k = 1 (full).

The phase *index* used for drawing is just ψ/360 measured eastward, i.e. the
fraction of the synodic month since the last new moon. It is also the moon's age
in units of a month, which is why `age_days = phase × 29.530588853`.

### Finding the next new or full moon

`elongation(t) − target` is monotonic-ish and crosses zero at the event, moving
at about 12.2° per day, so its sign changes once per ~29.5 days. Scan forward in
quarter-day steps looking for a sign change, then bisect 80 times (the bracket is
under half a day, so this converges to microseconds). The one trap: the residual
is wrapped into (−180, 180], so a step that jumps over the wrap without crossing
the target also shows a sign change. Guard: reject brackets whose residual jumps
by more than 90°, which is a wrap, not a root.

## 2. Drawing it

### Fitting a disc into a character grid

Terminal cells are about twice as tall as they are wide, so a grid of *w*
columns needs about *w/2* rows for the disc to look round. Everything below works
in normalised coordinates `u, v ∈ [−1, 1]`, where `u` is the column axis and `v`
the row axis, and the disc is `u² + v² ≤ 1`.

### The terminator is an ellipse

Consider the Moon as a sphere lit from the side, seen from Earth. Project the
boundary between lit and unlit onto the plane of the sky. The great circle that
separates day from night projects to an ellipse whose semi-major axis is the full
radius and whose semi-minor axis is `R·|cos i|`, where `i` is the phase angle. At
half moon `i = 90°` and the "ellipse" collapses to a straight line through the
centre — which is exactly the flat edge everyone draws. At full moon `cos i = −1`
and the ellipse coincides with the limb.

At height `v` the boundary is therefore at

    u_edge = cos(2π·phase) · √(1 − v²)

because `i = 180° − ψ` and ψ = 360°·phase, so `cos i = cos(180° − ψ) = −cos ψ =
cos(2π·phase)`. One line, no special cases:

- waxing (`phase < 0.5`): lit when `u > u_edge`;
- waning: lit when `u < −u_edge`.

Checked against the extremes: phase 0 gives `u > √(1−v²)`, i.e. only the limb,
i.e. nothing; phase 0.5 gives `u < √(1−v²)`, i.e. everything. Half moon gives
`u > 0` on the right, which is what a waxing moon looks like from the northern
hemisphere. The southern hemisphere sees it upside down, so `--south` flips `u`
before the test.

### Anti-aliasing for free

Each cell is tested with a 4×4 grid of sub-pixels and the fraction that are lit
becomes the cell's brightness. That fraction indexes a 10-character ramp
(`" .:-=+*#%@"`), so a terminator crossing a cell gets an intermediate character
instead of a jagged edge. It costs 16 tests per cell — 14 000 per frame at 43
columns, which is a rounding error on any machine from the last thirty years.

Supersampling is what separates "an ASCII moon" from "a blob with a bite taken
out of it". The same coverage value drives the colour, interpolated from a slate
blue — barely lit — to warm white, so the limb fades instead of stepping.

### The maria

A full moon rendered as a solid `@` is technically correct and visually useless.
The near side of the Moon always faces Earth, so its dark patches — the maria —
sit at fixed positions on the disc and can simply be placed by hand:

    Mare Crisium     ( 0.60,  0.44)
    Mare Imbrium     (−0.06,  0.53)
    Oceanus Procellarum (−0.42, 0.12)
    ...

(`x` right, `y` up, in disc radii; the table in `render.py` has ten of them.)
Each cell's brightness is multiplied by the summed cosine falloff of these blobs,
which drops it a few ramp steps and gives the moon a face. It also makes the
drawing asymmetric in the right way: the maria do not mirror when the phase does,
because the Moon does not.

### Earthshine

The unlit limb is drawn with a dim `.` rather than a space. A new moon then looks
like a faint disc instead of an empty rectangle, and a crescent keeps its shape:
the eye reads the terminator correctly only if it can see what the terminator
bounds.

## 3. What is ignored, and why that is fine

| Effect | Size | Consequence |
| --- | --- | --- |
| Topocentric parallax | up to 1° in position | sub-pixel at 43 columns |
| Libration | ±8° | shifts maria by a cell or two; we place the mean near side |
| Aberration | 0.02° in elongation | under a minute of phase |
| ΔT (TT − UT) | ~70 s | 0.001 in illumination |
| Light-time | 1.3 s | nothing |

The tests hold the code to what it claims: Meeus' example 47.a to 0.02°, published
new and full moons to ten minutes (it currently lands within three), and the
renderer's mirror symmetries to exact equality.

## References

- Jean Meeus, *Astronomical Algorithms*, 2nd ed., chapters 7, 25, 47, 49.
- E. W. Weisstein, "Moon Phase", MathWorld — for the ellipse formulation.
