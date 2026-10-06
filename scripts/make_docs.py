"""Regenerate every image in docs/images and samples/outputs. Needs: pip install -e ".[docs]"."""

from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
from scipy.spatial import Delaunay

from lowpoly import generate
from lowpoly.core import detect_edges, place_points, smooth, triangle_colors

ROOT = Path(__file__).resolve().parent.parent
IN, OUT, DOC = (
    ROOT / "samples" / "inputs",
    ROOT / "samples" / "outputs",
    ROOT / "docs" / "images",
)
DOC.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
INK, MUTE = "#14212b", "#5d6b76"
plt.rcParams.update(
    {
        "font.size": 11,
        "font.family": "DejaVu Sans",
        "text.color": INK,
        "axes.edgecolor": MUTE,
    }
)


def rgb(bgr):
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def load(name):
    return cv2.imread(str(IN / name))


def panels(items, path, cols=None, cell=3.6, title_size=11):
    """items: list of (title, image, optional subtitle). Saves a clean grid of images."""
    n = len(items)
    cols = cols or n
    rows = -(-n // cols)
    fig, axes = plt.subplots(
        rows, cols, figsize=(cell * cols, cell * rows * 0.86 + 0.5), squeeze=False
    )
    for ax in axes.ravel():
        ax.axis("off")
    for ax, it in zip(axes.ravel(), items):
        title, im = it[0], it[1]
        ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(title, fontsize=title_size, pad=6)
        if len(it) > 2:
            ax.text(
                0.5,
                -0.04,
                it[2],
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=9,
                color=MUTE,
            )
    fig.tight_layout(w_pad=0.6)
    fig.savefig(path, dpi=130, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("wrote", path.relative_to(ROOT))


def wire(shape, pts, simplices, base=None, dim=0.55, color="white", lw=0.6):
    """Image with the mesh drawn over it (dimmed photo underneath)."""
    h, w = shape[:2]
    canvas = (
        np.zeros((h, w, 3), np.uint8)
        if base is None
        else (base * (1 - dim)).astype(np.uint8)
    )
    canvas = np.ascontiguousarray(canvas)
    for t in simplices:
        cv2.polylines(
            canvas,
            [pts[t].astype(np.int32)],
            True,
            (255, 255, 255) if color == "white" else color,
            1,
            cv2.LINE_AA,
        )
    return canvas


def classify(pts, edges):
    h, w = edges.shape
    border = (
        (pts[:, 0] == 0)
        | (pts[:, 1] == 0)
        | (pts[:, 0] == w - 1)
        | (pts[:, 1] == h - 1)
    )
    snapped = ~border & (edges[pts[:, 1], pts[:, 0]] > 0)
    return border, snapped, ~border & ~snapped


def draw_points(img, pts, edges, r=3):
    out = np.ascontiguousarray((img * 0.45).astype(np.uint8))
    border, snapped, free = classify(pts, edges)
    for mask, col in (
        (free, (255, 255, 255)),
        (border, (232, 209, 79)),
        (snapped, (67, 159, 255)),
    ):  # BGR
        for x, y in pts[mask]:
            cv2.circle(out, (int(x), int(y)), r, col, -1, cv2.LINE_AA)
    return out, border.sum(), snapped.sum(), free.sum()


# ---------------------------------------------------------------- figure 1: the whole pipeline
def fig_pipeline():
    img = load("cat.png")
    res = generate(img, grid_size=14, jitter=12)
    pt_img, nb, ns, nf = draw_points(img, res.points, res.edges, r=2)
    mesh = wire(img.shape, res.points, res.simplices, base=img)
    items = [
        ("1. Original", rgb(img), f"{img.shape[1]}x{img.shape[0]} px, BGR array"),
        (
            "2. Smoothed + saturated",
            rgb(res.smoothed),
            "bilateral filter, saturation x1.3",
        ),
        ("3. Canny edges", res.edges, "computed on the original"),
        ("4. Points", rgb(pt_img), f"{ns} on edges, {nf} jittered, {nb} border"),
        ("5. Delaunay mesh", rgb(mesh), f"{len(res.simplices)} triangles"),
        ("6. Coloured", rgb(res.to_png()), "one flat colour per triangle"),
    ]
    panels(items, DOC / "pipeline.png", cols=3)


# ---------------------------------------------------------------- figure 2: bilateral vs gaussian
def fig_bilateral():
    img = load("portrait.png")[40:200, 130:290]

    def big(a):
        return cv2.resize(a, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_NEAREST)

    gauss = cv2.GaussianBlur(img, (9, 9), 0)
    bil = cv2.bilateralFilter(img, 9, 75, 75)
    panels(
        [
            ("Original", rgb(big(img))),
            (
                "Gaussian blur (9x9)",
                rgb(big(gauss)),
                "edges smear with everything else",
            ),
            (
                "Bilateral filter (d=9)",
                rgb(big(bil)),
                "flat areas smooth, edges stay sharp",
            ),
        ],
        DOC / "bilateral.png",
        cell=3.6,
    )


# ---------------------------------------------------------------- figure 3: canny
def fig_canny():
    img = load("cat.png")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    mag = np.clip(np.hypot(gx, gy) / 2, 0, 255).astype(np.uint8)

    def e(lo, hi):
        return cv2.Canny(gray, lo, hi)

    panels(
        [
            ("Gradient strength", mag, "step 1: how fast brightness changes"),
            ("Canny 200 / 400", e(200, 400), "strict: only strong outlines"),
            ("Canny 100 / 200 (default)", e(100, 200), "balanced"),
            ("Canny 40 / 80", e(40, 80), "permissive: fur texture counts too"),
        ],
        DOC / "canny.png",
        cols=4,
        cell=3.2,
        title_size=10,
    )


def fig_hysteresis():
    """1-D illustration of the two Canny thresholds."""
    x = np.arange(60)
    g = np.zeros(60)
    g[[8, 9, 10]] = [90, 150, 80]
    g[[22, 23, 24, 25, 26, 27]] = [70, 120, 230, 190, 140, 110]
    g[[40, 41, 42]] = [60, 95, 70]
    g[[50]] = [60]
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    ax.bar(x, g, color="#9fb3bf", width=0.85)
    for xi in (9, 24, 41):
        pass
    ax.axhline(100, color="#d97b29", lw=1.4)
    ax.axhline(200, color="#1f7a8c", lw=1.4)
    ax.text(59.5, 205, "high = 200", ha="right", color="#1f7a8c", fontsize=10)
    ax.text(59.5, 105, "low = 100", ha="right", color="#d97b29", fontsize=10)
    ax.annotate(
        "kept: above high",
        (24, 230),
        (30, 262),
        arrowprops={"arrowstyle": "->", "color": INK},
        fontsize=10,
    )
    ax.annotate(
        "kept: above low and\nconnected to a strong pixel",
        (26, 140),
        (31, 148),
        fontsize=9,
        color=INK,
        arrowprops={"arrowstyle": "->", "color": INK},
    )
    ax.annotate(
        "dropped: above low but\nnot connected to a strong one",
        (9, 150),
        (0.5, 205),
        fontsize=9,
        arrowprops={"arrowstyle": "->", "color": INK},
    )
    ax.annotate(
        "dropped: below low",
        (50, 62),
        (43, 20),
        fontsize=9,
        arrowprops={"arrowstyle": "->", "color": INK},
    )
    ax.set_ylim(0, 290)
    ax.set_xlabel("pixels along a line across the image")
    ax.set_ylabel("edge strength (after thinning)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(DOC / "hysteresis.png", dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote docs/images/hysteresis.png")


# ---------------------------------------------------------------- figure 4: why snap to edges
def fig_snap():
    img = load("portrait.png")
    sm = smooth(img)
    edges = detect_edges(img)
    g, j = 18, 12
    out = []
    for title, e, sub in (
        ("Points snapped to Canny edges", edges, "triangle sides follow outlines"),
        (
            "Jitter only (edges ignored)",
            np.zeros_like(edges),
            "sides cut across outlines",
        ),
    ):
        pts = place_points(e, g, j)
        tri = Delaunay(pts)
        col = triangle_colors(pts, tri.simplices, sm)
        r = generate(img, grid_size=g)  # for the Result type only
        r.points, r.simplices, r.colors = pts, tri.simplices, col
        out.append((title, rgb(r.to_png(scale=2)[40:400, 140:500]), sub))
    panels(out, DOC / "edge_snapping.png", cell=4.4)


# ---------------------------------------------------------------- figure 5: border anchors
def fig_anchors():
    img = load("coffee.png")
    edges = detect_edges(img)
    items = []
    for title, anchors, sub in (
        ("Without border anchors", False, "mesh stops short, hull edges are skewed"),
        ("With border anchors", True, "triangles tile the whole frame"),
    ):
        pts = place_points(edges, 40, 12, anchors=anchors)
        tri = Delaunay(pts)
        items.append(
            (title, rgb(wire(img.shape, pts, tri.simplices, base=img, dim=0.35)), sub)
        )
    panels(items, DOC / "anchors.png", cell=4.8)


# ---------------------------------------------------------------- figure 6: grid size, jitter
def fig_grid():
    img = load("portrait.png")
    items = []
    for g in (40, 20, 10):
        r = generate(img, grid_size=g)
        items.append(
            (f"grid_size = {g}", rgb(r.to_png()), f"{len(r.simplices)} triangles")
        )
    panels(items, DOC / "grid_size.png", cell=3.6)


def fig_jitter():
    img = load("coffee.png")
    edges = np.zeros(
        img.shape[:2], np.uint8
    )  # flat-area behaviour: no edge snapping, jitter is visible
    items = []
    for j in (0, 6, 16):
        pts = place_points(edges, 40, j)
        tri = Delaunay(pts)
        items.append(
            (
                f"jitter = {j}",
                rgb(wire(img.shape, pts, tri.simplices, base=img, dim=0.55)),
                "perfect grid" if j == 0 else "organic",
            )
        )
    panels(items, DOC / "jitter.png", cell=3.8)


# ---------------------------------------------------------------- figure 7: colour modes
def fig_colors():
    img = load("cat.png")
    y0, y1, x0, x1 = 40, 200, 130, 330
    items = []
    for mode, sub in (
        ("centroid", "1 pixel per triangle: fast, can pick up noise"),
        ("mean", "average of the triangle: smoother"),
    ):
        r = generate(img, grid_size=22, color_mode=mode)
        items.append(
            (
                f'color_mode = "{mode}"',
                rgb(r.to_png(scale=3)[y0 * 3 : y1 * 3, x0 * 3 : x1 * 3]),
                sub,
            )
        )
    panels(items, DOC / "color_modes.png", cell=5.0)


# ---------------------------------------------------------------- figure 8: delaunay rule
def fig_delaunay():
    """Same four points, two triangulations. Only one satisfies the empty-circle rule."""
    P = np.array([[0.0, 0.0], [4.0, 0.0], [2.0, 3.0], [2.0, -0.6]])  # A B C D
    names = "ABCD"

    def circ(i, j, k):
        a, b, c = P[i], P[j], P[k]
        d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
        ux = (
            (a @ a) * (b[1] - c[1]) + (b @ b) * (c[1] - a[1]) + (c @ c) * (a[1] - b[1])
        ) / d
        uy = (
            (a @ a) * (c[0] - b[0]) + (b @ b) * (a[0] - c[0]) + (c @ c) * (b[0] - a[0])
        ) / d
        return np.array([ux, uy]), float(np.hypot(*(a - [ux, uy])))

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.2))
    cases = (
        (
            axes[0],
            [(0, 1, 2), (0, 1, 3)],
            "#d97b29",
            "Not Delaunay\nD lies inside the circle through A, B, C",
        ),
        (
            axes[1],
            [(0, 2, 3), (1, 2, 3)],
            "#1f7a8c",
            "Delaunay\nneither circle contains a fourth point",
        ),
    )
    for ax, tris, col, title in cases:
        for t in tris:
            ax.fill(*P[list(t)].T, alpha=0.16, color=col)
            ax.plot(*P[list(t + (t[0],))].T, color=INK, lw=1.5)
        circles = [circ(*tris[0])] if col == "#d97b29" else [circ(*t) for t in tris]
        for c, r in circles:
            ax.add_patch(Circle(c, r, fill=False, ls="--", lw=1.2, color=col))
        ax.scatter(*P.T, color=INK, zorder=3, s=36)
        if col == "#d97b29":
            ax.scatter(*P[3], color=col, zorder=4, s=70, edgecolor=INK)
        for p, n in zip(P, names):
            ax.annotate(n, p, textcoords="offset points", xytext=(7, 6), fontsize=11)
        ax.set_aspect("equal")
        ax.set_xlim(-1.4, 5.4)
        ax.set_ylim(-2.0, 3.8)
        ax.axis("off")
        ax.set_title(title, fontsize=10.5)
    fig.tight_layout()
    fig.savefig(
        DOC / "delaunay_rule.png",
        dpi=130,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.2,
    )
    plt.close(fig)
    print("wrote docs/images/delaunay_rule.png")


