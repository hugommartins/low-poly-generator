"""Property-based tests (Hypothesis).

Each test states a rule that must hold for every input, and Hypothesis tries to break it with generated
images and settings. A failing case is shrunk to the smallest input that still fails.

Run:   pip install hypothesis
       python -m unittest tests.test_properties -v
Profiles (set HYPOTHESIS_PROFILE): "dev" 200 examples (default), "ci" 100 examples and reproducible runs.
"""

import os
import unittest
import xml.etree.ElementTree as ET

import cv2
import numpy as np
from scipy.spatial import Delaunay

try:
    from hypothesis import HealthCheck, assume, given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("hypothesis is not installed (pip install hypothesis)")

from lowpoly import generate
from lowpoly.core import detect_edges, place_points

settings.register_profile(
    "dev", max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

SVG = "{http://www.w3.org/2000/svg}"
KINDS = [
    "flat",
    "split",
    "ramp",
    "stripes",
    "noise",
]  # simplest first, so failures shrink toward "flat"


# --------------------------------------------------------------------------- generators
def make_image(h, w, kind, value, seed):
    if kind == "flat":
        return np.full((h, w, 3), value, np.uint8)
    if kind == "split":
        img = np.zeros((h, w, 3), np.uint8)
        img[:, w // 2 :] = 255
        return img
    if kind == "ramp":
        return np.tile(np.linspace(0, 255, w, dtype=np.uint8)[None, :, None], (h, 1, 3))
    if kind == "stripes":
        img = np.zeros((h, w, 3), np.uint8)
        img[:, :: max(2, w // 7)] = 255
        return img
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)


@st.composite
def images(draw, min_side=2, max_side=120, kinds=KINDS):
    h = draw(st.integers(min_side, max_side))
    w = draw(st.integers(min_side, max_side))
    return make_image(
        h,
        w,
        draw(st.sampled_from(kinds)),
        draw(st.integers(0, 255)),
        draw(st.integers(0, 2**32 - 1)),
    )


grids = st.integers(3, 60)
jitters = st.integers(0, 30)
seeds = st.integers(0, 10_000)


def mesh(img, grid, jitter, seed):
    pts = place_points(detect_edges(img), grid, jitter, seed)
    return pts, Delaunay(pts)


def triangle_areas(pts, simplices):
    t = pts[simplices].astype(float)
    a, b = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    return 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])


# --------------------------------------------------------------------------- point placement
class PlacePointsProperties(unittest.TestCase):
    @given(images(), grids, jitters, seeds)
    def test_points_lie_inside_the_frame(self, img, grid, jitter, seed):
        h, w = img.shape[:2]
        pts = place_points(detect_edges(img), grid, jitter, seed)
        self.assertTrue(
            (
                (pts[:, 0] >= 0)
                & (pts[:, 0] <= w - 1)
                & (pts[:, 1] >= 0)
                & (pts[:, 1] <= h - 1)
            ).all()
        )

    @given(images(), grids, jitters, seeds)
    def test_points_are_unique_and_sorted(self, img, grid, jitter, seed):
        pts = place_points(detect_edges(img), grid, jitter, seed)
        self.assertTrue((pts == np.unique(pts, axis=0)).all())

    @given(images(), grids, jitters, seeds)
    def test_the_four_corners_are_always_points(self, img, grid, jitter, seed):
        h, w = img.shape[:2]
        found = {
            tuple(p)
            for p in place_points(detect_edges(img), grid, jitter, seed).tolist()
        }
        self.assertTrue({(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)} <= found)

    @given(images(), grids, jitters, seeds)
    def test_same_inputs_give_the_same_points(self, img, grid, jitter, seed):
        edges = detect_edges(img)
        self.assertTrue(
            (
                place_points(edges, grid, jitter, seed)
                == place_points(edges, grid, jitter, seed)
            ).all()
        )

    @given(images(), grids, jitters, seeds)
    def test_every_free_point_is_within_jitter_of_a_cell_centre(
        self, img, grid, jitter, seed
    ):
        # Without anchors, each point comes from one cell: an edge pixel or a shifted centre, both within `jitter`.
        h, w = img.shape[:2]
        pts = place_points(detect_edges(img), grid, jitter, seed, anchors=False)
        assume(
            pts.ndim == 2 and len(pts) > 0
        )  # with no anchors and a tiny image there can be no points at all
        cx = np.arange(grid // 2, w, grid)  # centres that exist (cx < w)
        cy = np.arange(grid // 2, h, grid)
        near_x = np.abs(pts[:, 0][:, None] - cx[None, :]).min(axis=1) <= jitter
        near_y = np.abs(pts[:, 1][:, None] - cy[None, :]).min(axis=1) <= jitter
        self.assertTrue(near_x.all() and near_y.all())

    @given(images(), grids, jitters, seeds)
    def test_no_more_points_than_cells_plus_anchors(self, img, grid, jitter, seed):
        h, w = img.shape[:2]
        cells = -(-w // grid) * -(-h // grid)
        anchors = 2 * (-(-w // grid)) + 2 * (-(-h // grid)) + 4
        self.assertLessEqual(
            len(place_points(detect_edges(img), grid, jitter, seed)), cells + anchors
        )


# --------------------------------------------------------------------------- triangulation of those points
class TriangulationProperties(unittest.TestCase):
    @given(images(), grids, jitters, seeds)
    def test_triangles_tile_the_frame_exactly(self, img, grid, jitter, seed):
        h, w = img.shape[:2]
        pts, tri = mesh(img, grid, jitter, seed)
        self.assertAlmostEqual(
            triangle_areas(pts, tri.simplices).sum(), (w - 1) * (h - 1), delta=1e-6
        )

    @given(images(), grids, jitters, seeds)
    def test_no_zero_area_triangles(self, img, grid, jitter, seed):
        pts, tri = mesh(img, grid, jitter, seed)
        self.assertTrue((triangle_areas(pts, tri.simplices) > 0).all())

    @given(images(), grids, jitters, seeds)
    def test_every_point_is_used(self, img, grid, jitter, seed):
        pts, tri = mesh(img, grid, jitter, seed)
        self.assertEqual(len(tri.coplanar), 0)
        self.assertEqual(len(np.unique(tri.simplices)), len(pts))

    @given(images(), grids, jitters, seeds)
    def test_triangle_count_follows_eulers_formula(self, img, grid, jitter, seed):
        # A triangulation of n points with b of them on the boundary has 2n - 2 - b triangles.
        h, w = img.shape[:2]
        pts, tri = mesh(img, grid, jitter, seed)
        border = (
            (pts[:, 0] == 0)
            | (pts[:, 0] == w - 1)
            | (pts[:, 1] == 0)
            | (pts[:, 1] == h - 1)
        ).sum()
        self.assertEqual(len(tri.simplices), 2 * len(pts) - 2 - border)

    @given(images(max_side=80), st.integers(8, 60), jitters, seeds)
    def test_no_point_inside_any_circumcircle(self, img, grid, jitter, seed):
        # The definition of a Delaunay triangulation.
        pts, tri = mesh(img, grid, jitter, seed)
        assume(len(pts) <= 150)
        P = pts.astype(float)
        for s in tri.simplices:
            a, b, c = P[s]
            d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
            if abs(d) < 1e-9:
                continue
            ux = (
                (a @ a) * (b[1] - c[1])
                + (b @ b) * (c[1] - a[1])
                + (c @ c) * (a[1] - b[1])
            ) / d
            uy = (
                (a @ a) * (c[0] - b[0])
                + (b @ b) * (a[0] - c[0])
                + (c @ c) * (b[0] - a[0])
            ) / d
            r2 = (a[0] - ux) ** 2 + (a[1] - uy) ** 2
            inside = ((P[:, 0] - ux) ** 2 + (P[:, 1] - uy) ** 2) < r2 - 1e-6 * max(
                1.0, r2
            )
            inside[s] = False
            self.assertFalse(inside.any())


# --------------------------------------------------------------------------- colours and SVG
class OutputProperties(unittest.TestCase):
    @given(images(), grids, jitters, seeds, st.sampled_from(["centroid", "mean"]))
    def test_one_rgb_colour_per_triangle(self, img, grid, jitter, seed, mode):
        r = generate(img, grid_size=grid, jitter=jitter, seed=seed, color_mode=mode)
        self.assertEqual(r.colors.shape, (len(r.simplices), 3))
        self.assertEqual(r.colors.dtype, np.uint8)

    @given(images(kinds=["flat"]), grids, jitters, seeds)
    def test_a_flat_image_gives_triangles_of_that_one_colour(
        self, img, grid, jitter, seed
    ):
        r = generate(img, grid_size=grid, jitter=jitter, seed=seed)
        self.assertTrue((r.colors == r.smoothed[0, 0][::-1]).all())

    @given(images(kinds=["flat"]), grids, jitters, seeds)
    def test_a_flat_image_gives_triangles_of_that_one_colour_in_mean_mode(
        self, img, grid, jitter, seed
    ):
        r = generate(img, grid_size=grid, jitter=jitter, seed=seed, color_mode="mean")
        self.assertTrue((r.colors == r.smoothed[0, 0][::-1]).all())

    @given(images(), grids, jitters, seeds)
    def test_svg_has_one_polygon_per_triangle_inside_the_frame(
        self, img, grid, jitter, seed
    ):
        h, w = img.shape[:2]
        r = generate(img, grid_size=grid, jitter=jitter, seed=seed)
        root = ET.fromstring(r.to_svg())
        self.assertEqual(root.get("viewBox"), f"0 0 {w - 1} {h - 1}")
        polys = root.findall(SVG + "polygon")
        self.assertEqual(len(polys), len(r.simplices))
        for p in polys:
            self.assertEqual(p.get("fill"), p.get("stroke"))
            for xy in p.get("points").split():
                x, y = map(float, xy.split(","))
                self.assertTrue(0 <= x <= w - 1 and 0 <= y <= h - 1)

    @given(images(), grids, jitters, seeds, st.integers(1, 3))
    def test_png_has_the_requested_size(self, img, grid, jitter, seed, scale):
        h, w = img.shape[:2]
        self.assertEqual(
            generate(img, grid_size=grid, jitter=jitter, seed=seed)
            .to_png(scale=scale)
            .shape,
            (h * scale, w * scale, 3),
        )

    @given(images(kinds=["flat"], min_side=4), grids, jitters, seeds)
    def test_a_flat_image_gives_a_flat_png(self, img, grid, jitter, seed):
        png = generate(img, grid_size=grid, jitter=jitter, seed=seed).to_png()
        self.assertTrue((png == png[0, 0]).all())

    @given(st.integers(1, 60), st.sampled_from(["row", "column"]), grids)
    def test_one_pixel_images_are_rejected_cleanly_or_rendered(self, n, shape, grid):
        img = np.zeros((1, n, 3) if shape == "row" else (n, 1, 3), np.uint8)
        try:
            generate(img, grid_size=grid)
        except ValueError:
            pass  # a clear, catchable error is acceptable; a QhullError is not


# --------------------------------------------------------------------------- relief lighting
@st.composite
def depth_maps(draw, h, w):
    d = (
        np.random.default_rng(draw(st.integers(0, 2**32 - 1)))
        .random((h, w))
        .astype(np.float32)
    )
    d = cv2.GaussianBlur(d, (0, 0), draw(st.floats(0.5, 6.0)))
    assume(float(d.max() - d.min()) > 1e-4)
    return ((d - d.min()) / (d.max() - d.min())).astype(
        np.float32
    )  # full 0..1 range, so 1 - d is also normalised


class ReliefProperties(unittest.TestCase):
    @given(
        images(min_side=10, max_side=100),
        st.data(),
        grids,
        seeds,
        st.floats(1, 60),
        st.floats(0, 359),
    )
    def test_zero_shading_changes_nothing(self, img, data, grid, seed, relief, angle):
        d = data.draw(depth_maps(*img.shape[:2]))
        r = generate(
            img,
            grid_size=grid,
            seed=seed,
            relief=relief,
            depth=d,
            light_angle=angle,
            shading=0,
        )
        self.assertTrue((r.colors == r.flat_colors).all())

    @given(
        images(min_side=10, max_side=100),
        st.data(),
        grids,
        seeds,
        st.floats(1, 60),
        st.floats(0, 359),
        st.floats(10, 90),
    )
    def test_lit_colours_stay_within_the_lighting_bounds(
        self, img, data, grid, seed, relief, angle, elevation
    ):
        # factor = ambient + k * lambert, with lambert in [0, 1] and k = (1 - ambient) / sin(elevation)
        d = data.draw(depth_maps(*img.shape[:2]))
        r = generate(
            img,
            grid_size=grid,
            seed=seed,
            relief=relief,
            depth=d,
            light_angle=angle,
            light_elevation=elevation,
        )
        ambient, top = 0.45, 0.45 + 0.55 / np.sin(np.radians(elevation))
        flat = r.flat_colors.astype(float)
        self.assertTrue((r.colors.astype(float) >= np.rint(flat * ambient) - 1).all())
        self.assertTrue(
            (r.colors.astype(float) <= np.minimum(255, np.rint(flat * top) + 1)).all()
        )

    @given(
        images(min_side=10, max_side=100),
        st.data(),
        grids,
        seeds,
        st.floats(1, 60),
        st.floats(0, 359),
    )
    def test_inverting_depth_and_turning_the_light_around_gives_the_same_shading(
        self, img, data, grid, seed, relief, angle
    ):
        # Flipping every height flips every slope; turning the light 180 degrees flips it back.
        d = data.draw(depth_maps(*img.shape[:2]))
        a = generate(
            img, grid_size=grid, seed=seed, relief=relief, depth=d, light_angle=angle
        )
        b = generate(
            img,
            grid_size=grid,
            seed=seed,
            relief=relief,
            depth=1 - d,
            light_angle=(angle + 180) % 360,
        )
        self.assertLessEqual(
            np.abs(a.colors.astype(int) - b.colors.astype(int)).max(), 1
        )


if __name__ == "__main__":
    unittest.main()
