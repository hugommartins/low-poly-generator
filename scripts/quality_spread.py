"""Print the quality scores of one or more CI legs, and how far they spread.

    python scripts/quality_spread.py quality-scores.json                 # one leg, as a Markdown table
    python scripts/quality_spread.py DIR_OR_FILE [DIR_OR_FILE ...]       # many legs: scores and spread

A directory is searched for `quality-scores*.json` files (the layout `gh run download` produces, one folder
per artifact). Each file is what `LOWPOLY_QUALITY_OUT` writes. The spread is the largest minus the smallest
value of each score across the legs, next to the stored baseline. Needs no third-party package.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "quality_baseline.json"


def load(paths):
    legs = {}
    for p in map(Path, paths):
        files = sorted(p.rglob("quality-scores*.json")) if p.is_dir() else [p]
        for f in files:
            data = json.loads(f.read_text())
            env = data.get("environment", {})
            label = f.parent.name if f.parent.name.startswith("quality-scores") else f.stem
            legs[label.removeprefix("quality-scores-")] = (env, data["scores"])
    return legs


def keys(scores):
    return [(p, s) for p in sorted(scores) for s in sorted(scores[p])]


def main(paths):
    legs = load(paths)
    if not legs:
        sys.exit("no quality-scores*.json found")
    base = json.loads(BASELINE.read_text())["scores"] if BASELINE.exists() else {}
    names = sorted(legs)
    print("### Quality scores\n")
    print("| Leg | Python | Platform | NumPy | OpenCV | SciPy | scikit-image |\n|---|---|---|---|---|---|---|")
    for n in names:
        e = legs[n][0]
        print(f"| {n} | {e.get('python', '')} | {e.get('platform', '')} | {e.get('numpy', '')} | "
              f"{e.get('opencv', '')} | {e.get('scipy', '')} | {e.get('scikit-image', '')} |")
    print()
    for metric, unit in (("ssim", ""), ("psnr", " dB")):
        spread_col = " Spread |" if len(names) > 1 else ""
        print(f"**{metric.upper()}{unit}**\n")
        print("| Photo / setting | Baseline | " + " | ".join(names) + " |" + spread_col)
        print("|---|---|" + "---|" * len(names) + ("---|" if spread_col else ""))
        worst = 0.0
        for p, s in keys(legs[names[0]][1]):
            vals = [legs[n][1].get(p, {}).get(s, {}).get(metric) for n in names]
            b = base.get(p, {}).get(s, {}).get(metric)
            got = [v for v in vals if v is not None]
            sp = (max(got) - min(got)) if len(got) > 1 else None
            worst = max(worst, sp or 0)
            cells = " | ".join("" if v is None else str(v) for v in vals)
            tail = f" {sp:.4g} |" if spread_col and sp is not None else (" |" if spread_col else "")
            print(f"| {p} / {s} | {'' if b is None else b} | {cells} |{tail}")
        if len(names) > 1:
            print(f"\nLargest spread across legs: {worst:.4g}{unit}\n")
        else:
            print()
    tri = {(p, s): {legs[n][1].get(p, {}).get(s, {}).get("triangles") for n in names} for p, s in keys(legs[names[0]][1])}
    differing = {k: sorted(v, key=lambda x: (x is None, x)) for k, v in tri.items() if len(v) > 1}
    if len(names) > 1:
        print("Triangle counts differ across legs: " + (
            ", ".join(f"{p}/{s} {v}" for (p, s), v in differing.items()) if differing else "no") + "\n")


if __name__ == "__main__":
    main(sys.argv[1:] or ["quality-scores.json"])