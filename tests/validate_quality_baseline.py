"""Check that the quality baseline catches real faults and ignores harmless changes.

Each mutant is a copy of the package with one change to core.py. For every mutant the script records
- whether the existing tests (without the baseline test) fail, split into the differential test and the rest;
- how far the sample scores move from tests/quality_baseline.json and whether the baseline would fail.

Usage: python scripts/validate_quality_baseline.py [--markdown] [--json FILE]
Needs scikit-image. Takes about a minute. Writes nothing into the project.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import quality_support as qs  # noqa: E402

CENTROID_RETURN = "return img[c[:, 1], c[:, 0]][:, ::-1]"
CENTROID_CLIP = "c = np.clip(tris.mean(axis=1).astype(int), [0, 0], [w - 1, h - 1])"

# name -> (group, description, [(old, new), ...])
MUTANTS = {
    "no_smooth": (
        "fault",
        "smoothing filter skipped",
        [
            (
                "out = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)",
                "out = img.copy()",
            )
        ],
    ),
    "rgb_swapped": (
        "fault",
        "red and blue swapped in the colours",
        [(CENTROID_RETURN, "return img[c[:, 1], c[:, 0]]")],
    ),
    "transposed": (
        "fault",
        "colour sampled at transposed coordinates",
        [
            (
                CENTROID_RETURN,
                "return img[np.clip(c[:, 0], 0, h - 1), np.clip(c[:, 1], 0, w - 1)][:, ::-1]",
            )
        ],
    ),
    "no_snap": (
        "fault",
        "points no longer search for an edge pixel",
        [
            (
                "x1, x2 = max(0, cx - jitter), min(w, cx + jitter)",
                "x1, x2 = cx, min(w, cx + 1)",
            ),
            (
                "y1, y2 = max(0, cy - jitter), min(h, cy + jitter)",
                "y1, y2 = cy, min(h, cy + 1)",
            ),
        ],
    ),
    "edges_on_smoothed": (
        "fault",
        "Canny run on the smoothed image",
        [
            (
                "edges = detect_edges(img, canny_low, canny_high)",
                "edges = detect_edges(smoothed, canny_low, canny_high)",
            )
        ],
    ),
    "canny_10_20": (
        "fault",
        "default Canny thresholds changed to 10/20",
        [
            (
                "canny_low=100, canny_high=200, relief=0.0",
                "canny_low=10, canny_high=20, relief=0.0",
            )
        ],
    ),
    "half_density": (
        "fault",
        "every other grid cell skipped",
        [
            (
                "for y in range(0, h, grid_size):\n        for x in range(0, w, grid_size):",
                "for y in range(0, h, grid_size * 2):\n        for x in range(0, w, grid_size * 2):",
            )
        ],
    ),
    "no_anchors": (
        "fault",
        "border anchor points removed",
        [("    if anchors:\n", "    if False:\n")],
    ),
    "saturation_ignored": (
        "fault",
        "saturation option ignored (always 1.0)",
        [("hsv[:, :, 1] * saturation", "hsv[:, :, 1] * 1.0")],
    ),
    "seed_7": (
        "harmless",
        "default seed 42 changed to 7",
        [("saturation=1.3, seed=42, color_mode", "saturation=1.3, seed=7, color_mode")],
    ),
    "bilateral_window_7": (
        "harmless",
        "bilateral window 9 changed to 7",
        [("d=9, sigmaColor", "d=7, sigmaColor")],
    ),
}
for n in (1, 2, 4, 8):
    MUTANTS[f"darker_{n}"] = (
        "size",
        f"colours {n} level{'s' if n > 1 else ''} darker",
        [
            (
                CENTROID_RETURN,
                f"return np.clip(img[c[:, 1], c[:, 0]][:, ::-1].astype(np.int16) - {n}, 0, 255).astype(np.uint8)",
            )
        ],
    )
for n in (1, 2, 3):
    MUTANTS[f"shift_{n}px"] = (
        "size",
        f"colour sampled {n} px right and down",
        [
            (
                CENTROID_CLIP,
                f"c = np.clip(tris.mean(axis=1).astype(int) + {n}, [0, 0], [w - 1, h - 1])",
            )
        ],
    )
for n in (5, 15, 30):
    MUTANTS[f"right_strip_{n}px"] = (
        "size",
        f"triangles in the right {n} px painted black",
        [
            (
                CENTROID_RETURN,
                f"res_ = img[c[:, 1], c[:, 0]][:, ::-1].copy(); res_[c[:, 0] > w - {n}] = 0; return res_",
            )
        ],
    )


def build(workdir, edits):
    for sub in ("src", "tests", "samples"):
        shutil.copytree(
            ROOT / sub, workdir / sub, ignore=shutil.ignore_patterns("__pycache__")
        )
    (
        workdir / "tests" / "test_quality_baseline.py"
    ).unlink()  # the baseline test is measured separately
    core = workdir / "src" / "lowpoly" / "core.py"
    text = core.read_text()
    for old, new in edits:
        assert old in text, f"edit does not apply: {old!r}"
        text = text.replace(old, new)
    core.write_text(text)


def existing_tests(workdir):
    env = dict(os.environ, PYTHONPATH=str(workdir / "src"))
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
    )
    failed = [ln for ln in p.stderr.splitlines() if ln.startswith(("FAIL:", "ERROR:"))]
    differential = [
        ln for ln in failed if "test_differential" in ln or "DifferentialTests" in ln
    ]
    return {"differential": len(differential), "other": len(failed) - len(differential)}


def scores(workdir):
    code = (
        "import sys, json; sys.path.insert(0, 'src'); sys.path.insert(0, 'tests');"
        "import quality_support as q; print(json.dumps(q.score_all()))"
    )
    p = subprocess.run(
        [sys.executable, "-c", code],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PYTHONPATH=str(workdir / "src")),
    )
    return json.loads(p.stdout.strip().splitlines()[-1])


def run_one(name, edits, stored):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        build(work, edits)
        tests = existing_tests(work)
        measured = scores(work)
    d_ssim = [
        measured[p][s]["ssim"] - stored[p][s]["ssim"] for p in stored for s in stored[p]
    ]
    d_psnr = [
        measured[p][s]["psnr"] - stored[p][s]["psnr"] for p in stored for s in stored[p]
    ]
    found = qs.compare(stored, measured)
    return {
        "tests": tests,
        "ssim": [round(min(d_ssim), 3), round(max(d_ssim), 3)],
        "psnr": [round(min(d_psnr), 2), round(max(d_psnr), 2)],
        "baseline": sorted({f["kind"] for f in found}),  # drop, rise
        "findings": len(found),
    }


def markdown(results):
    def mark(b):
        return "caught" if b else "missed"

    rows = [
        "| Change | Group | Existing tests, other than the differential test | Baseline | SSIM change | PSNR change (dB) |",
        "|---|---|---|---|---|---|",
    ]
    for name, r in results.items():
        group, desc, _ = MUTANTS[name]
        other = (
            mark(r["tests"]["other"])
            if group != "harmless"
            else ("flagged" if r["tests"]["other"] else "not flagged")
        )
        base = ", ".join(r["baseline"]) if r["baseline"] else "none"
        base = (
            ("caught (" + base + ")")
            if r["baseline"] and group != "harmless"
            else (
                ("false alarm (" + base + ")")
                if r["baseline"]
                else ("missed" if group != "harmless" else "not flagged")
            )
        )
        rows.append(
            f"| {desc} | {group} | {other} | {base} | {r['ssim'][0]:+.3f} to {r['ssim'][1]:+.3f} "
            f"| {r['psnr'][0]:+.2f} to {r['psnr'][1]:+.2f} |"
        )
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    stored = qs.load_baseline()["scores"]
    results = {}
    for name, (_, desc, edits) in MUTANTS.items():
        results[name] = run_one(name, edits, stored)
        print(
            f"{name}: baseline={results[name]['baseline']} other_tests_failed={results[name]['tests']['other']}",
            file=sys.stderr,
            flush=True,
        )
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1))
    if args.markdown:
        print(markdown(results))


if __name__ == "__main__":
    main()
