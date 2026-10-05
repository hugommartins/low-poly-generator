"""Command line: `lowpoly INPUT OUTPUT [options]` (a file, or a folder of images to a folder)."""
from __future__ import annotations

import argparse
from pathlib import Path

from .core import render_file

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def build_parser():
    p = argparse.ArgumentParser(prog="lowpoly", description="Turn an image into a low-poly SVG or PNG.")
    p.add_argument("input", help="image file, or a folder of images")
    p.add_argument("output", help="output .svg or .png (or a folder when input is a folder)")
    p.add_argument("--grid-size", type=int, default=25, help="cell size in px; smaller = more triangles (default 25)")
    p.add_argument("--jitter", type=int, default=12, help="random offset / edge search radius in px (default 12)")
    p.add_argument("--saturation", type=float, default=1.3, help="HSV saturation multiplier (default 1.3)")
    p.add_argument("--canny-low", type=int, default=100, help="Canny low threshold (default 100)")
    p.add_argument("--canny-high", type=int, default=200, help="Canny high threshold (default 200)")
    p.add_argument("--color-mode", choices=["centroid", "mean"], default="centroid",
                   help="triangle colour: centroid pixel (fast) or mean of pixels (smoother)")
    p.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
    p.add_argument("--max-size", type=int, help="downscale so the longest side is at most this many px")
    p.add_argument("--scale", type=int, default=1, help="PNG output scale factor (default 1)")
    r = p.add_argument_group("3D relief (lights the triangles as if they had height)")
    r.add_argument("--relief", type=float, default=0.0,
                   help="relief height as %% of the longest side; 0 = off (try 10 to 15)")
    r.add_argument("--depth-map", help="greyscale depth image, brighter = closer")
    r.add_argument("--light-angle", type=float, default=315.0, help="degrees the light comes from: 0 top, 90 right, 315 top left")
    r.add_argument("--light-elevation", type=float, default=55.0, help="degrees above the image plane (default 55)")
    r.add_argument("--shading", type=float, default=1.0, help="shading strength, 0 to 1.5 (default 1)")
    p.add_argument("--format", choices=["svg", "png"], default="svg", help="output format when input is a folder")
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    params = dict(grid_size=a.grid_size, jitter=a.jitter, saturation=a.saturation, seed=a.seed,
                  color_mode=a.color_mode, canny_low=a.canny_low, canny_high=a.canny_high,
                  relief=a.relief, light_angle=a.light_angle, light_elevation=a.light_elevation, shading=a.shading)
    if a.relief <= 0 and a.depth_map:
        raise SystemExit("--depth-map needs --relief greater than 0")
    src, dst = Path(a.input).expanduser(), Path(a.output).expanduser()
    try:
        return run(a, src, dst, params)
    except (FileNotFoundError, ValueError, OSError) as e:
        raise SystemExit(f"lowpoly: error: {e}")


def run(a, src, dst, params):
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        files = sorted(f for f in src.iterdir() if f.suffix.lower() in IMAGE_EXTS)
        if not files:
            raise FileNotFoundError(f"no images found in {src}")
        used = set()
        for f in files:
            name = f.stem if f.stem not in used else f"{f.stem}_{f.suffix[1:].lower()}"  # a.jpg and a.png
            used.add(f.stem)
            out = dst / f"{name}.{a.format}"
            render_file(f, out, max_size=a.max_size, scale=a.scale, depth_map=a.depth_map, **params)
            print(f"{f.name} -> {out}")
    else:
        render_file(src, dst, max_size=a.max_size, scale=a.scale, depth_map=a.depth_map, **params)
        print(f"wrote {dst}")
    return 0