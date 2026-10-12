"""Metamorphic tests (Hypothesis).

A metamorphic test does not know the right output for an image. It changes the input in a way whose effect is
known and checks that the output changes in that way: mirror the scene and the light, and the shading must
mirror; add a constant to every pixel, and the edges must not move. See docs/TESTING.md, "Metamorphic tests".

Two groups:
  ExactRelations      hold to rounding (one colour level) or exactly.
  ToleratedRelations  hold only approximately. Each states its tolerance and why it is needed.

Run:   pip install hypothesis
       python -m unittest tests.test_metamorphic -v
Profiles are the same as in test_properties.py (HYPOTHESIS_PROFILE).
"""
import unittest

import cv2
import numpy as np

try:
    from hypothesis import assume, given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("hypothesis is not installed (pip install hypothesis)")

try:  # run as `unittest discover -s tests` or as `unittest tests.test_metamorphic`
    from test_properties import depth_maps, grids, images, seeds
except ImportError:  # pragma: no cover
    from tests.test_properties import depth_maps, grids, images, seeds

from lowpoly import generate
from lowpoly.core import detect_edges, relief_colors, smooth

# --------------------------------------------------------------------------- tolerances
ROUNDING = 1.0 + 1e-6   # colours are rounded to whole numbers, so equal results can differ by one level
FLIP_RADIUS = 1         # px. Canny breaks ties between equal gradients by scan order, so a mirrored edge may sit one pixel over
FLIP_STRAYS = 0.01      # share of edge pixels (at least 8) that may have no partner within the radius; hysteresis can drop a weak chain
SWAP_LEVELS = 12        # colour levels. Worst seen: 9, on 1,500 random images. The HSV round trip is 8-bit (see test)
SCALE_RATIO = 0.15      # +-15%. Worst seen: 11%, on 1,500 random images. Point count follows the grid, not the content
EDGE_KINDS = ["flat", "split", "noise"]   # not ramp or stripes: their gradients tie over wide areas (see test)

reliefs = st.floats(1, 60)
angles = st.floats(0, 359)


def max_colour_difference(a, b):
    return float(np.abs(a.astype(int) - b.astype(int)).max())


def strays(a, b, radius=FLIP_RADIUS):
    """Number of set pixels of `a` with no set pixel of `b` within `radius` (Chebyshev distance)."""
    kernel = np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)
    near_b = cv2.dilate((b > 0).astype(np.uint8), kernel) > 0
    return int(((a > 0) & ~near_b).sum())


def assert_same_edges_up_to_ties(test, a, b):
    allowed = max(8, int(FLIP_STRAYS * max((a > 0).sum(), (b > 0).sum())))
    test.assertLessEqual(max(strays(a, b), strays(b, a)), allowed)


# --------------------------------------------------------------------------- exact relations
class ExactRelations(unittest.TestCase):
    @given(images(min_side=10, max_side=100), st.data(), grids, seeds, reliefs, angles, st.floats(10, 90))
    def test_mirroring_the_scene_and_the_light_mirrors_the_shading(self, img, data, grid, seed, relief, angle, elevation):
        # Mirror the points and the depth map left to right, and the light from angle a to 360 - a.
        h, w = img.shape[:2]
        d = data.draw(depth_maps(h, w))
        base = generate(img, grid_size=grid, seed=seed)
        lit = relief_colors(base.points, base.simplices, base.colors, d, relief, angle, elevation)
        mirrored_points = base.points.copy()
        mirrored_points[:, 0] = w - 1 - mirrored_points[:, 0]
        lit_mirrored = relief_colors(mirrored_points, base.simplices, base.colors, d[:, ::-1].copy(),
                                     relief, 360 - angle, elevation)
        self.assertLessEqual(max_colour_difference(lit, lit_mirrored), ROUNDING)

    @given(images(min_side=10, max_side=100), st.data(), grids, seeds, reliefs, angles)
    def test_turning_the_light_a_full_circle_changes_nothing(self, img, data, grid, seed, relief, angle):
        d = data.draw(depth_maps(*img.shape[:2]))
        a = generate(img, grid_size=grid, seed=seed, relief=relief, depth=d, light_angle=angle)
        b = generate(img, grid_size=grid, seed=seed, relief=relief, depth=d, light_angle=angle + 360)
        self.assertLessEqual(max_colour_difference(a.colors, b.colors), ROUNDING)

    @given(images(min_side=10, max_side=100), st.data(), grids, seeds, reliefs, st.floats(0.5, 20), st.floats(-5, 5))
    def test_depth_scale_and_offset_do_not_matter(self, img, data, grid, seed, relief, scale, offset):
        # Depth is normalised to 0..1 before use, so d and scale * d + offset must give the same picture.
        d = data.draw(depth_maps(*img.shape[:2]))
        a = generate(img, grid_size=grid, seed=seed, relief=relief, depth=d)
        b = generate(img, grid_size=grid, seed=seed, relief=relief, depth=d * scale + offset)
        self.assertLessEqual(max_colour_difference(a.colors, b.colors), ROUNDING)

    @given(images(min_side=10, max_side=100), st.data(), grids, seeds, reliefs, angles, st.floats(30, 90), st.floats(0, 1))
    def test_shading_strength_is_linear(self, img, data, grid, seed, relief, angle, elevation, strength):
        # colour(s) = flat * (1 + (lit_factor - 1) * s), so it lies on the line from colour(0) to colour(1).
        # Dark images only: the final clip to 255 would bend the line for bright colours.
        img = img // 3
        d = data.draw(depth_maps(*img.shape[:2]))
        run = lambda s: generate(img, grid_size=grid, seed=seed, relief=relief, depth=d, light_angle=angle,
                                 light_elevation=elevation, shading=s).colors.astype(float)
        none, full, part = run(0), run(1), run(strength)
        self.assertLessEqual(np.abs(part - ((1 - strength) * none + strength * full)).max(), ROUNDING)

    @given(images(min_side=10, max_side=100), grids, seeds, st.integers(1, 120))
    def test_brightening_the_photo_keeps_the_mesh(self, img, grid, seed, shift):
        # Adding the same amount to every channel leaves every gradient alone, so the edges, the points and
        # the triangles must be identical. Only the colours may change.
        dark = img // 2
        bright = dark + np.uint8(shift)
        a, b = generate(dark, grid_size=grid, seed=seed), generate(bright, grid_size=grid, seed=seed)
        self.assertTrue(np.array_equal(a.edges, b.edges))
        self.assertTrue(np.array_equal(a.points, b.points))
        self.assertTrue(np.array_equal(a.simplices, b.simplices))

    @given(images(min_side=4, max_side=100))
    def test_transposing_the_photo_transposes_the_edge_map(self, img):
        self.assertTrue(np.array_equal(detect_edges(img.transpose(1, 0, 2).copy()), detect_edges(img).T))


