"""Scene math for the CSS ray tracer.

Every quantity below becomes a registered custom property
(`@property --name { syntax: '<number>' }`), so the browser stores a computed
number per element and later expressions read it back through `var()`.

The math is split in two levels:

  ROW  computed once per scanline (the <b> element): camera basis, eye
       position, sun direction, per-sphere constants, and the part of the
       primary ray that only depends on the row.
  PIX  computed once per pixel (the <i> element): ray direction, sphere and
       floor intersections, normal, soft shadows, ambient occlusion, the
       reflected ray, and the final color.

Inputs read here but set elsewhere (see build.py):
  --yaw --pitch          camera orbit angle and height (radians)
  --sun --elev           sun azimuth and elevation (radians)
  --mr --mg --mb         center sphere albedo
  --tr --tg --tb         center sphere reflection tint
  --mk --ms              center sphere reflectivity and specular strength
  --wb --wn --wd --wl    render pass weights: beauty, normals, depth, lighting
  --soft                 shadow sharpness (higher is harder)
  --u                    horizontal pixel coordinate, set on each pixel

Chromium spends roughly 1 us per registered property plus ~0.2 us per token
when it resolves these, so names are short, shared work is hoisted to the
row, and expressions are kept compact.
"""

# Spheres: center x, y, z and radius. Sphere 0 is the mirror ball.
SPHERES = [
    (0.0, 1.0, 0.0, 1.0),     # center: chrome / gold / clay (from the UI)
    (1.8, 0.55, 1.15, 0.55),  # blue
    (-1.6, 0.62, 0.95, 0.62), # clay white
]
BLUE = (0.05, 0.22, 0.50)
CLAY = (0.84, 0.80, 0.72)
TILE_RED = (0.62, 0.085, 0.055)   # Whitted's checkerboard
TILE_YELLOW = (0.92, 0.74, 0.30)
ZENITH = (0.13, 0.30, 0.64)
HORIZON = (0.78, 0.83, 0.88)
SUN = (1.00, 0.87, 0.68)
AMBIENT = (0.17, 0.21, 0.29)

TARGET_Y = 0.75   # the camera looks at (0, TARGET_Y, 0)
DISTANCE = 4.6    # camera distance from the target
FOCAL = 2.0       # pinhole focal length (vertical half-FOV = atan(1/FOCAL))
FOG = 0.07        # exp() fog density on the floor
FOG_START = 7     # distance where the fog begins
MISS = "1e5"      # distance that means "no hit"


def f(x):
    """Short number literal: 0.55 -> .55, -0.5 -> -.5."""
    s = f"{x:.4g}"
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return s


def _sel(weights, values, scale=1.0):
    """Sum of var(--w_k) * value_k, skipping zero values. Used to pick the
    center or radius of whichever sphere a ray hit."""
    terms = []
    for w, val in zip(weights, values):
        val *= scale
        if abs(val) < 1e-12:
            continue
        if abs(val - 1) < 1e-12:
            terms.append(f"var(--{w})")
        else:
            terms.append(f"{f(val)} * var(--{w})")
    return " + ".join(terms) if terms else "0"


