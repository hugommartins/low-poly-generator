"""Low-poly pipeline: smooth -> Canny edges -> edge-snapped points -> Delaunay -> flat colours -> SVG/PNG."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import Delaunay


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
    rs = np.random.RandomState(seed)  # same stream as the original script's np.random.seed(seed)
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
    dome = np.exp(-(((xx - w / 2) / (w * 0.45)) ** 2 + ((yy - h / 2) / (h * 0.45)) ** 2))
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


def relief_colors(pts, simplices, colors, depth, relief=13.0, light_angle=315.0, light_elevation=55.0,
                  shading=1.0, ambient=0.45, max_tilt=60.0):
    """Shade each triangle by how it tilts toward a light, using heights taken from `depth` at its corners.

    relief:          height of the full depth range, as a percent of the image's longest side
    light_angle:     compass degrees the light comes from (0 = top, 90 = right, 315 = top left)
    light_elevation: degrees above the image plane (90 = straight on, low = raking light)
    shading:         0 = no effect, 1 = full, above 1 exaggerates
    max_tilt:        steepest facet angle in degrees; limits streaks at sudden depth steps
    """
    h, w = depth.shape
    z = depth[pts[:, 1], pts[:, 0]] * (relief / 100.0) * max(h, w)
    a, b, c = [np.c_[pts[simplices[:, k]], z[simplices[:, k]]].astype(np.float64) for k in range(3)]
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    n[n[:, 2] < 0] *= -1                       # normals face the viewer
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
    light = np.array([np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)])  # image y points down
    lam = np.clip(n @ light, 0, 1)
    k = (1 - ambient) / light[2]               # a flat facet (normal straight at the viewer) keeps its colour
    factor = 1 + (ambient + k * lam - 1) * shading
    return np.clip(np.rint(colors.astype(np.float64) * factor[:, None]), 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- result object
@dataclass
class Result:
    """Everything the pipeline produced, so each stage can be inspected or drawn."""
    size: tuple          # (width, height)
    smoothed: np.ndarray  # BGR, after bilateral filter + saturation
    edges: np.ndarray     # Canny map
    points: np.ndarray    # (n, 2) x, y
    simplices: np.ndarray  # (m, 3) indices into points
    colors: np.ndarray    # (m, 3) RGB uint8 (lit colours when relief is on)
    depth: object = None  # (h, w) float 0..1, only when relief is on
    flat_colors: object = None  # (m, 3) colours before relief lighting

    def to_svg(self):
        """SVG text: one <polygon> per triangle. The same-colour stroke hides anti-aliasing seams."""
        w, h = self.size
        lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">']
        for tri, (r, g, b) in zip(self.simplices, self.colors):
            points = " ".join(f"{x},{y}" for x, y in self.points[tri])
            fill = f"rgb({r},{g},{b})"
            lines.append(f'  <polygon points="{points}" fill="{fill}" stroke="{fill}" stroke-width="0.5"/>')
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
            canvas = cv2.resize(canvas, (w * scale, h * scale), interpolation=cv2.INTER_AREA)
        return canvas


def generate(img, grid_size=25, jitter=12, saturation=1.3, seed=42, color_mode="centroid",
             canny_low=100, canny_high=200, relief=0.0, depth=None, light_angle=315.0,
             light_elevation=55.0, shading=1.0):
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
        colors = relief_colors(pts, tri.simplices, colors, d, relief, light_angle, light_elevation, shading)
    return Result((w, h), smoothed, edges, pts, tri.simplices, colors, d, flat)


def low_poly(img, **params):
    """BGR image array -> SVG string."""
    return generate(img, **params).to_svg()


# --------------------------------------------------------------------------- files
def sniff_format(data):
    """Name the image format from the file's first bytes (the extension can lie). None if unrecognised."""
    head = data[:16]
    if head[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WebP"
    if head[:2] == b"BM":
        return "BMP"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"
    if head[:4] == b"GIF8":
        return "GIF"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"avif", b"avis"):
            return "AVIF"
        return "HEIC"
    if head[:4] == b"%PDF":
        return "PDF"
    return None


SUPPORTED = ("JPEG", "PNG", "WebP", "BMP", "TIFF", "GIF")


def load_image(path, max_size=None):
    """Read an image file as a BGR array, with errors that say what is actually wrong."""
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    if path.is_dir():
        raise ValueError(f"{path} is a folder, not an image")
    try:
        data = path.read_bytes()
    except PermissionError:
        raise OSError(
            f"Permission denied reading {path}. The file exists but this program may not open it. "
            "On macOS: System Settings > Privacy & Security > Files and Folders (or Full Disk Access), "
            "allow your terminal app to access that folder, then restart the terminal. "
            "Or copy the file somewhere else with Finder and use that path.") from None
    if not data:
        raise ValueError(f"{path} is empty (0 bytes). The download or copy probably failed.")
    img = None
    kind = sniff_format(data)
    if kind in SUPPORTED:  # decode by content; the extension can be wrong
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"{path} looks like a {kind} file but could not be decoded; it may be damaged or incomplete.")
    elif kind:
        hint = (" On macOS: sips -s format jpeg INPUT --out OUTPUT.jpg" if kind in ("HEIC", "AVIF") else "")
        raise ValueError(f"{path} is a {kind} file (judged by its content, whatever its name says), "
                         f"which is not supported. Convert it to JPG or PNG first.{hint}")
    else:
        raise ValueError(f"{path} is not a recognised image file (first bytes: {data[:8].hex(' ')}). "
                         "Supported: JPEG, PNG, WebP, BMP, TIFF, GIF.")
    if max_size and max(img.shape[:2]) > max_size:
        s = max_size / max(img.shape[:2])
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return img


def render_file(src, dst, max_size=None, scale=1, depth_map=None, **params):
    """Read an image file and write .svg or .png (chosen by dst's extension). Returns the Result.

    depth_map: path to a greyscale depth image (brighter = closer). Only matters when relief > 0.
    """
    img = load_image(src, max_size)
    if depth_map:
        params["depth"] = depth_map
    res = generate(img, **params)
    dst = Path(dst).expanduser()
    suffix = dst.suffix.lower()
    if suffix not in (".svg", ".png"):
        raise ValueError(f"output must end in .svg or .png, got {dst.name!r}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".svg":
        dst.write_text(res.to_svg())
    elif not cv2.imwrite(str(dst), res.to_png(scale)):
        raise OSError(f"could not write {dst}")
    return res