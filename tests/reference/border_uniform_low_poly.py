"""The original script, kept verbatim as the oracle for tests/test_differential.py.

Only the "Execution" block at the bottom of the author's file was removed. Do not edit the function.
"""

import cv2
import numpy as np
from scipy.spatial import Delaunay


def border_uniform_low_poly(image_path, svg_output_path, grid_size=25, jitter_range=12):
    np.random.seed(42)
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
    h, w = img.shape[:2]
    filtered_img = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
    hsv = cv2.cvtColor(filtered_img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.3, 0, 255)
    filtered_img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    pts = []
    # 1. Internal Grid Distribution
    for y in range(0, h, grid_size):
        for x in range(0, w, grid_size):
            cx, cy = x + grid_size // 2, y + grid_size // 2
            if cx >= w or cy >= h:
                continue
            x1, x2 = max(0, cx - jitter_range), min(w, cx + jitter_range)
            y1, y2 = max(0, cy - jitter_range), min(h, cy + jitter_range)
            window_edges = edges[y1:y2, x1:x2]
            edge_pixels = np.argwhere(window_edges > 0)
            if len(edge_pixels) > 0:
                ey, ex = edge_pixels[np.random.randint(len(edge_pixels))]
                pts.append([x1 + ex, y1 + ey])
            else:
                jx = cx + np.random.randint(-jitter_range, jitter_range + 1)
                jy = cy + np.random.randint(-jitter_range, jitter_range + 1)
                pts.append([np.clip(jx, 0, w - 1), np.clip(jy, 0, h - 1)])
    # 2. Boundary Anchors (Eliminates stretched edge triangles)
    for x in range(0, w, grid_size):
        pts.extend([[x, 0], [x, h - 1]])  # Top and Bottom perimeters
    for y in range(0, h, grid_size):
        pts.extend([[0, y], [w - 1, y]])  # Left and Right perimeters
    pts.extend([[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]])  # 4 Corners
    pts = np.unique(np.array(pts), axis=0)
    tri = Delaunay(pts)
    # 3. Render SVG
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">'
    ]
    for simplex in tri.simplices:
        triangle = pts[simplex]
        cx_tri, cy_tri = np.mean(triangle, axis=0).astype(int)
        cx_tri, cy_tri = np.clip(cx_tri, 0, w - 1), np.clip(cy_tri, 0, h - 1)
        b, g, r = filtered_img[cy_tri, cx_tri]
        pts_str = " ".join([f"{p[0]},{p[1]}" for p in triangle])
        svg_lines.append(
            f'  <polygon points="{pts_str}" fill="rgb({r},{g},{b})" '
            f'stroke="rgb({r},{g},{b})" stroke-width="0.5"/>'
        )
    svg_lines.append("</svg>")
    with open(svg_output_path, "w") as f:
        f.write("\n".join(svg_lines))