# --------------------------------------------------------------------------- tolerated relations
class ToleratedRelations(unittest.TestCase):
    """Relations that hold only up to a stated error. The tolerance is the point: it records where the exact
    version is false and why."""

    # Why only flat, split and noise photos: on a ramp or a set of one-pixel stripes the gradient has the same
    # size over a wide area, so which pixel counts as "the edge" is decided by scan order alone, and the
    # mirrored run can pick a pixel far away (a whole 90-pixel ramp edge moved in one probe). The relation
    # makes no sense there, so those kinds are left out rather than hidden by a huge tolerance.
    @given(images(min_side=4, max_side=100, kinds=EDGE_KINDS))
    def test_flipping_the_photo_left_to_right_flips_the_edge_map_to_within_a_pixel(self, img):
        # Not exact: for an edge that is two pixels wide, OpenCV keeps the left or the right pixel by scan
        # order, so the mirrored edge can land one column over.
        assert_same_edges_up_to_ties(self, detect_edges(img), detect_edges(img[:, ::-1].copy())[:, ::-1])

    @given(images(min_side=4, max_side=100, kinds=EDGE_KINDS))
    def test_flipping_the_photo_top_to_bottom_flips_the_edge_map_to_within_a_pixel(self, img):
        assert_same_edges_up_to_ties(self, detect_edges(img), detect_edges(img[::-1].copy())[::-1])

    @given(images(min_side=4, max_side=100))
    def test_swapping_blue_and_red_swaps_the_smoothed_image(self, img):
        # Bilateral weights use colour distance, which is symmetric in the channels, and saturation does not
        # depend on which channel is which. Not exact: hue is stored in 8 bits, so the round trip through HSV
        # rounds differently for the two orders.
        swapped = smooth(img[:, :, ::-1].copy())
        self.assertLessEqual(max_colour_difference(smooth(img)[:, :, ::-1], swapped), SWAP_LEVELS)

    @given(images(min_side=60, max_side=120), st.integers(2, 8), st.data(), seeds)
    def test_doubling_the_image_and_the_grid_keeps_the_triangle_count_close(self, img, half_grid, data, seed):
        # One point is placed per grid cell whatever the content, so the count follows the grid. The test
        # keeps to the range where that is true:
        #   even grid sizes: with an odd size the cell centre, grid // 2, does not scale exactly;
        #   jitter up to half the grid: above that, neighbouring cells search the same pixels and snap to the
        #   same edge pixel, which merges points, and how often depends on the content;
        #   at least 60 px per side: in a tiny mesh one merged point is a large share of the triangles.
        grid = 2 * half_grid
        jitter = data.draw(st.integers(0, half_grid))
        big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        before = len(generate(img, grid_size=grid, jitter=jitter, seed=seed).simplices)
        after = len(generate(big, grid_size=2 * grid, jitter=2 * jitter, seed=seed).simplices)
        self.assertGreater(before, 0)
        self.assertLessEqual(abs(after / before - 1), SCALE_RATIO)


if __name__ == "__main__":
    unittest.main()