# ---------------------------------------------------------------- relief figures
def fig_relief():
    img = load("cat.png")
    flat = generate(img, grid_size=20)
    lit = generate(img, grid_size=20, relief=13)
    depth = (lit.depth * 255).astype(np.uint8)
    panels(
        [
            ("Flat colours", rgb(flat.to_png(2)), f"{len(flat.simplices)} triangles"),
            ("Depth guess from brightness", depth, "lighter = closer"),
            (
                "Lit by that depth (--relief 13)",
                rgb(lit.to_png(2)),
                "light from the top left",
            ),
        ],
        DOC / "relief_cat.png",
        cell=3.9,
    )


def fig_sphere():
    """A known depth map (a dome) shows what the lighting does when the depth is right."""
    n = 300
    yy, xx = np.mgrid[0:n, 0:n]
    rr = np.hypot(xx - n / 2, yy - n / 2) / (n * 0.38)
    dome = np.sqrt(np.clip(1 - rr**2, 0, 1)).astype(np.float32)  # hemisphere height
    img = np.zeros((n, n, 3), np.uint8)
    img[:] = (120, 105, 90)
    img[rr < 1] = (70, 140, 230)
    items = [("Flat colours", rgb(generate(img, grid_size=14).to_png(2)), "no depth")]
    for ang, name in (
        (315, "light from the top left"),
        (135, "light from the bottom right"),
    ):
        r = generate(img, grid_size=14, relief=30, depth=dome, light_angle=ang)
        items.append((f"Known dome depth, {ang} deg", rgb(r.to_png(2)), name))
    panels(items, DOC / "relief_dome.png", cell=3.6)


