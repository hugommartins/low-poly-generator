"""Low-poly pipeline: smooth -> Canny edges -> edge-snapped points -> Delaunay -> flat colours -> SVG/PNG."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from scipy.spatial import Delaunay

from .relief import (
    depth_from_brightness,
    load_depth_map,
    normalize_depth,
    relief_colors,
)


# --------------------------------------------------------------------------- stages
def smooth(img, saturation=1.3):
    """Edge-preserving bilateral filter, then scale HSV saturation (img is BGR uint8)."""
    out = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def detect_edges(img, low=100, high=200):
    """Canny edge map (255 on edges, 0 elsewhere), computed on the original image."""
    return cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), low, high)


def place_points(edges, grid_size=25, jitter=12, seed=42, anchors=True):
    """One point per grid cell, plus (optionally) anchors along the image border.

    Each cell looks for edge pixels within +/- `jitter` pixels of its centre. If any exist, one is
    picked at random and used as the point (so triangle corners sit on contours). Otherwise the point
    is the cell centre shifted by a random offset in [-jitter, jitter].
    """
    rs = np.random.RandomState(
        seed
    )  # same stream as the original script's np.random.seed(seed)
    h, w = edges.shape
    pts = []
    for y in range(0, h, grid_size):
        for x in range(0, w, grid_size):
            cx, cy = x + grid_size // 2, y + grid_size // 2
            if cx >= w or cy >= h:
                continue
            x1, x2 = max(0, cx - jitter), min(w, cx + jitter)
            y1, y2 = max(0, cy - jitter), min(h, cy + jitter)
            hits = np.argwhere(edges[y1:y2, x1:x2] > 0)
            if len(hits):
                ey, ex = hits[rs.randint(len(hits))]
                pts.append([x1 + ex, y1 + ey])
            else:
                jx = cx + rs.randint(-jitter, jitter + 1)
                jy = cy + rs.randint(-jitter, jitter + 1)
                pts.append([np.clip(jx, 0, w - 1), np.clip(jy, 0, h - 1)])
    if anchors:
        for x in range(0, w, grid_size):
            pts.extend([[x, 0], [x, h - 1]])
        for y in range(0, h, grid_size):
            pts.extend([[0, y], [w - 1, y]])
        pts.extend([[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]])
    return np.unique(np.array(pts), axis=0)


def triangle_colors(pts, simplices, img, mode="centroid"):
    """RGB colour per triangle, sampled from `img` (BGR).

    "centroid": the single pixel at the triangle's centre (original behaviour, fast).
    "mean":     the average of all pixels inside the triangle (less noisy, slower).
    """
    h, w = img.shape[:2]
    tris = pts[simplices]
    if mode == "centroid":
        c = np.clip(tris.mean(axis=1).astype(int), [0, 0], [w - 1, h - 1])
        return img[c[:, 1], c[:, 0]][:, ::-1]
    if mode != "mean":
        raise ValueError(f"unknown colour mode {mode!r}")
    out = np.zeros((len(tris), 3), np.uint8)
    for i, t in enumerate(tris):
        x0, y0 = t.min(axis=0)
        x1, y1 = t.max(axis=0) + 1
        mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillConvexPoly(mask, (t - [x0, y0]).astype(np.int32), 255)
        out[i] = np.array(cv2.mean(img[y0:y1, x0:x1], mask=mask)[:3])[::-1]
    return out


# --------------------------------------------------------------------------- result object
@dataclass
class Result:
    """Everything the pipeline produced, so each stage can be inspected or drawn."""

    size: tuple  # (width, height)
    smoothed: np.ndarray  # BGR, after bilateral filter + saturation
    edges: np.ndarray  # Canny map
    points: np.ndarray  # (n, 2) x, y
    simplices: np.ndarray  # (m, 3) indices into points
    colors: np.ndarray  # (m, 3) RGB uint8 (lit colours when relief is on)
    depth: object = None  # (h, w) float 0..1, only when relief is on
    flat_colors: object = None  # (m, 3) colours before relief lighting

    def to_svg(self):
        """SVG text: one <polygon> per triangle. The same-colour stroke hides anti-aliasing seams."""
        w, h = self.size
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">'
        ]
        for tri, (r, g, b) in zip(self.simplices, self.colors):
            points = " ".join(f"{x},{y}" for x, y in self.points[tri])
            fill = f"rgb({r},{g},{b})"
            lines.append(
                f'  <polygon points="{points}" fill="{fill}" stroke="{fill}" stroke-width="0.5"/>'
            )
        lines.append("</svg>")
        return "\n".join(lines)

    def to_png(self, scale=1, supersample=2):
        """Rasterise to a BGR array (no SVG library needed). Drawn at scale*supersample, then averaged down."""
        w, h = self.size
        k = scale * supersample
        canvas = np.zeros((h * k, w * k, 3), np.uint8)
        for tri, (r, g, b) in zip(self.simplices, self.colors):
            poly = np.round(self.points[tri] * k).astype(np.int32)
            cv2.fillConvexPoly(canvas, poly, (int(b), int(g), int(r)))
        if supersample > 1:
            canvas = cv2.resize(
                canvas, (w * scale, h * scale), interpolation=cv2.INTER_AREA
            )
        return canvas


def generate(
    img,
    grid_size=25,
    jitter=12,
    saturation=1.3,
    seed=42,
    color_mode="centroid",
    canny_low=100,
    canny_high=200,
    relief=0.0,
    depth=None,
    light_angle=315.0,
    light_elevation=55.0,
    shading=1.0,
):
    """Run the whole pipeline on a BGR image array and return a Result.

    relief > 0 turns on the 3D illusion (see relief_colors). `depth` is where heights come from:
    None (brightness guess), a path to a greyscale depth image, or an (h, w) array. Brighter = closer.
    """
    smoothed = smooth(img, saturation)
    edges = detect_edges(img, canny_low, canny_high)
    pts = place_points(edges, grid_size, jitter, seed)
    tri = Delaunay(pts)
    colors = triangle_colors(pts, tri.simplices, smoothed, color_mode)
    h, w = img.shape[:2]
    flat, d = None, None
    if relief and relief > 0:
        if depth is None:
            d = depth_from_brightness(smoothed)
        elif isinstance(depth, (str, bytes)) or hasattr(depth, "__fspath__"):
            d = load_depth_map(depth, (w, h))
        else:
            d = normalize_depth(np.asarray(depth), (w, h))
        flat = colors
        colors = relief_colors(
            pts, tri.simplices, colors, d, relief, light_angle, light_elevation, shading
        )
    return Result((w, h), smoothed, edges, pts, tri.simplices, colors, d, flat)


def low_poly(img, **params):
    """BGR image array -> SVG string."""
    return generate(img, **params).to_svg()
