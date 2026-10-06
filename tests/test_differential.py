"""Differential test: the package must produce the same SVG as the author's original script.

The oracle is tests/reference/border_uniform_low_poly.py, run in the same environment as the package,
so OpenCV and SciPy builds are identical on both sides and a byte-for-byte comparison is valid on any
platform. (A stored golden file would not be: its bytes depend on the build that made it.)
"""

import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from lowpoly import low_poly
from lowpoly.core import load_image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / "reference"))
from border_uniform_low_poly import border_uniform_low_poly

SAMPLES = sorted((ROOT / "samples" / "inputs").glob("*.[jp][pn]g"))
SETTINGS = [(10, 12), (25, 12), (18, 6), (30, 20)]  # (grid_size, jitter_range)


def reference_svg(path, grid, jitter, tmp):
    out = Path(tmp) / "reference.svg"
    border_uniform_low_poly(str(path), str(out), grid_size=grid, jitter_range=jitter)
    return out.read_text()


class DifferentialTests(unittest.TestCase):
    def check(self, path, grid, jitter):
        with tempfile.TemporaryDirectory() as tmp:
            expected = reference_svg(path, grid, jitter, tmp)
        actual = low_poly(load_image(path), grid_size=grid, jitter=jitter)
        self.assertEqual(
            actual.count("<polygon"),
            expected.count("<polygon"),
            "triangle count differs",
        )
        self.assertEqual(actual, expected)

    def test_samples_match_the_original_script(self):
        self.assertTrue(SAMPLES, "no sample photos found in samples/inputs")
        for path in SAMPLES:
            for grid, jitter in SETTINGS:
                with self.subTest(photo=path.name, grid=grid, jitter=jitter):
                    self.check(path, grid, jitter)

    def test_odd_sizes_match_the_original_script(self):
        """Sizes that are not multiples of the grid, including very small ones."""
        rng = np.random.RandomState(0)
        with tempfile.TemporaryDirectory() as tmp:
            for h, w in [(37, 53), (64, 64), (101, 17), (9, 200)]:
                img = rng.randint(0, 256, (h, w, 3), dtype=np.uint8)
                path = Path(tmp) / f"noise_{w}x{h}.png"
                cv2.imwrite(str(path), img)
                for grid, jitter in [(8, 4), (10, 12)]:
                    with self.subTest(size=f"{w}x{h}", grid=grid, jitter=jitter):
                        self.check(path, grid, jitter)

    def test_the_comparison_can_fail(self):
        """Guard against a vacuous pass: a different jitter must give a different SVG."""
        path = SAMPLES[0]
        with tempfile.TemporaryDirectory() as tmp:
            expected = reference_svg(path, 10, 12, tmp)
        self.assertNotEqual(
            low_poly(load_image(path), grid_size=10, jitter=11), expected
        )


if __name__ == "__main__":
    unittest.main()
