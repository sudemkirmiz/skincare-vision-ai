# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Turn the recorded demo tour into the README animation, screenshots/demo.webp.

Usage:  .venv\\Scripts\\python scripts\\make_demo_animation.py [--fps 12] [--width 1280] [--quality 80]
Record the tour first with `node scripts/demo-tour.mjs video` in frontend/ (see that file).

Animated WebP instead of GIF: it keeps full colour, so the face photo, text and soft gradients stay crisp,
at a fraction of a GIF's size. GIF's 256-colour limit is what made the first animation look pixelated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "outputs" / "demo" / "frames"


def timeline(frames_dir: Path, fps: float) -> tuple[list[Path], list[int]]:
    """Resample the screencast (frames arrive only when the page repaints) onto an even clock."""
    timings = json.loads((frames_dir / "timings.json").read_text(encoding="utf-8"))
    # Skip the blank frames painted while the first page loads.
    first = next((k for k, item in enumerate(timings)
                  if max(ImageStat.Stat(Image.open(frames_dir / item["name"]).convert("L")).stddev) > 12), None)
    if first is None:
        raise SystemExit(f"no usable frames in {frames_dir}")
    timings = timings[first:]
    start, end = timings[0]["t"], timings[-1]["t"]
    step = 1 / fps
    paths: list[Path] = []
    durations: list[int] = []
    index, clock, last_name = 0, start, None
    while clock <= end + step:
        while index + 1 < len(timings) and timings[index + 1]["t"] <= clock:
            index += 1
        name = timings[index]["name"]
        if name == last_name:
            durations[-1] += round(step * 1000)  # nothing repainted: hold the frame longer
        else:
            paths.append(frames_dir / name)
            durations.append(round(step * 1000))
            last_name = name
        clock += step
    durations[-1] += 2500  # rest on the last frame before looping
    return paths, durations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, default=FRAMES)
    parser.add_argument("--fps", type=float, default=12)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--quality", type=int, default=80)
    args = parser.parse_args()

    paths, durations = timeline(args.frames, args.fps)

    def frame(path: Path) -> Image.Image:
        image = Image.open(path).convert("RGB")
        if image.width != args.width:
            image = image.resize((args.width, round(image.height * args.width / image.width)), Image.LANCZOS)
        return image

    images = [frame(path) for path in paths]
    out = ROOT / "screenshots" / "demo.webp"
    # method 4 is the speed/size sweet spot; 6 takes many times longer for a few percent.
    images[0].save(out, save_all=True, append_images=images[1:], duration=durations, loop=0, quality=args.quality, method=4)
    print(f"{out.name}: {len(images)} frames, {sum(durations) / 1000:.0f} s, {out.stat().st_size / 1_048_576:.1f} MB")


if __name__ == "__main__":
    main()
