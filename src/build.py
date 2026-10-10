"""Build index.html for the CSS ray tracer.

    python3 src/build.py            # writes ./index.html next to src/

The output is a single static HTML file with no JavaScript. All of the
ray tracing happens in the stylesheet that this script generates from the
scene math in scene.py. Only the Python standard library is needed.
"""
from pathlib import Path

from scene import SPHERES, build

ROW, PIX = build()
ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/marco-jardim/css-raytracer"
SITE_URL = "https://marco-jardim.github.io/css-raytracer/"

# ------------------------------------------------------------------ settings
# Defaults for the scene inputs. Each one is set on every scanline and
# overridden by the :has() rules generated from the presets below.
INPUTS = {
    "yaw": 0.3, "pitch": 0.3, "sun": 2.5, "elev": 0.26,
    "mk": 0.85, "ms": 1, "mr": 0.03, "mg": 0.03, "mb": 0.035,
    "tr": 0.95, "tg": 0.95, "tb": 0.97,
    "wb": 1, "wn": 0, "wd": 0, "wl": 0,
}
CAMERAS = [  # id, yaw (radians), label
    ("c0", 0.30, "Front"),
    ("c1", 1.25, "Right"),
    ("c2", 2.35, "Back right"),
    ("c3", 3.45, "Back"),
    ("c4", -1.95, "Back left"),
    ("c5", -0.85, "Left"),
]
HEIGHTS = [("p0", 0.10, "Grazing"), ("p1", 0.30, "Eye level"), ("p2", 0.62, "High")]
SUNS = [  # id, azimuth, elevation (radians), label
    ("s0", 2.5, 0.26, "Late afternoon"),
    ("s1", 0.9, 0.55, "Afternoon"),
    ("s2", 1.4, 1.15, "Noon"),
    ("s3", -1.6, 0.32, "Backlight"),
]
MATERIALS = [  # id, label, values for the center sphere
    ("m0", "Chrome", dict(mr=.03, mg=.03, mb=.035, tr=.95, tg=.95, tb=.97, mk=.85, ms=1)),
    ("m1", "Gold", dict(mr=.12, mg=.07, mb=.01, tr=1, tg=.74, tb=.32, mk=.82, ms=1)),
    ("m2", "Clay", dict(mr=.74, mg=.43, mb=.32, tr=1, tg=1, tb=1, mk=.04, ms=.25)),
]
PASSES = [
    ("v0", "Beauty", dict(wb=1, wn=0, wd=0, wl=0)),
    ("v1", "Normals", dict(wb=0, wn=1, wd=0, wl=0)),
    ("v2", "Depth", dict(wb=0, wn=0, wd=1, wl=0)),
    ("v3", "Lighting", dict(wb=0, wn=0, wd=0, wl=1)),
]
RESOLUTIONS = [(64, 36), (96, 54), (128, 72), (160, 90), (192, 108), (256, 144), (320, 180)]
DEFAULT_RES = 96

# Time budget per pixel for the scanline scheduler. A row of W pixels gets
# W * MS_PER_PX before the next row is revealed. Measured cost on a 2.8 GHz
# Xeon was ~0.7 ms per pixel; if the budget is smaller than the real cost,
# rows pile up and arrive in bursts. "Fast scan" halves it.
MS_PER_PX = 0.72


def num(x):
    return f"{x:.4g}"


def fmt(n):
    return f"{n:,}"


def step_ms(w, fast=False):
    return round(w * MS_PER_PX / (2 if fast else 1))


def eta_s(w, h, fast=False):
    return (step_ms(w, fast) * h + 120) / 1000


