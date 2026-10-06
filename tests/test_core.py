import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import Delaunay

from lowpoly import generate, low_poly, render_file
from lowpoly.cli import main
from lowpoly.core import detect_edges, place_points, triangle_colors

ROOT = Path(__file__).resolve().parent.parent


def sample(w=120, h=90):
    img = np.zeros((h, w, 3), np.uint8)
    img[:, w // 2 :] = 255
    return img


class CoreTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(
            low_poly(sample(), grid_size=15), low_poly(sample(), grid_size=15)
        )

    def test_seed_changes_output(self):
        self.assertNotEqual(
            low_poly(sample(), grid_size=15, seed=1),
            low_poly(sample(), grid_size=15, seed=2),
        )

    def test_svg_is_valid_triangles(self):
        root = ET.fromstring(low_poly(sample(), grid_size=15))
        polys = root.findall("{http://www.w3.org/2000/svg}polygon")
        self.assertGreater(len(polys), 10)
        self.assertTrue(all(len(p.get("points").split()) == 3 for p in polys))

    def test_frame_corners_present(self):
        pts = place_points(np.zeros((90, 120), np.uint8), 15, 5).tolist()
        for c in ([0, 0], [119, 0], [0, 89], [119, 89]):
            self.assertIn(c, pts)

    def test_points_snap_to_edges(self):
        pts = place_points(detect_edges(sample()), 15, 12)
        self.assertTrue(any(abs(x - 60) <= 1 and 0 < y < 89 for x, y in pts))

    def test_triangles_cover_frame(self):
        pts = place_points(detect_edges(sample()), 15, 12)
        t = pts[Delaunay(pts).simplices]
        a, b = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        area = 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum()
        self.assertAlmostEqual(area, 119 * 89, delta=1)

    def test_png_matches_size_and_colours(self):
        res = generate(sample(), grid_size=15)
        png = res.to_png(scale=2)
        self.assertEqual(png.shape, (180, 240, 3))
        self.assertLess(png[90, 20].astype(int).sum(), 60)  # left half black
        self.assertGreater(png[90, 220].astype(int).sum(), 700)  # right half white

    def test_mean_mode_runs(self):
        res = generate(sample(), grid_size=15, color_mode="mean")
        self.assertEqual(res.colors.shape, (len(res.simplices), 3))

    def test_bad_color_mode(self):
        with self.assertRaises(ValueError):
            generate(sample(), color_mode="nope")


class FileTests(unittest.TestCase):
    def test_cli_svg_png_and_folder(self):
        src = ROOT / "samples" / "inputs" / "cat.png"
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            main([str(src), str(d / "a.svg"), "--grid-size", "30"])
            main([str(src), str(d / "a.png"), "--grid-size", "30", "--scale", "2"])
            self.assertTrue((d / "a.svg").read_text().startswith("<svg"))
            self.assertTrue((d / "a.png").stat().st_size > 1000)
            main(
                [
                    str(src.parent),
                    str(d / "batch"),
                    "--grid-size",
                    "40",
                    "--format",
                    "png",
                ]
            )
            self.assertEqual(
                len(list((d / "batch").glob("*.png"))),
                len(list(src.parent.glob("*.[pj]*g"))),
            )

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            render_file("nope.png", "out.svg")

    def test_bad_output_extension(self):
        with self.assertRaises(ValueError):
            render_file(ROOT / "samples" / "inputs" / "cat.png", "out.gif")

    def test_output_folder_is_created_for_png_and_svg(self):
        src = ROOT / "samples" / "inputs" / "cat.png"
        with tempfile.TemporaryDirectory() as d:
            for name in ("new/dir/a.png", "other/dir/a.svg"):
                render_file(src, Path(d) / name, grid_size=40)
                self.assertGreater((Path(d) / name).stat().st_size, 500)

    def test_unrecognised_file_gives_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "photo.jpg"
            fake.write_text("not an image")
            with self.assertRaises(ValueError) as cm:
                render_file(fake, Path(d) / "o.svg")
            self.assertIn("not a recognised image", str(cm.exception))

    def test_empty_file_is_named_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "photo.jpg"
            f.write_bytes(b"")
            with self.assertRaises(ValueError) as cm:
                render_file(f, Path(d) / "o.svg")
            self.assertIn("empty", str(cm.exception))

    def test_heic_by_content_is_reported_with_a_fix(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "photo.jpg"  # named .jpg, content is HEIC
            f.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
            with self.assertRaises(ValueError) as cm:
                render_file(f, Path(d) / "o.svg")
            self.assertIn("HEIC", str(cm.exception))
            self.assertIn("sips", str(cm.exception))

    def test_extension_can_be_wrong_when_content_is_supported(self):
        import shutil

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "really_a_png.jpg"
            shutil.copy(ROOT / "samples" / "inputs" / "cat.png", f)
            render_file(f, Path(d) / "o.svg", grid_size=40)
            self.assertTrue((Path(d) / "o.svg").exists())

    def test_truncated_jpeg_is_reported_as_damaged(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "cut.jpg"
            f.write_bytes(
                (ROOT / "samples" / "inputs" / "rocket.jpg").read_bytes()[:200]
            )
            with self.assertRaises(ValueError) as cm:
                render_file(f, Path(d) / "o.svg")
            self.assertIn("damaged", str(cm.exception))

    @unittest.skipIf(
        hasattr(__import__("os"), "geteuid") and __import__("os").geteuid() == 0,
        "root ignores file permissions",
    )
    def test_permission_denied_message_mentions_macos_fix(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "locked.png"
            f.write_bytes((ROOT / "samples" / "inputs" / "cat.png").read_bytes())
            os.chmod(f, 0)
            try:
                with self.assertRaises(OSError) as cm:
                    render_file(f, Path(d) / "o.svg")
                self.assertIn("Privacy & Security", str(cm.exception))
            finally:
                os.chmod(f, 0o644)

    def test_cli_errors_are_clean_messages(self):
        with tempfile.TemporaryDirectory() as d:
            for args in (
                [str(Path(d) / "missing.png"), str(Path(d) / "o.svg")],
                [str(ROOT / "samples" / "inputs" / "cat.png"), str(Path(d) / "o.gif")],
            ):
                with self.assertRaises(SystemExit) as cm:
                    main(args)
                self.assertIn("lowpoly: error:", str(cm.exception))

    def test_tilde_is_expanded(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Downloads").mkdir()
            import shutil

            shutil.copy(
                ROOT / "samples" / "inputs" / "cat.png",
                Path(d) / "Downloads" / "my photo.png",
            )
            old = os.environ.get("HOME")
            os.environ["HOME"] = d
            try:
                main(
                    [
                        "~/Downloads/my photo.png",
                        "~/Downloads/out.png",
                        "--grid-size",
                        "40",
                    ]
                )
            finally:
                os.environ["HOME"] = old
            self.assertTrue((Path(d) / "Downloads" / "out.png").exists())

    def test_folder_mode_same_stem_does_not_overwrite(self):
        import shutil

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "in").mkdir()
            shutil.copy(ROOT / "samples" / "inputs" / "cat.png", d / "in" / "a.png")
            shutil.copy(ROOT / "samples" / "inputs" / "rocket.jpg", d / "in" / "a.jpg")
            main([str(d / "in"), str(d / "out"), "--grid-size", "40"])
            self.assertEqual(len(list((d / "out").glob("*.svg"))), 2)


class ReliefTests(unittest.TestCase):
    def setUp(self):
        self.img = np.full((90, 120, 3), 128, np.uint8)
        self.ramp = np.tile(
            np.linspace(0, 1, 120, dtype=np.float32), (90, 1)
        )  # rises to the right

    def mean_shade(self, **kw):
        r = generate(self.img, grid_size=15, relief=20, depth=self.ramp, **kw)
        return r.colors.astype(float).mean() / r.flat_colors.astype(float).mean()

    def test_off_by_default_and_identical(self):
        a, b = (
            generate(self.img, grid_size=15),
            generate(self.img, grid_size=15, relief=0),
        )
        self.assertTrue((a.colors == b.colors).all())
        self.assertIsNone(a.depth)

    def test_light_direction_matters(self):
        # a slope rising to the right faces left: lit from the left it brightens, from the right it darkens
        self.assertGreater(self.mean_shade(light_angle=270), 1.05)
        self.assertLess(self.mean_shade(light_angle=90), 0.95)

    def test_flat_depth_keeps_colours(self):
        r = generate(
            self.img, grid_size=15, relief=20, depth=np.zeros((90, 120), np.float32)
        )
        self.assertTrue((r.colors == r.flat_colors).all())

    def test_shading_zero_is_no_effect(self):
        r = generate(self.img, grid_size=15, relief=20, depth=self.ramp, shading=0)
        self.assertTrue((r.colors == r.flat_colors).all())

    def test_brightness_depth_runs_and_changes_colours(self):
        img = cv2.imread(str(ROOT / "samples" / "inputs" / "cat.png"))
        r = generate(img, grid_size=20, relief=13)
        self.assertEqual(r.depth.shape, img.shape[:2])
        self.assertFalse((r.colors == r.flat_colors).all())

    def test_depth_map_file_is_resized(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "depth.png"
            cv2.imwrite(
                str(path), (self.ramp[::3, ::3] * 255).astype(np.uint8)
            )  # smaller than the image
            r = generate(self.img, grid_size=15, relief=20, depth=path, light_angle=270)
            self.assertEqual(r.depth.shape, (90, 120))
            self.assertGreater(
                r.colors.astype(float).mean(), r.flat_colors.astype(float).mean()
            )

    def test_cli_relief_png_and_flag_checks(self):
        src = ROOT / "samples" / "inputs" / "cat.png"
        with tempfile.TemporaryDirectory() as d:
            main(
                [
                    str(src),
                    str(Path(d) / "r.png"),
                    "--grid-size",
                    "30",
                    "--relief",
                    "13",
                ]
            )
            self.assertGreater((Path(d) / "r.png").stat().st_size, 1000)
            with self.assertRaises(SystemExit):
                main(
                    [str(src), str(Path(d) / "x.png"), "--depth-map", "nope.png"]
                )  # needs --relief

    def test_missing_depth_map(self):
        with self.assertRaises(FileNotFoundError):
            generate(self.img, relief=10, depth="missing.png")

    def test_one_pixel_images_are_rejected_cleanly(self):
        for h, w in [(1, 1), (1, 50), (50, 1)]:
            with (
                self.subTest(size=f"{w}x{h}"),
                self.assertRaisesRegex(ValueError, "2x2"),
            ):
                generate(np.zeros((h, w, 3), np.uint8))

    def test_the_smallest_accepted_image_renders(self):
        img = np.zeros((2, 2, 3), np.uint8)
        self.assertEqual(generate(img).to_png().shape, (2, 2, 3))
        self.assertEqual(low_poly(img).count("<polygon"), 2)

    def test_mean_mode_rounds_instead_of_truncating(self):
        img = np.full((4, 4, 3), 101, np.uint8)
        img[0, 0] = 100  # triangle mean is just under 101, so truncation gives 100
        pts = np.array([[0, 0], [3, 0], [0, 3]])
        out = triangle_colors(pts, np.array([[0, 1, 2]]), img, mode="mean")
        self.assertEqual(out.tolist(), [[101, 101, 101]])


if __name__ == "__main__":
    unittest.main()
