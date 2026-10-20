"""Saturation, smoothing and colour mode, measured on colour images only.
Run from the repo root:  python scripts/colour_options.py [--size 384] [--cells 16]
Greyscale images (colour spread below --min-chroma) are listed and left out, because these options cannot move them.
Needs scikit-image. Smoothing variants replace `smooth` in the module that defines `generate`."""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from lowpoly.core import generate  # noqa: E402

SEEDS = (0, 1, 2)
SATURATION = (0.6, 1.0, 1.3, 1.6, 2.0)
SMOOTHING = (0, 25, 50, 75, 100, 150)  # bilateral sigma; 0 = no filter
MODES = ("centroid", "mean")
DEFAULT = {"saturation": 1.3, "smoothing": 75, "mode": "centroid"}


def load(size, min_chroma):
    keep, dropped = {}, []
    for d in ("samples/inputs", "samples/study"):
        for p in sorted((ROOT / d).glob("*.jpg")) + sorted((ROOT / d).glob("*.png")):
            img = cv2.imread(str(p))
            if img is None:
                continue
            s = size / max(img.shape[:2])
            if s < 1:
                img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            chroma = float((img.max(axis=2).astype(int) - img.min(axis=2)).mean())
            if chroma >= min_chroma:
                keep[p.stem] = img
            else:
                dropped.append(p.stem)
    return keep, dropped


def smoother(sigma):
    def smooth(img, saturation=1.3):
        out = img if sigma == 0 else cv2.bilateralFilter(img, d=9, sigmaColor=sigma, sigmaSpace=sigma)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return smooth


def score(img, grid, saturation, sigma, mode):
    generate.__globals__["smooth"] = smoother(sigma)
    out = []
    for seed in SEEDS:
        res = generate(img, grid_size=grid, saturation=saturation, seed=seed, color_mode=mode)
        png = res.to_png(1)
        out.append((ssim(img, png, channel_axis=2, data_range=255), psnr(img, png, data_range=255)))
    return np.mean(out, axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=384)
    ap.add_argument("--cells", type=int, default=16)
    ap.add_argument("--min-chroma", type=float, default=8.0)
    a = ap.parse_args()
    images, dropped = load(a.size, a.min_chroma)
    print(f"{len(images)} colour images; left out as greyscale: {', '.join(dropped) or 'none'}")
    variants = ([("saturation", v, dict(saturation=v)) for v in SATURATION]
                + [("smoothing", v, dict(sigma=v)) for v in SMOOTHING]
                + [("mode", v, dict(mode=v)) for v in MODES])
    base = {"saturation": DEFAULT["saturation"], "sigma": DEFAULT["smoothing"], "mode": DEFAULT["mode"]}
    table = {}
    for name, img in images.items():
        grid = max(2, round(max(img.shape[:2]) / a.cells))
        ref = score(img, grid, **base)
        for opt, val, kw in variants:
            s = score(img, grid, **{**base, **kw})
            table.setdefault((opt, val), []).append((s[0], s[1], s[0] - ref[0]))
    print(f"\n{'option':<11}{'value':<10}{'SSIM':>8}{'PSNR dB':>9}{'vs default':>12}{'better than default':>21}")
    for (opt, val), rows in table.items():
        m = np.mean(rows, axis=0)
        better = sum(r[2] > 0 for r in rows)
        flag = "  (default)" if DEFAULT[opt] == val else ""
        print(f"{opt:<11}{str(val):<10}{m[0]:8.4f}{m[1]:9.2f}{m[2]:+12.4f}{better:>12} of {len(rows)}{flag}")


main()