def build():
    ROW, PIX = [], []
    r = lambda n, e: ROW.append((n, e))
    p = lambda n, e: PIX.append((n, e))
    S = SPHERES

    # ------------------------------------------------------------- per row
    # camera basis: forward F = (-sy cp, -sp, -cy cp), right R = (cy, 0, -sy),
    # up U = (-sy sp, cp, -cy sp); eye E = target - F * distance
    r("sy", "sin(var(--yaw))")
    r("cy", "cos(var(--yaw))")
    r("sp", "sin(var(--pitch))")
    r("cp", "cos(var(--pitch))")
    r("fx", "calc(-1 * var(--sy) * var(--cp))")
    r("fz", "calc(-1 * var(--cy) * var(--cp))")
    r("ex", f"calc(var(--sy) * var(--cp) * {f(DISTANCE)})")
    r("ey", f"calc({f(TARGET_Y)} + var(--sp) * {f(DISTANCE)})")
    r("ez", f"calc(var(--cy) * var(--cp) * {f(DISTANCE)})")
    # c_k = |E - center_k|^2 - r^2 (the constant term of the ray/sphere quadratic)
    for k, (cx, cy, cz, rad) in enumerate(S):
        r(f"c{k}", f"calc(pow(var(--ex) - {f(cx)}, 2) + pow(var(--ey) - {f(cy)}, 2) + pow(var(--ez) - {f(cz)}, 2) - {f(rad * rad)})")
    # sun direction L, and center_k . L for the shadow tests
    r("lx", "calc(cos(var(--sun)) * cos(var(--elev)))")
    r("ly", "sin(var(--elev))")
    r("lz", "calc(sin(var(--sun)) * cos(var(--elev)))")
    for k, (cx, cy, cz, rad) in enumerate(S):
        r(f"l{k}", f"calc({f(cx)} * var(--lx) + {f(cy)} * var(--ly) + {f(cz)} * var(--lz))")
    # this scanline: v in [-1, 1]; unnormalized ray q = F * focal + U * v (+ R * u per pixel)
    r("hh", "sibling-count()")
    r("v", "calc((sibling-count() + 1 - 2 * sibling-index()) / sibling-count())")
    r("qx", f"calc(var(--fx) * {f(FOCAL)} - var(--sy) * var(--sp) * var(--v))")
    r("qy", f"calc(var(--sp) * -{f(FOCAL)} + var(--cp) * var(--v))")
    r("qz", f"calc(var(--fz) * {f(FOCAL)} - var(--cy) * var(--sp) * var(--v))")
    # (E - center_k) . ray = B_k + u * G_k, so each pixel only adds one product
    for k, (cx, cy, cz, rad) in enumerate(S):
        r(f"B{k}", f"calc((var(--ex) - {f(cx)}) * var(--qx) + (var(--ey) - {f(cy)}) * var(--qy) + (var(--ez) - {f(cz)}) * var(--qz))")
        r(f"G{k}", f"calc((var(--ex) - {f(cx)}) * var(--cy) - (var(--ez) - {f(cz)}) * var(--sy))")

    # ----------------------------------------------------------- per pixel
    # normalized primary ray d
    p("rx", "calc(var(--qx) + var(--cy) * var(--u))")
    p("rz", "calc(var(--qz) - var(--sy) * var(--u))")
    p("rl", "hypot(var(--rx), var(--qy), var(--rz))")
    p("dx", "calc(var(--rx) / var(--rl))")
    p("dy", "calc(var(--qy) / var(--rl))")
    p("dz", "calc(var(--rz) / var(--rl))")
    # distance to each sphere; a negative discriminant adds MISS via sign()
    for k in range(3):
        p(f"b{k}", f"calc((var(--B{k}) + var(--u) * var(--G{k})) / var(--rl))")
        p(f"e{k}", f"calc(sqrt(max(var(--b{k}) * var(--b{k}) - var(--c{k}), 0)) * -1 - var(--b{k}) + {MISS} * max(0, sign(var(--c{k}) - var(--b{k}) * var(--b{k}))))")
    # floor (y = 0); rays going up land far away and read as sky
    p("ef", "calc(var(--ey) / max(-1 * var(--dy), 1e-4))")
    p("tm", "min(var(--e0), var(--e1), var(--e2), var(--ef))")
    # one-hot masks: 1 for the nearest object, 0 otherwise
    for k in range(3):
        p(f"i{k}", f"calc(1 + sign(var(--tm) - var(--e{k})))")
    p("if", "calc(1 + sign(var(--tm) - var(--ef)))")
    # hit point
    p("hx", "calc(var(--ex) + var(--dx) * var(--tm))")
    p("hy", "calc(var(--ey) + var(--dy) * var(--tm))")
    p("hz", "calc(var(--ez) + var(--dz) * var(--tm))")
    # normal: (hit - center) / radius of the sphere that was hit, (0, 1, 0) on the floor
    masks = ["i0", "i1", "i2"]
    p("rs", "calc(" + _sel(masks, [s[3] for s in S]) + " + var(--if))")
    for a, axis in enumerate("xyz"):
        center = _sel(masks, [s[a] for s in S])
        expr = f"(var(--h{axis}) - ({center})) * (1 - var(--if)) / var(--rs)"
        if axis == "y":
            expr += " + var(--if)"
        p(f"n{axis}", f"calc({expr})")
    # soft shadows: closest approach of the sun ray to each sphere center
    p("pl", "calc(var(--hx) * var(--lx) + var(--hy) * var(--ly) + var(--hz) * var(--lz))")
    for k, (cx, cy, cz, rad) in enumerate(S):
        p(f"a{k}", f"calc(pow(var(--hx) - {f(cx)}, 2) + pow(var(--hy) - {f(cy)}, 2) + pow(var(--hz) - {f(cz)}, 2))")
    for k, (cx, cy, cz, rad) in enumerate(S):
        p(f"s{k}", f"max(clamp(0, (sqrt(max(var(--a{k}) - pow(var(--l{k}) - var(--pl), 2), 0)) - {f(rad)}) / max(var(--l{k}) - var(--pl), 1e-4) * var(--soft), 1), sign(var(--pl) - var(--l{k})))")
    # direct sun light, and analytic ambient occlusion of the floor by each sphere
    p("ls", "calc(1.15 * max(0, var(--nx) * var(--lx) + var(--ny) * var(--ly) + var(--nz) * var(--lz)) * min(var(--s0), var(--s1), var(--s2)))")
    occ = " + ".join(f"{f(cy * rad * rad)} / pow(var(--a{k}), 1.5)" for k, (cx, cy, cz, rad) in enumerate(S))
    p("la", f"calc((.7 + .3 * var(--ny)) * (1 - var(--if) * min(.8, {occ})))")
    # reflected ray m = d - 2 (d . n) n
    p("dn", "calc(var(--dx) * var(--nx) + var(--dy) * var(--ny) + var(--dz) * var(--nz))")
    for axis in "xyz":
        p(f"m{axis}", f"calc(var(--d{axis}) - 2 * var(--dn) * var(--n{axis}))")
    p("ml", "calc(var(--mx) * var(--lx) + var(--my) * var(--ly) + var(--mz) * var(--lz))")
    p("pm", "calc(var(--hx) * var(--mx) + var(--hy) * var(--my) + var(--hz) * var(--mz))")
    # trace m against the spheres (a hit needs a positive discriminant and a sphere in front)
    for k, (cx, cy, cz, rad) in enumerate(S):
        p(f"n{k}", f"calc(var(--pm) - {f(cx)} * var(--mx) - {f(cy)} * var(--my) - {f(cz)} * var(--mz))")
        p(f"g{k}", f"calc(sqrt(max(var(--n{k}) * var(--n{k}) - var(--a{k}) + {f(rad * rad)}, 0)) * -1 - var(--n{k}) + {MISS} * max(0, sign(var(--a{k}) - {f(rad * rad)} - var(--n{k}) * var(--n{k})), sign(var(--n{k}))))")
    # ... and against the floor
    p("gf", f"calc(var(--hy) / max(-1 * var(--my), 1e-4) + {MISS} * max(0, sign(var(--my))))")
    p("rm", "min(var(--g0), var(--g1), var(--g2), var(--gf), 5e4)")
    for k in range(3):
        p(f"j{k}", f"calc(1 + sign(var(--rm) - var(--g{k})))")
    p("jf", "calc(1 + sign(var(--rm) - var(--gf)))")
    p("js", "calc(1 + sign(var(--rm) - 5e4))")
    # diffuse light at the reflected hit, checker at the reflected floor point, its fog
    p("rd", "max(0, (var(--pl) + var(--rm) * var(--ml) - var(--j0) * var(--l0) - var(--j1) * var(--l1) - var(--j2) * var(--l2)) / ("
            + _sel(["j0", "j1", "j2"], [s[3] for s in S]) + " + var(--jf) + var(--js)))")
    # checker: mod() of a negative even number returns 2 in Chromium, so shift into positives first
    p("rk", "mod(round(down, var(--hx) + var(--mx) * var(--rm)) + round(down, var(--hz) + var(--mz) * var(--rm)) + 1e6, 2)")
    p("rf", f"calc(var(--jf) * exp(-{f(FOG)} * max(0, var(--tm) + var(--rm) - {FOG_START})))")
    p("ck", "mod(round(down, var(--hx)) + round(down, var(--hz)) + 1e6, 2)")
    p("fo", f"calc(1 - var(--if) * (1 - exp(-{f(FOG)} * max(0, var(--tm) - {FOG_START}))))")
    # Schlick Fresnel and reflectivity per surface
    p("fr", "pow(1 - abs(var(--dn)), 5)")
    p("kr", "calc(var(--i0) * var(--mk) + var(--if) * (.04 + .4 * var(--fr)) + (var(--i1) + var(--i2)) * (.03 + .3 * var(--fr)))")
    # sky: gradient plus sun disc and glow, for the primary and the reflected ray
    p("sk", "calc(var(--if) * max(0, sign(var(--dy))))")
    p("sc", "sqrt(max(var(--dy), 0))")
    p("du", "max(0, var(--dx) * var(--lx) + var(--dy) * var(--ly) + var(--dz) * var(--lz))")
    p("sn", "calc(6 * pow(var(--du), 900) + .35 * pow(var(--du), 12))")
    p("mm", "max(0, var(--ml))")
    p("sm", "calc(6 * pow(var(--mm), 900) + .35 * pow(var(--mm), 12))")
    p("hl", "calc((var(--i0) + var(--i1) + var(--i2)) * var(--ms) * 1.4 * pow(var(--mm), 60) * min(var(--s0), var(--s1), var(--s2)))")
    p("cm", "sqrt(max(var(--my), 0))")

    # ------------------------------------------------------- color, per channel
    for c, ch in enumerate("rgb"):
        albedo = (f"var(--i0) * var(--m{ch}) + var(--i1) * {f(BLUE[c])} + var(--i2) * {f(CLAY[c])}"
                  f" + var(--if) * ({f(TILE_YELLOW[c])} + {f(TILE_RED[c] - TILE_YELLOW[c])} * var(--ck))")
        reflected = (f"var(--js) * ({f(HORIZON[c])} + {f(ZENITH[c] - HORIZON[c])} * var(--cm) + {f(SUN[c])} * var(--sm))"
                     f" + .3 * var(--j0) * var(--t{ch})"
                     f" + (var(--j1) * {f(BLUE[c])} + var(--j2) * {f(CLAY[c])}) * ({f(AMBIENT[c])} + {f(SUN[c])} * var(--rd))"
                     f" + var(--rf) * ({f(TILE_YELLOW[c])} + {f(TILE_RED[c] - TILE_YELLOW[c])} * var(--rk)) * ({f(AMBIENT[c])} + {f(SUN[c])} * var(--ly))"
                     f" + (var(--jf) - var(--rf)) * {f(HORIZON[c])}")
        p(f"R{ch}", f"calc({reflected})")
        surface = (f"({albedo}) * ({f(AMBIENT[c])} * var(--la) + {f(SUN[c])} * var(--ls)) * (1 - var(--kr))"
                   f" + var(--kr) * var(--R{ch}) * (1 - var(--i0) + var(--i0) * var(--t{ch}))"
                   f" + {f(SUN[c])} * var(--hl)")
        sky = f"{f(HORIZON[c])} + {f(ZENITH[c] - HORIZON[c])} * var(--sc) + {f(SUN[c])} * var(--sn)"
        beauty = (f"(({surface}) * var(--fo) + {f(HORIZON[c])} * (1 - var(--fo))) * (1 - var(--sk))"
                  f" + var(--sk) * ({sky})")
        axis = "xyz"[c]
        p(f"O{ch}", f"calc(var(--wb) * ({beauty}) + (1 - var(--sk)) * (var(--wn) * (.5 + .5 * var(--n{axis}))"
                    f" + var(--wd) * exp(-.16 * var(--tm)) + var(--wl) * (var(--ls) * .8 + .2) * var(--la)))")
    return ROW, PIX


if __name__ == "__main__":
    import re
    rows, pix = build()
    tokens = lambda e: len(re.findall(r"var\(--[a-zA-Z0-9-]+\)|[a-z-]+\(|[0-9.e-]+|[-+*/(),]", e))
    print(f"{len(rows)} row properties, {len(pix)} pixel properties, "
          f"{sum(tokens(e) for _, e in pix)} pixel tokens")
