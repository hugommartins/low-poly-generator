"""Image file input and output: format sniffing, loading, and writing .svg/.png."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .pipeline import generate


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
            "Or copy the file somewhere else with Finder and use that path."
        ) from None
    if not data:
        raise ValueError(
            f"{path} is empty (0 bytes). The download or copy probably failed."
        )
    img = None
    kind = sniff_format(data)
    if kind in SUPPORTED:  # decode by content; the extension can be wrong
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(
                f"{path} looks like a {kind} file but could not be decoded; it may be damaged or incomplete."
            )
    elif kind:
        hint = (
            " On macOS: sips -s format jpeg INPUT --out OUTPUT.jpg"
            if kind in ("HEIC", "AVIF")
            else ""
        )
        raise ValueError(
            f"{path} is a {kind} file (judged by its content, whatever its name says), "
            f"which is not supported. Convert it to JPG or PNG first.{hint}"
        )
    else:
        raise ValueError(
            f"{path} is not a recognised image file (first bytes: {data[:8].hex(' ')}). "
            "Supported: JPEG, PNG, WebP, BMP, TIFF, GIF."
        )
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
