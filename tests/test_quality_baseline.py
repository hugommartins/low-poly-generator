"""Quality baseline: the sample photos must keep the similarity scores stored in quality_baseline.json.

Why: with no expected image, a stored score is the only reference for "has the output got worse".
Method and validation: docs/BASELINE_REPORT.md. After an intended output change, review the new images
and regenerate with `python scripts/update_quality_baseline.py`.

Environment variables:
  LOWPOLY_QUALITY_MODE=report   print differences instead of failing (used on CI until the spread is known)
  LOWPOLY_QUALITY_OUT=file.json write the measured scores and environment to this file
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quality_support as qs  # noqa: E402

try:
    import skimage  # noqa: F401
except ImportError:
    skimage = None


class ComparisonTests(unittest.TestCase):
    """The comparison itself, without scikit-image."""

    stored = {"a": {"s": {"ssim": 0.50, "psnr": 20.0, "triangles": 400}}}

    def measured(self, ssim, psnr):
        return {"a": {"s": {"ssim": ssim, "psnr": psnr, "triangles": 400}}}

    def test_a_score_inside_the_tolerance_passes(self):
        self.assertEqual(qs.compare(self.stored, self.measured(0.505, 20.2)), [])

    def test_a_drop_beyond_the_tolerance_is_found(self):
        self.assertEqual(
            [f["kind"] for f in qs.compare(self.stored, self.measured(0.48, 20.0))],
            ["drop"],
        )
        self.assertEqual(
            [f["kind"] for f in qs.compare(self.stored, self.measured(0.50, 19.5))],
            ["drop"],
        )

    def test_a_rise_beyond_the_tolerance_is_found_too(self):
        self.assertEqual(
            [f["kind"] for f in qs.compare(self.stored, self.measured(0.55, 20.0))],
            ["rise"],
        )

    def test_a_missing_entry_is_found(self):
        self.assertEqual([f["kind"] for f in qs.compare(self.stored, {})], ["missing"])


@unittest.skipUnless(skimage, "scikit-image not installed (pip install -e '.[test]')")
class BaselineTests(unittest.TestCase):
    def test_sample_scores_match_the_baseline(self):
        measured = qs.score_all()
        out = os.environ.get("LOWPOLY_QUALITY_OUT")
        if out:
            Path(out).write_text(
                json.dumps(
                    {"environment": qs.environment(), "scores": measured}, indent=1
                )
            )
        found = qs.compare(qs.load_baseline()["scores"], measured)
        if not found:
            return
        message = (
            f"scores moved by more than SSIM {qs.SSIM_TOL} or PSNR {qs.PSNR_TOL_DB} dB:\n  "
            + "\n  ".join(qs.describe(found))
            + "\nIf the output change is intended, review the images, then run "
            "`python scripts/update_quality_baseline.py`."
        )
        if os.environ.get("LOWPOLY_QUALITY_MODE") == "report":
            print("QUALITY BASELINE (report only): " + message, file=sys.stderr)
        else:
            self.fail(message)


if __name__ == "__main__":
    unittest.main()
