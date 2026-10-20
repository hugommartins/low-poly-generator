"""Does Canny 100/200 stay best when the reference edges are not Canny edges?
Run from the repo root:  python scripts/canny_reference.py [--bsds DIR]
References (each photo, 384 px long side, grid 16, jitter 12, seeds 0-2):
  canny  Canny 100/200 on the photo (the circular control)
  sobel  thinned Sobel magnitude, density matched to canny
  log    Laplacian-of-Gaussian zero crossings, strongest pixels, density matched to canny
  bsds   human-drawn boundaries (BSDS500), if --bsds is given; images are matched by file stem
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import gaussian_laplace, sobel as ndsobel
from skimage.morphology import skeletonize

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from lowpoly.core import generate  # noqa: E402

SETTINGS = ((25, 50), (50, 100), (100, 200), (200, 400))
SEEDS = (0, 1, 2)
SIZE, CELLS = 384, 16


def load(size):
    for d in ("samples/inputs", "samples/study"):
        for p in sorted((ROOT / d).glob("*.jpg")) + sorted((ROOT / d).glob("*.png")):
            img = cv2.imread(str(p))
            if img is None:
                continue
            s = size / max(img.shape[:2])
            if s < 1:
                img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            yield p.stem, img


def match_density(score, valid, count):
    count = min(count, int(valid.sum()))
    if count == 0:
        return np.zeros(score.shape, bool)
    thr = np.partition(score[valid], -count)[-count]
    return valid & (score >= thr)


def references(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    canny = cv2.Canny(g, 100, 200) > 0
    n = int(canny.sum())
    gf = g.astype(np.float32)
    mag = np.hypot(ndsobel(gf, 0), ndsobel(gf, 1))
    sob = skeletonize(match_density(mag, mag > 0, 3 * n)) if n else canny
    lap = gaussian_laplace(gf, 2.0)
    zc = (np.sign(lap) != np.sign(np.roll(lap, 1, 0))) | (np.sign(lap) != np.sign(np.roll(lap, 1, 1)))
    log = match_density(mag, zc, n)
    return {"canny": canny, "sobel": sob, "log": log}


def mesh_near(res):
    w, h = res.size
    canvas = np.zeros((h, w), np.uint8)
    for a, b, c in res.simplices:
        cv2.polylines(canvas, [res.points[[a, b, c]].astype(np.int32)], True, 255, 1)
    return cv2.distanceTransform(255 - canvas, cv2.DIST_L2, 3) <= 2


def bsds_truth(root, stem, shape):
    import scipy.io as sio
    for f in Path(root).rglob(stem + ".mat"):
        gt = sio.loadmat(str(f))["groundTruth"][0]
        b = np.zeros(gt[0][0][0][1].shape, bool)
        for a in gt:
            b |= a[0][0][1] > 0
        return cv2.resize(b.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bsds")
    a = ap.parse_args()
    lifts = {}
    for stem, img in load(SIZE):
        refs = references(img)
        if a.bsds:
            t = bsds_truth(a.bsds, stem, img.shape[:2])
            if t is not None:
                refs["bsds"] = t
        grid = max(2, round(max(img.shape[:2]) / CELLS))
        for lo, hi in SETTINGS:
            for seed in SEEDS:
                near = mesh_near(generate(img, grid_size=grid, canny_low=lo, canny_high=hi, seed=seed))
                for name, e in refs.items():
                    if e.any():
                        lifts.setdefault((name, lo, hi), []).append(near[e].mean() - near.mean())
    print(f"{'reference':<8}" + "".join(f"{lo}/{hi:<8}" for lo, hi in SETTINGS) + "best   images")
    for name in ("canny", "sobel", "log", "bsds"):
        if (name, *SETTINGS[0]) not in lifts:
            continue
        m = [float(np.mean(lifts[(name, lo, hi)])) for lo, hi in SETTINGS]
        best = SETTINGS[int(np.argmax(m))]
        print(f"{name:<8}" + "".join(f"{x:<12.4f}" for x in m) + f"{best[0]}/{best[1]}  {len(lifts[(name, *SETTINGS[0])]) // len(SEEDS)}")


main()