def fig_light():
    img = load("cat.png")
    items = []
    for ang, name in (
        (315, "top left"),
        (45, "top right"),
        (135, "bottom right"),
        (225, "bottom left"),
    ):
        items.append(
            (
                f"--light-angle {ang}",
                rgb(generate(img, grid_size=20, relief=13, light_angle=ang).to_png(2)),
                name,
            )
        )
    panels(items, DOC / "relief_light.png", cols=4, cell=3.2, title_size=10)


# ---------------------------------------------------------------- samples
def samples():
    for f in sorted(IN.glob("*")):
        if f.suffix.lower() not in (".png", ".jpg"):
            continue
        img = cv2.imread(str(f))
        for label, g in (("sparse", 24), ("dense", 9)):
            r = generate(img, grid_size=g)
            (OUT / f"{f.stem}_{label}.svg").write_text(r.to_svg())
            cv2.imwrite(str(OUT / f"{f.stem}_{label}.png"), r.to_png())
        rl = generate(img, grid_size=20, relief=13)
        cv2.imwrite(str(OUT / f"{f.stem}_relief.png"), rl.to_png())
        (OUT / f"{f.stem}_relief.svg").write_text(rl.to_svg())
        r = {k: cv2.imread(str(OUT / f"{f.stem}_{k}.png")) for k in ("sparse", "dense")}
        panels(
            [
                ("Original", rgb(img)),
                ("Sparse  (--grid-size 24)", rgb(r["sparse"])),
                ("Dense  (--grid-size 9)", rgb(r["dense"])),
            ],
            DOC / f"sample_{f.stem}.png",
            cell=3.9,
        )


if __name__ == "__main__":
    for fn in (
        fig_pipeline,
        fig_bilateral,
        fig_canny,
        fig_hysteresis,
        fig_snap,
        fig_anchors,
        fig_grid,
        fig_jitter,
        fig_colors,
        fig_delaunay,
        fig_relief,
        fig_sphere,
        fig_light,
        samples,
    ):
        fn()