# --------------------------------------------------------------- engine CSS
def engine_css():
    o = []
    for n, d in INPUTS.items():
        o.append(f"@property --{n}{{syntax:'<number>';inherits:true;initial-value:{num(d)}}}")
    o.append(f"@property --sun0{{syntax:'<number>';inherits:true;initial-value:{num(INPUTS['sun'])}}}")
    o.append("@property --soft{syntax:'<number>';inherits:true;initial-value:7}")
    o.append("@property --step{syntax:'<time>';inherits:false;initial-value:69ms}")
    for n, _ in ROW:
        o.append(f"@property --{n}{{syntax:'<number>';inherits:true;initial-value:0}}")
    o.append("@property --u{syntax:'<number>';inherits:false;initial-value:0}")
    for n, _ in PIX:
        o.append(f"@property --{n}{{syntax:'<number>';inherits:false;initial-value:0}}")

    # The scanline scheduler. Every control group owns one entry in each row's
    # animation list. Each entry is a 1 ms animation that holds display:none
    # during its delay (fill-mode: backwards), and the delay grows with the row
    # index. Choosing an option swaps that entry's name, which restarts it, so
    # every row drops to display:none and comes back one scanline at a time.
    # Rows that are display:none cost nothing: their pixels are not styled.
    groups = ["cam", "hgt", "sun", "mat", "pas", "lap", "spd"]
    defaults = {"cam": "c0", "hgt": "p1", "sun": "s0", "mat": "m0", "pas": "v0", "lap": "0", "spd": "0"}
    names = ([f"rv-cam-{c}" for c, _, _ in CAMERAS] + [f"rv-hgt-{h}" for h, _, _ in HEIGHTS]
             + [f"rv-sun-{s}" for s, _, _, _ in SUNS] + [f"rv-mat-{m}" for m, _, _ in MATERIALS]
             + [f"rv-pas-{v}" for v, _, _ in PASSES] + ["rv-lap-0", "rv-lap-1", "rv-spd-0", "rv-spd-1"])
    o.append("".join(f"@keyframes {n}{{from,to{{display:none}}}}" for n in names))
    # moving sun: each row steps the sun 15 degrees once per sweep, staggered top to bottom
    o.append("@keyframes lapse{from{--sun:var(--sun0)}to{--sun:calc(var(--sun0) + 6.28318)}}")

    n = len(groups)
    delay = "calc(sibling-index() * var(--step) + 120ms)"
    row = [f"--{k}:{num(v)}" for k, v in INPUTS.items() if k != "sun"]
    row += [f"--sun0:{num(INPUTS['sun'])}", "--sun:var(--sun0)", "--lp:none"]
    row += [f"--a-{g}:rv-{g}-{defaults[g]}" for g in groups]
    row += [f"--{k}:{e}" for k, e in ROW]
    o.append(
        ".fb>b{display:flex;position:absolute;left:0;right:0;"
        "top:calc((sibling-index() - 1) / sibling-count() * 100%);height:calc(100% / sibling-count() + 1px);"
        "counter-increment:rows;"
        "animation-name:" + ",".join(f"var(--a-{g})" for g in groups) + ",var(--lp);"
        "animation-duration:" + ",".join(["1ms"] * n) + ",calc(24 * sibling-count() * var(--step));"
        "animation-timing-function:" + ",".join(["step-end"] * n) + ",steps(24,end);"
        "animation-fill-mode:" + ",".join(["backwards"] * n) + ",none;"
        "animation-iteration-count:" + ",".join(["1"] * n) + ",infinite;"
        "animation-delay:" + ",".join([delay] * n) + ",calc(sibling-index() * var(--step));"
        + ";".join(row) + "}"
    )
    pix = ["--u:calc((2 * sibling-index() - 1 - sibling-count()) / var(--hh))"]
    pix += [f"--{k}:{e}" for k, e in PIX]
    color = ("background-color:rgb(calc(255 * pow(clamp(0, var(--Or), 1), .4545)) "
             "calc(255 * pow(clamp(0, var(--Og), 1), .4545)) "
             "calc(255 * pow(clamp(0, var(--Ob), 1), .4545)))")
    o.append(".fb>b>i{flex:1 0 0;margin-right:-.5px;counter-increment:px;" + ";".join(pix) + ";" + color + "}")

    # Controls. :has() on the app writes the inputs on the rows only. Nothing
    # here may set an inherited property on an ancestor of the pixels, or every
    # pixel would be restyled at once instead of one scanline at a time.
    R = ".fb>b"
    for cid, yaw, _ in CAMERAS:
        o.append(f".app:has(#{cid}:checked) {R}{{--yaw:{num(yaw)};--a-cam:rv-cam-{cid}}}")
    for hid, pitch, _ in HEIGHTS:
        o.append(f".app:has(#{hid}:checked) {R}{{--pitch:{num(pitch)};--a-hgt:rv-hgt-{hid}}}")
    for sid, az, el, _ in SUNS:
        o.append(f".app:has(#{sid}:checked) {R}{{--sun0:{num(az)};--elev:{num(el)};--a-sun:rv-sun-{sid}}}")
    for mid, _, vals in MATERIALS:
        o.append(f".app:has(#{mid}:checked) {R}{{" + ";".join(f"--{k}:{num(v)}" for k, v in vals.items()) + f";--a-mat:rv-mat-{mid}}}")
    for vid, _, vals in PASSES:
        o.append(f".app:has(#{vid}:checked) {R}{{" + ";".join(f"--{k}:{num(v)}" for k, v in vals.items()) + f";--a-pas:rv-pas-{vid}}}")
    o.append(f".app:has(#lapse:checked) {R}{{--lp:lapse;--a-lap:rv-lap-1}}")
    o.append(f".app:has(#fast:checked) {R}{{--a-spd:rv-spd-1}}")
    for w, h in RESOLUTIONS:
        o.append(f".fb-{w}>b{{--step:{step_ms(w)}ms}}")
        o.append(f".app:has(#fast:checked) .fb-{w}>b{{--step:{step_ms(w, True)}ms}}")
    return "\n".join(o)


