"""Shared helpers for the quality baseline: scoring, comparison and environment record.

Scoring needs scikit-image (a test dependency, not a package dependency). Comparison does not.
"""

import json
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASELINE = HERE / "quality_baseline.json"
SAMPLES = ROOT / "samples" / "inputs"

MAX_SIZE = 450  # long side the sample photos are loaded at
SETTINGS = {"default": {}, "grid16": {"grid_size": 16}}  # name -> generate() arguments

# Largest score change treated as noise. Taken from the study's seed noise (SSIM sd 0.002 to 0.006,
# PSNR sd 0.1 to 0.3 dB). A run with the seed fixed is repeatable. Measured across CI platforms (Linux, Windows,
# macOS on Apple silicon) the spread is at most 0.0007 SSIM and 0.02 dB (docs/BASELINE_REPORT.md), so these have headroom.
SSIM_TOL = 0.01
PSNR_TOL_DB = 0.3


def environment():
    import cv2
    import numpy
    import scipy
    import skimage

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "opencv": cv2.__version__,
        "scipy": scipy.__version__,
        "scikit-image": skimage.__version__,
    }


def score_all(max_size=MAX_SIZE):
    """{photo: {setting: {"ssim", "psnr", "triangles"}}} for every sample photo, at the default seed."""
    from skimage.metrics import peak_signal_noise_ratio, structural_similarity

    from lowpoly.core import generate, load_image

    out = {}
    for path in sorted(SAMPLES.glob("*.[jp][pn]g")):
        photo = load_image(path, max_size)
        out[path.stem] = {}
        for name, params in SETTINGS.items():
            res = generate(photo, **params)
            png = res.to_png(1)
            out[path.stem][name] = {
                "ssim": round(
                    float(
                        structural_similarity(
                            photo, png, channel_axis=2, data_range=255
                        )
                    ),
                    4,
                ),
                "psnr": round(
                    float(peak_signal_noise_ratio(photo, png, data_range=255)), 2
                ),
                "triangles": int(len(res.simplices)),
            }
    return out


def compare(stored, measured, ssim_tol=SSIM_TOL, psnr_tol=PSNR_TOL_DB):
    """List what differs from the baseline by more than the tolerance, in either direction.

    A rise counts too: an unreviewed jump in similarity can be a different look (for example a colour
    option ignored), not an improvement.
    """
    found = []
    for photo in sorted(set(stored) | set(measured)):
        for setting in sorted(
            set(stored.get(photo, {})) | set(measured.get(photo, {}))
        ):
            old, new = (
                stored.get(photo, {}).get(setting),
                measured.get(photo, {}).get(setting),
            )
            if old is None or new is None:
                found.append({"photo": photo, "setting": setting, "kind": "missing"})
                continue
            for key, tol in (("ssim", ssim_tol), ("psnr", psnr_tol)):
                delta = new[key] - old[key]
                if abs(delta) > tol:
                    found.append(
                        {
                            "photo": photo,
                            "setting": setting,
                            "metric": key,
                            "stored": old[key],
                            "measured": new[key],
                            "delta": round(delta, 4),
                            "kind": "drop" if delta < 0 else "rise",
                        }
                    )
    return found


def describe(findings):
    lines = []
    for f in findings:
        if f["kind"] == "missing":
            lines.append(
                f"{f['photo']}/{f['setting']}: not in both the baseline and the measurement"
            )
        else:
            lines.append(
                f"{f['photo']}/{f['setting']} {f['metric']}: {f['stored']} -> {f['measured']} "
                f"({f['delta']:+}, {f['kind']})"
            )
    return lines


def load_baseline():
    return json.loads(BASELINE.read_text())
