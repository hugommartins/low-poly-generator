"""Thin re-export so existing `lowpoly.core` imports keep working."""

from .io import SUPPORTED, load_image, render_file, sniff_format
from .pipeline import (
    Result,
    detect_edges,
    generate,
    low_poly,
    place_points,
    smooth,
    triangle_colors,
)
from .relief import (
    depth_from_brightness,
    load_depth_map,
    normalize_depth,
    relief_colors,
)

__all__ = [
    "SUPPORTED",
    "Result",
    "depth_from_brightness",
    "detect_edges",
    "generate",
    "load_depth_map",
    "load_image",
    "low_poly",
    "normalize_depth",
    "place_points",
    "relief_colors",
    "render_file",
    "smooth",
    "sniff_format",
    "triangle_colors",
]
