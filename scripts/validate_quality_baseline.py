"""Check that the quality baseline catches real faults and ignores harmless changes.

Each mutant is a copy of the package with one change to the source under src/lowpoly/. Each text edit is applied to
the one module that contains the text (a parameter-default edit, to every place the default is written), so it works whether the pipeline sits in one file or several. For every
mutant the script records
- whether the existing tests (without the baseline test) fail, split into the differential test and the rest;
- how far the sample scores move from tests/quality_baseline.json and whether the baseline would fail.

Usage: python scripts/validate_quality_baseline.py [--check] [--markdown] [--json FILE]
  --check   only verify that every edit applies to the current source, then stop (seconds)
Needs scikit-image. A full run takes several minutes. Writes nothing into the project.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import quality_support as qs  # noqa: E402


def default(name, old, new):
    """Edit that changes a parameter default wherever it is written (`name=100`, `name: int = 100`)."""
    return re.compile(rf"(\b{name}\s*(?::[^=,)\n]+)?=\s*){old}\b"), rf"\g<1>{new}"


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
        [default("canny_low", 100, 10), default("canny_high", 200, 20)],
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
    "seed_7": ("harmless", "default seed 42 changed to 7", [default("seed", 42, 7)]),
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


def apply_edits(package_dir, edits):
    """Apply each (old, new) to the single module under package_dir that contains `old`. Raises ValueError otherwise."""
    modules = sorted(package_dir.glob("*.py"))
    for old, new in edits:
        if isinstance(
            old, re.Pattern
        ):  # every match in every module; at least one must exist
            total = 0
            for m in modules:
                text, n = old.subn(new, m.read_text())
                if n:
                    m.write_text(text)
                total += n
            if not total:
                raise ValueError(f"edit does not apply (no match): {old.pattern!r}")
            continue
        hits = [m for m in modules if old in m.read_text()]
        if len(hits) != 1:
            where = ", ".join(m.name for m in hits) or "no module"
            raise ValueError(f"edit does not apply (found in {where}): {old!r}")
        hits[0].write_text(hits[0].read_text().replace(old, new))


def build(workdir, edits):
    for sub in ("src", "tests", "samples"):
        shutil.copytree(
            ROOT / sub, workdir / sub, ignore=shutil.ignore_patterns("__pycache__")
        )
    (
        workdir / "tests" / "test_quality_baseline.py"
    ).unlink()  # the baseline test is measured separately
    apply_edits(workdir / "src" / "lowpoly", edits)


def check_edits():
    """Dry run of every mutant's edits on a copy of the source. Returns {name: error} for the ones that fail."""
    bad = {}
    for name, (_, _, edits) in MUTANTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "lowpoly"
            shutil.copytree(
                ROOT / "src" / "lowpoly",
                pkg,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            try:
                apply_edits(pkg, edits)
            except ValueError as e:
                bad[name] = str(e)
    return bad


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
    ap.add_argument(
        "--check", action="store_true", help="only verify that every edit applies"
    )
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    bad = check_edits()
    for name, msg in bad.items():
        print(f"{name}: {msg}", file=sys.stderr)
    if bad:
        sys.exit(
            f"{len(bad)} of {len(MUTANTS)} changes no longer apply to the source; update their (old, new) text first"
        )
    print(f"all {len(MUTANTS)} changes apply", file=sys.stderr)
    if args.check:
        return
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
