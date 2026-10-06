"""Depth maps and relief lighting."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


# --------------------------------------------------------------------------- depth and relief lighting
def depth_from_brightness(smoothed):
    """Cheap depth guess in 0..1 (1 = near): blurred brightness plus a gentle bulge toward the centre.

    Brightness is not depth (dark pupils sink, pale fur rises), so this is a convincing guess, not a measurement.
    """
    h, w = smoothed.shape[:2]
    gray = cv2.cvtColor(smoothed, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    d = cv2.GaussianBlur(gray, (0, 0), max(1.0, 0.009 * max(h, w)))
    d = (d - d.min()) / max(float(d.max() - d.min()), 1e-6)
    yy, xx = np.mgrid[0:h, 0:w]
    dome = np.exp(
        -(((xx - w / 2) / (w * 0.45)) ** 2 + ((yy - h / 2) / (h * 0.45)) ** 2)
    )
    return (0.65 * d + 0.35 * dome).astype(np.float32)


def load_depth_map(path, size):
    """Read a greyscale image as depth (brighter = closer) and resize it to size=(width, height), scaled to 0..1."""
    d = cv2.imread(str(Path(path).expanduser()), cv2.IMREAD_UNCHANGED)
    if d is None:
        raise FileNotFoundError(f"Depth map not found or unreadable: {path}")
    if d.ndim == 3:
        d = cv2.cvtColor(d[:, :, :3], cv2.COLOR_BGR2GRAY)
    return normalize_depth(d, size)


def normalize_depth(d, size):
    d = cv2.resize(d.astype(np.float32), size, interpolation=cv2.INTER_CUBIC)
    return ((d - d.min()) / max(float(d.max() - d.min()), 1e-6)).astype(np.float32)


def relief_colors(
    pts,
    simplices,
    colors,
    depth,
    relief=13.0,
    light_angle=315.0,
    light_elevation=55.0,
    shading=1.0,
    ambient=0.45,
    max_tilt=60.0,
):
    """Shade each triangle by how it tilts toward a light, using heights taken from `depth` at its corners.

    relief:          height of the full depth range, as a percent of the image's longest side
    light_angle:     compass degrees the light comes from (0 = top, 90 = right, 315 = top left)
    light_elevation: degrees above the image plane (90 = straight on, low = raking light)
    shading:         0 = no effect, 1 = full, above 1 exaggerates
    max_tilt:        steepest facet angle in degrees; limits streaks at sudden depth steps
    """
    h, w = depth.shape
    z = depth[pts[:, 1], pts[:, 0]] * (relief / 100.0) * max(h, w)
    a, b, c = [
        np.c_[pts[simplices[:, k]], z[simplices[:, k]]].astype(np.float64)
        for k in range(3)
    ]
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    n[n[:, 2] < 0] *= -1  # normals face the viewer
    # Long thin triangles that straddle a sudden depth step would tilt almost edge-on and flash black or white.
    # Capping the tilt keeps them from dominating the image.
    sin_max, cos_max = np.sin(np.radians(max_tilt)), np.cos(np.radians(max_tilt))
    xy = np.hypot(n[:, 0], n[:, 1])
    over = xy > sin_max
    scale = np.where(over, sin_max / np.maximum(xy, 1e-12), 1.0)
    n[:, 0] *= scale
    n[:, 1] *= scale
    n[over, 2] = cos_max
    az, el = np.radians(light_angle), np.radians(light_elevation)
    light = np.array(
        [np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)]
    )  # image y points down
    lam = np.clip(n @ light, 0, 1)
    k = (1 - ambient) / light[
        2
    ]  # a flat facet (normal straight at the viewer) keeps its colour
    factor = 1 + (ambient + k * lam - 1) * shading
    return np.clip(np.rint(colors.astype(np.float64) * factor[:, None]), 0, 255).astype(
        np.uint8
    )