def resolution_css():
    """Per-resolution rules: which framebuffer shows, grid overlay, blur, stats."""
    o = []
    for w, h in RESOLUTIONS:
        sel = f".app:has(#r{w}:checked)"
        o.append(f"{sel} .fb-{w}{{display:block}}")
        o.append(f"{sel} .frame::after{{background-size:calc(100% / {w}) 100%,100% calc(100% / {h})}}")
        o.append(f"{sel}:has(#smooth:checked) .fb-{w}{{filter:blur(max(.6px,{19 / w:.3f}vw))}}")
        o.append(f'{sel} .stat-px::after{{content:counter(px) " / {w * h}"}}')
        o.append(f'{sel} .stat-rows::after{{content:counter(rows) " / {h}"}}')
        o.append(f'{sel} .stat-eta::after{{content:"{step_ms(w)} ms per scanline, ≈ {eta_s(w, h):.1f} s per frame"}}')
        o.append(f'{sel}:has(#fast:checked) .stat-eta::after{{content:"{step_ms(w, True)} ms per scanline, ≈ {eta_s(w, h, True):.1f} s per frame"}}')
    return "\n".join(o)


# --------------------------------------------------------------------- HTML
def framebuffers():
    parts = []
    for w, h in RESOLUTIONS:
        row = "<b>" + "<i></i>" * w + "</b>"
        parts.append(f'<div class="fb fb-{w}" aria-hidden="true">' + row * h + "</div>")
    return "\n".join(parts)


def radio(name, rid, label, checked=False):
    c = " checked" if checked else ""
    return (f'<label class="seg"><input type="radio" name="{name}" id="{rid}"{c}>'
            f'<span>{label}</span></label>')


def plan_map():
    """Top-down plan of the scene: spheres to scale, camera stations on a ring."""
    balls = [(x, z, r, cls) for (x, _, z, r), cls in zip(SPHERES, ["s-mirror", "s-blue", "s-clay"])]
    out = ['<div class="map" role="radiogroup" aria-label="Camera position">',
           '<span class="ring"></span><span class="ray"></span><span class="sunmark" aria-hidden="true"></span>']
    for x, z, r, cls in balls:
        out.append(f'<span class="ball {cls}" style="--x:{num(x)};--z:{num(z)};--r:{num(r)}"></span>')
    for i, (cid, yaw, label) in enumerate(CAMERAS):
        ch = " checked" if i == 0 else ""
        out.append(f'<label class="cam" style="--a:{num(yaw)}" title="{label}"><input type="radio" name="cam" id="{cid}"{ch}>'
                   f'<span class="sr">{label}</span></label>')
    out.append("</div>")
    return "".join(out)


