"""Regenerate tests/quality_baseline.json from the current code.

Run only after reviewing the changed output (docs/BASELINE_REPORT.md says how). Needs scikit-image.
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import quality_support as qs  # noqa: E402


def main():
    data = {
        "about": "Similarity of the sample photos' output to the photo, at the default seed. See docs/BASELINE_REPORT.md.",
        "created": date.today().isoformat(),
        "tolerance": {"ssim": qs.SSIM_TOL, "psnr_db": qs.PSNR_TOL_DB},
        "max_size": qs.MAX_SIZE,
        "settings": qs.SETTINGS,
        "environment": qs.environment(),
        "scores": qs.score_all(),
    }
    qs.BASELINE.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {qs.BASELINE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
