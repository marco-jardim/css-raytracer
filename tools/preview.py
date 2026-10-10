"""Render index.html in headless Chromium and save what it draws.

Needs Playwright:  pip install playwright && playwright install chromium

    python3 tools/preview.py                          # 96x54 still -> docs/screenshot.png
    python3 tools/preview.py --res 320 --out docs/render-320.png
    python3 tools/preview.py --gif docs/scanline.gif  # record the scanline render
    python3 tools/preview.py --page docs/page.png     # whole page, for the README

It also prints the long animation frames seen during the render, which is
the quickest way to see whether the scanline budget (MS_PER_PX in
src/build.py) is too tight for the machine: if frame times keep growing
until the image is done, rows are arriving faster than they can be styled.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from build import RESOLUTIONS, eta_s, step_ms  # noqa: E402

FRAME_LOG = """
window.__frames = [];
(function tick(last) {
  requestAnimationFrame(t => { window.__frames.push(Math.round(t - last)); tick(t); });
})(performance.now());
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", type=int, default=96, help="framebuffer width preset (%s)" % ", ".join(str(w) for w, _ in RESOLUTIONS))
    ap.add_argument("--out", default=str(ROOT / "docs" / "screenshot.png"), help="PNG of the framebuffer")
    ap.add_argument("--page", help="also save a PNG of the top of the page")
    ap.add_argument("--gif", help="record the scanline render to this GIF")
    ap.add_argument("--width", type=int, default=1280, help="viewport width")
    ap.add_argument("--scale", type=float, default=1, help="device scale factor")
    ap.add_argument("--wait", type=float, help="seconds to wait for the frame (default: from the preset)")
    ap.add_argument("--click", nargs="*", default=[], help="control ids to click first, e.g. m1 p2 c1")
    args = ap.parse_args()

    sizes = dict(RESOLUTIONS)
    if args.res not in sizes:
        ap.error(f"unknown preset {args.res}")
    wait = args.wait or eta_s(args.res, sizes[args.res]) * 1.8 + 2

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": 900}, device_scale_factor=args.scale)
        page.add_init_script(FRAME_LOG)
        page.goto((ROOT / "index.html").as_uri(), wait_until="load")
        for cid in args.click:
            page.click(f"label:has(#{cid})")
        if args.res != 96:
            page.click(f"label:has(#r{args.res})")
        page.evaluate("window.__frames = []")
        frame = page.query_selector(".frame")

        if args.gif:
            # Headless screenshots are slow and would stall a real-time render,
            # so the scanline budget is stretched while recording and the GIF is
            # played back at the real pace.
            from PIL import Image
            w, h = args.res, sizes[args.res]
            real_ms = step_ms(w)
            slow_ms = max(real_ms, 300)
            page.add_style_tag(content=f".fb-{w}>b{{--step:{slow_ms}ms!important}}")
            other = next(x for x, _ in RESOLUTIONS if x != w)
            page.click(f"label:has(#r{other})")
            page.click(f"label:has(#r{w})")  # redisplay -> the reveal restarts at the slow pace
            tmp = ROOT / ".preview-frame.png"
            shots, t0 = [], time.time()
            total = (slow_ms * h + 600) / 1000
            while time.time() - t0 < total:
                frame.screenshot(path=str(tmp))
                shots.append(Image.open(tmp).convert("RGB"))
            tmp.unlink(missing_ok=True)
            per_frame = max(20, round(total * 1000 / len(shots) * real_ms / slow_ms))
            frames = [im.resize((640, round(640 * im.height / im.width))) for im in shots]
            sheet = Image.new("RGB", (frames[0].width, frames[0].height * 2))
            sheet.paste(frames[0], (0, 0))
            sheet.paste(frames[-1], (0, frames[0].height))
            pal = sheet.quantize(colors=160, method=Image.Quantize.MEDIANCUT)
            frames = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
            durations = [per_frame] * (len(frames) - 1) + [3000]
            frames[0].save(args.gif, save_all=True, append_images=frames[1:], duration=durations, loop=0)
            print(f"gif: {args.gif} ({len(frames)} frames, {per_frame} ms each)")
            page.add_style_tag(content=f".fb-{w}>b{{--step:{real_ms}ms!important}}")
        else:
            time.sleep(wait)

        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        frame.screenshot(path=args.out)
        print(f"png: {args.out}")
        if args.page:
            page.screenshot(path=args.page)
            print(f"page: {args.page}")

        long = [ms for ms in page.evaluate("window.__frames") if ms > 50]
        print(f"long frames (>50 ms) during the render: {len(long)}; max {max(long, default=0)} ms")
        if long:
            print("sequence:", long[:40])
        browser.close()


if __name__ == "__main__":
    main()