PAGE_CSS = r"""
/* Render-window studio: a dark graphite workbench around one framebuffer, the
   controls to its right; accent colors come from Whitted's red and yellow checkerboard. */
:root{
  --bg:#121318; --panel:#191b21; --raise:#20232b; --line:#2b2f39;
  --ink:#ece6da; --muted:#959aa6; --amber:#e9b64b; --brick:#c4472c; --void:#0b0c0f;
  --display:"Young Serif",Georgia,"Times New Roman",serif;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace;
  color-scheme:dark;
}
@property --sel{syntax:'<number>';inherits:true;initial-value:.3}
@property --sa{syntax:'<number>';inherits:true;initial-value:2.5}
@property --se{syntax:'<number>';inherits:true;initial-value:.26}
html,body{background:var(--bg)}
body{margin:0;color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--amber);text-underline-offset:3px}
.app{max-width:1240px;margin:0 auto;padding-inline:clamp(16px,4vw,40px);padding-block:clamp(20px,4vw,44px) 64px;counter-reset:px rows}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
header{display:grid;gap:10px;margin-bottom:clamp(18px,3vw,30px);max-width:62ch}
.eyebrow{font:500 11.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--amber)}
h1{font:400 clamp(34px,5.4vw,58px)/1.02 var(--display);letter-spacing:-.01em;margin:0;text-wrap:balance}
.lede{color:var(--muted);margin:0;font-size:16px}
code{font-family:var(--mono);font-size:.88em;color:var(--ink)}

.studio{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:clamp(16px,2.4vw,28px);align-items:start}
@media (max-width:900px){.studio{grid-template-columns:minmax(0,1fr)}}
.left{min-width:0;display:grid;gap:clamp(16px,2.4vw,28px)}
.window{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.titlebar{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;justify-content:space-between;padding:9px 14px;border-bottom:1px solid var(--line);font:500 11.5px/1.3 var(--mono);color:var(--muted);letter-spacing:.04em}
.titlebar b{color:var(--ink);font-weight:500}
.tiles{display:inline-grid;grid-template-columns:repeat(4,6px);grid-template-rows:repeat(2,6px);vertical-align:-2px;margin-right:8px}
.tiles i{background:var(--brick)}.tiles i:nth-child(4n+2),.tiles i:nth-child(4n+4){background:var(--amber)}
.tiles i:nth-child(n+5){background:var(--amber)}.tiles i:nth-child(6),.tiles i:nth-child(8){background:var(--brick)}
.stage{padding:clamp(10px,2vw,18px);background:var(--void);overflow:hidden}
.frame{position:relative;aspect-ratio:16/9;background:repeating-linear-gradient(to bottom,#14161b 0 1px,var(--void) 1px 4px)}
.fb{position:absolute;inset:0;display:none;overflow:hidden}
.frame::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .25s;
  background-image:linear-gradient(90deg,rgb(11 12 15/.85) 1px,transparent 1px),linear-gradient(rgb(11 12 15/.85) 1px,transparent 1px)}
.app:has(#grid:checked) .frame::after{opacity:1}
.stats{display:flex;flex-wrap:wrap;gap:4px 22px;padding:10px 14px;border-top:1px solid var(--line);font:400 12px/1.4 var(--mono);color:var(--muted);font-variant-numeric:tabular-nums}
.stats span::after{color:var(--ink)}
.stat-px::before{content:"pixels traced "}
.stat-rows::before{content:"scanlines drawn "}
.stat-eta{flex-basis:100%}

.panel{display:grid;gap:18px;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:16px}
.group{display:grid;gap:8px;border:0;margin:0;padding:0;min-width:0}
.group legend{font:500 11px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);padding:0;margin-bottom:8px}
.segs{display:flex;flex-wrap:wrap;gap:4px}
.seg{position:relative;cursor:pointer}
.seg input,.cam input,.tog input{position:absolute;opacity:0;width:1px;height:1px;margin:0}
.seg span{display:block;padding:6px 10px;border:1px solid var(--line);border-radius:4px;font:500 12.5px/1.2 var(--sans);color:var(--muted);background:var(--raise);transition:color .15s,border-color .15s,background .15s}
.seg:hover span{color:var(--ink);border-color:#3a3f4b}
.seg:has(input:checked) span{color:#17140c;background:var(--amber);border-color:var(--amber)}
.seg:has(input:focus-visible) span,.tog:has(input:focus-visible) .sw,.cam:has(input:focus-visible){outline:2px solid var(--ink);outline-offset:2px}
.res span{font-family:var(--mono);font-size:12px}
.hint{margin:0;font-size:12px;line-height:1.4;color:var(--muted)}

.map{position:relative;aspect-ratio:1;max-width:220px;width:100%;margin:2px auto 4px;
  background:repeating-conic-gradient(#1e2027 0 25%,#191b21 0 50%) 50% 50%/27% 27%;border-radius:50%;
  --k:13.5%;transition:--sel .4s,--sa .5s,--se .5s}
.map .ring{position:absolute;inset:6%;border:1px dashed #3a3f4b;border-radius:50%}
.ball{position:absolute;left:calc(50% + var(--x) * var(--k));top:calc(50% + var(--z) * var(--k));width:calc(var(--r) * 2 * var(--k));aspect-ratio:1;translate:-50% -50%;border-radius:50%}
.s-mirror{background:radial-gradient(circle at 35% 35%,#f2f3f5,#7b8190 60%,#3b3f49)}
.s-blue{background:radial-gradient(circle at 35% 35%,#6a9ad6,#1f4a8c 70%)}
.s-clay{background:radial-gradient(circle at 35% 35%,#f3ece0,#a99f8f 75%)}
.cam{position:absolute;left:calc(50% + sin(var(--a)) * 44%);top:calc(50% + cos(var(--a)) * 44%);width:18px;height:18px;translate:-50% -50%;border-radius:50%;cursor:pointer;
  background:var(--raise);border:1.5px solid #59606e;transition:background .15s,border-color .15s,scale .15s}
.cam:hover{border-color:var(--ink)}
.cam:has(input:checked){background:var(--amber);border-color:var(--amber);scale:1.15}
.map .ray{position:absolute;left:50%;top:50%;width:44%;height:0;border-top:1.5px solid rgb(233 182 75/.55);transform-origin:0 0;rotate:calc(90deg - var(--sel) * 1rad)}
.sunmark{position:absolute;left:calc(50% + cos(var(--sa)) * 50% * cos(var(--se)));top:calc(50% + sin(var(--sa)) * 50% * cos(var(--se)));width:12px;aspect-ratio:1;translate:-50% -50%;border-radius:50%;
  background:radial-gradient(#fff3d6 30%,#f0b54a 60%,transparent 70%);box-shadow:0 0 12px 3px rgb(240 181 74/.45)}
.toggles{gap:10px}
.tog{display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-size:13.5px;color:var(--ink)}
.tog .sw{flex:none;width:30px;height:17px;margin-top:2px;border-radius:9px;background:var(--raise);border:1px solid var(--line);position:relative;transition:background .15s}
.tog .sw::after{content:"";position:absolute;top:2px;left:2px;width:11px;height:11px;border-radius:50%;background:var(--muted);transition:translate .15s,background .15s}
.tog:has(input:checked) .sw{background:var(--amber);border-color:var(--amber)}
.tog:has(input:checked) .sw::after{translate:13px 0;background:#17140c}
.tog small{display:block;color:var(--muted);font-size:12px;line-height:1.35}
.note{margin:0;font-size:12.5px;line-height:1.5;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}

.nosupport{display:none;margin:0 0 18px;padding:12px 14px;border:1px solid var(--brick);border-radius:6px;color:var(--ink);background:rgb(196 71 44/.12);max-width:70ch}
@supports not (order: sibling-index()){.nosupport{display:block}}

.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.facts div{background:var(--panel);padding:14px 16px;display:grid;gap:2px;align-content:start}
.facts strong{font:400 26px/1.1 var(--display);color:var(--ink);font-variant-numeric:tabular-nums}
.facts span{font-size:12.5px;color:var(--muted)}

.how{margin-top:clamp(40px,6vw,72px);display:grid;gap:22px}
.how h2{font:400 clamp(26px,3.4vw,36px)/1.1 var(--display);margin:0;text-wrap:balance}
.how>p{margin:0;color:var(--muted);max-width:68ch}
.steps{list-style:none;margin:8px 0 0;padding:0;display:grid;counter-reset:step}
.steps li{counter-increment:step;display:grid;grid-template-columns:3.2em minmax(0,1fr);gap:4px 16px;padding:20px 0;border-top:1px solid var(--line)}
.steps li::before{content:counter(step,decimal-leading-zero);font:500 13px/1.6 var(--mono);color:var(--amber);grid-row:span 3}
.steps h3{margin:0;font:600 16px/1.4 var(--sans)}
.steps p{margin:0;color:var(--muted);max-width:68ch}
pre{margin:6px 0 0;padding:12px 14px;background:var(--panel);border:1px solid var(--line);border-radius:5px;overflow-x:auto;font:400 12.5px/1.6 var(--mono);color:#d8d2c4;max-width:100%}
pre .k{color:var(--amber)}
footer{margin-top:40px;display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 24px;font:400 12px/1.5 var(--mono);color:var(--muted)}
@media (prefers-reduced-motion:reduce){.map,.cam,.seg span,.frame::after,.tog .sw,.tog .sw::after{transition:none}}
"""


def map_css():
    o = [f".app:has(#{cid}:checked) .map{{--sel:{num(yaw)}}}" for cid, yaw, _ in CAMERAS]
    o += [f".app:has(#{sid}:checked) .map{{--sa:{num(az)};--se:{num(el)}}}" for sid, az, el, _ in SUNS]
    return "\n".join(o)


FAVICON = ("data:image/svg+xml,"
           "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Cdefs%3E%3CradialGradient id='g' cx='.35' cy='.35' r='.7'%3E%3Cstop offset='0' stop-color='%23f2f3f5'/%3E"
           "%3Cstop offset='.6' stop-color='%237b8190'/%3E%3Cstop offset='1' stop-color='%233b3f49'/%3E%3C/radialGradient%3E%3C/defs%3E"
           "%3Crect width='32' height='32' rx='6' fill='%23121318'/%3E"
           "%3Cpath fill='%23c4472c' d='M2 22h7v8H2zM16 22h7v8h-7z'/%3E%3Cpath fill='%23e9b64b' d='M9 22h7v8H9zM23 22h7v8h-7z'/%3E"
           "%3Ccircle cx='16' cy='14' r='9' fill='url(%23g)'/%3E%3C/svg%3E")


def page():
    props = len(PIX) + 1
    row_props = len(ROW) + len(INPUTS) + 2
    top_w, top_h = RESOLUTIONS[-1]
    title = "CSS Ray Tracer"
    desc = ("A ray tracer written in pure CSS: every pixel is an element whose color comes out of "
            "@property, sqrt(), pow(), exp() and sibling-index(). No JavaScript, no WebGL.")

    controls = f"""
    <div class="panel" role="group" aria-label="Render settings">
      <fieldset class="group">
        <legend>Camera</legend>
        {plan_map()}
        <div class="segs" role="radiogroup" aria-label="Camera height">{"".join(radio("height", hid, label, hid == "p1") for hid, _, label in HEIGHTS)}</div>
      </fieldset>
      <fieldset class="group">
        <legend>Sun</legend>
        <div class="segs">{"".join(radio("sun", sid, label, sid == "s0") for sid, _, _, label in SUNS)}</div>
      </fieldset>
      <fieldset class="group">
        <legend>Center sphere</legend>
        <div class="segs">{"".join(radio("mat", mid, label, mid == "m0") for mid, label, _ in MATERIALS)}</div>
      </fieldset>
      <fieldset class="group">
        <legend>Render pass</legend>
        <div class="segs">{"".join(radio("pass", vid, label, vid == "v0") for vid, label, _ in PASSES)}</div>
      </fieldset>
      <fieldset class="group">
        <legend>Resolution</legend>
        <div class="segs res">{"".join(radio("res", f"r{w}", f"{w}×{h}", w == DEFAULT_RES) for w, h in RESOLUTIONS)}</div>
        <p class="hint">Higher presets take longer. {top_w}×{top_h} is {fmt(top_w * top_h)} elements and about {eta_s(top_w, top_h):.0f} s per frame.</p>
      </fieldset>
      <fieldset class="group toggles">
        <legend>Display</legend>
        <label class="tog"><input type="checkbox" id="smooth"><span class="sw"></span><span>Smooth<small>Blurs the framebuffer like a CRT.</small></span></label>
        <label class="tog"><input type="checkbox" id="grid"><span class="sw"></span><span>Show grid<small>Each cell is one &lt;i&gt; element.</small></span></label>
        <label class="tog"><input type="checkbox" id="fast"><span class="sw"></span><span>Fast scan<small>Halves the time budget per scanline. On slower machines rows arrive in bursts.</small></span></label>
        <label class="tog"><input type="checkbox" id="lapse"><span class="sw"></span><span>Moving sun<small>Advances the sun 15° per sweep. Keeps one CPU core busy.</small></span></label>
      </fieldset>
      <p class="note">Every change clears the image and redraws it one scanline at a time, top to bottom, like a 1980 renderer.</p>
    </div>"""

    how = f"""
  <section class="how" aria-labelledby="how-h">
    <h2 id="how-h">What the browser is computing</h2>
    <p>There is no script on this page. Each pixel is an <code>&lt;i&gt;</code> element with {props} properties registered through <code>@property</code>. The style engine resolves them as a chain of numeric expressions, and the last one becomes the element's <code>background-color</code>.</p>
    <ol class="steps">
      <li><h3>Pixel coordinates</h3>
        <p><code>sibling-index()</code> and <code>sibling-count()</code> tell each element where it sits in its row and how many rows there are. That gives the direction of the ray leaving the camera.</p>
<pre><span class="k">--u</span>: calc((2 * sibling-index() - 1 - sibling-count()) / var(--hh));
<span class="k">--rl</span>: hypot(var(--rx), var(--qy), var(--rz));</pre></li>
      <li><h3>Sphere intersections</h3>
        <p>The ray against each sphere is a quadratic with a discriminant. When the discriminant is negative, <code>sign()</code> adds 100,000 to the distance and that sphere loses the <code>min()</code> that follows. That is how the stylesheet branches without <code>if</code>.</p>
<pre><span class="k">--e0</span>: calc(sqrt(max(var(--b0) * var(--b0) - var(--c0), 0)) * -1 - var(--b0)
      + 1e5 * max(0, sign(var(--c0) - var(--b0) * var(--b0))));
<span class="k">--tm</span>: min(var(--e0), var(--e1), var(--e2), var(--ef));</pre></li>
      <li><h3>Soft shadows and occlusion</h3>
        <p>For each sphere, the closest approach between the sun ray and the sphere center gives a penumbra that widens with distance. Floor occlusion uses the analytic solid-angle formula, with <code>pow(d², 1.5)</code>.</p>
<pre><span class="k">--s1</span>: max(clamp(0, (sqrt(max(var(--a1) - pow(var(--l1) - var(--pl), 2), 0)) - .55)
      / max(var(--l1) - var(--pl), 1e-4) * var(--soft), 1), sign(var(--pl) - var(--l1)));</pre></li>
      <li><h3>Second ray: the reflection</h3>
        <p>At the hit point, <code>m = d − 2(d·n)n</code> gives the reflected ray, which is tested again against the three spheres and the floor. The center sphere shows the checkerboard, the other spheres and the sun; the floor reflects the sky following Fresnel, with <code>pow(1 − |d·n|, 5)</code>. Fog uses <code>exp()</code>.</p>
<pre><span class="k">--fo</span>: calc(1 - var(--if) * (1 - exp(-.07 * max(0, var(--tm) - 7))));</pre></li>
      <li><h3>Scanline scheduler</h3>
        <p>Computing all {fmt(96 * 54)} pixels at once would freeze the tab for seconds. Every row starts as <code>display: none</code>, held there by 1 ms animations whose delay grows with the row index. While a row is hidden, the browser computes none of its pixels. Each control group owns one animation in the list, and <code>:has()</code> swaps its name when you pick an option. A new name restarts the animation, the rows disappear, and the image comes back from the top.</p>
<pre><span class="k">animation-name</span>: var(--a-cam), var(--a-hgt), var(--a-sun), var(--a-mat), var(--a-pas), …;
<span class="k">animation-delay</span>: calc(sibling-index() * var(--step) + 120ms);

.app:has(#m1:checked) .fb &gt; b {{ --mr: .12; --mg: .07; …; <span class="k">--a-mat</span>: rv-mat-m1 }}
@keyframes rv-mat-m1 {{ from, to {{ display: none }} }}</pre></li>
    </ol>
    <p>The scene is a tribute to Turner Whitted's 1980 image, the first to trace recursive reflections: spheres over a red and yellow checkerboard. It runs in Chrome and Edge 138 or later, which shipped <code>sibling-index()</code>, <code>sign()</code> and <code>abs()</code>. On a 2.8 GHz Xeon each pixel cost about 0.7 ms of style work, so the scheduler budgets {MS_PER_PX} ms per pixel: {step_ms(96)} ms per scanline at 96×54, about {eta_s(96, 54):.0f} seconds per frame.</p>
  </section>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{SITE_URL}docs/screenshot.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="color-scheme" content="dark">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Young+Serif&display=swap">
<style>
{PAGE_CSS}
{map_css()}
{resolution_css()}
/* ---------------------------------------------------------------- engine */
{engine_css()}
</style>
</head>
<body>
<main class="app">
  <header>
    <span class="eyebrow">Pure CSS · no JavaScript · no WebGL</span>
    <h1>Ray tracing in a stylesheet</h1>
    <p class="lede">Three spheres, a checkerboard floor, soft shadows, ambient occlusion and a mirror reflection. Every pixel is an <code>&lt;i&gt;</code> element whose color comes out of <code>sqrt()</code>, <code>pow()</code>, <code>exp()</code>, <code>hypot()</code>, <code>sign()</code> and <code>sibling-index()</code>.</p>
  </header>
  <p class="nosupport">This browser does not support <code>sibling-index()</code>. Open the page in Chrome or Edge 138 or later to see the render.</p>
  <section class="studio">
    <div class="left">
      <div class="window">
        <div class="titlebar"><span><span class="tiles" aria-hidden="true">{"<i></i>" * 8}</span><b>framebuffer</b> · pinhole, f = 2.0</span><span>Whitted, 1980 · re-implemented in CSS</span></div>
        <div class="stage">
          <div class="frame" role="img" aria-label="Render of three spheres over a red and yellow checkerboard floor, with reflections and soft shadows">
{framebuffers()}
          </div>
        </div>
        <div class="stats"><span class="stat-px"></span><span class="stat-rows"></span><span class="stat-eta"></span></div>
      </div>
      <div class="facts">
        <div><strong>{props}</strong><span>@property values per pixel</span></div>
        <div><strong>{row_props}</strong><span>properties per scanline</span></div>
        <div><strong>{fmt(props * 96 * 54)}</strong><span>values computed at 96×54</span></div>
        <div><strong>0</strong><span>lines of JavaScript</span></div>
      </div>
    </div>
{controls}
  </section>
{how}
  <footer><span>@property · sibling-index() · sibling-count() · sign() · hypot() · pow() · exp() · mod() · round() · :has() · display animations</span><a href="{REPO_URL}">Source on GitHub</a></footer>
</main>
</body>
</html>
"""


if __name__ == "__main__":
    out = ROOT / "index.html"
    html = page()
    out.write_text(html, encoding="utf-8")
    total = sum(w * h for w, h in RESOLUTIONS)
    print(f"wrote {out.relative_to(ROOT)}: {len(html.encode()):,} bytes, "
          f"{len(PIX) + 1} properties per pixel, {total:,} pixel elements across {len(RESOLUTIONS)} presets")
