"""
Low-level image processing utilities used across multiple pipeline stages.

All functions are stateless and operate purely on NumPy arrays,
making them easily testable and reusable.
"""

import cv2
import numpy as np
from typing import Tuple


def order_rectangle_points(pts: np.ndarray) -> np.ndarray:
    """
    Order four 2-D points into [top-left, top-right, bottom-right, bottom-left].

    This ordering is required by cv2.getPerspectiveTransform to produce
    a correctly-oriented warp.

    Args:
        pts: Array of shape (4, 2) with unordered corner coordinates.

    Returns:
        Array of shape (4, 2) with points in TL, TR, BR, BL order.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left  — smallest x+y
    rect[2] = pts[np.argmax(s)]   # bottom-right — largest x+y
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right — smallest y-x
    rect[3] = pts[np.argmax(diff)]  # bottom-left — largest y-x
    return rect


def perspective_warp(frame: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Apply a perspective (bird's-eye) transform to straighten a detected plate.

    Given four corner points of a potentially rotated/skewed license plate,
    this function computes a homography matrix and returns a rectified,
    axis-aligned crop.

    Args:
        frame: Full BGR video frame.
        pts: Array of shape (4, 2) with the plate's corner coordinates.

    Returns:
        Rectified BGR image of the license plate region.

    Raises:
        ValueError: If fewer than 4 points are provided.
    """
    if len(pts) != 4:
        raise ValueError(f"Expected 4 corner points, got {len(pts)}.")

    rect = order_rectangle_points(pts)
    tl, tr, br, bl = rect

    width = max(
        int(np.linalg.norm(br - bl)),
        int(np.linalg.norm(tr - tl)),
    )
    height = max(
        int(np.linalg.norm(tr - br)),
        int(np.linalg.norm(tl - bl)),
    )

    if width <= 0 or height <= 0:
        raise ValueError("Computed warp dimensions are non-positive.")

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(frame, M, (width, height))


def preprocess_plate(
    roi: np.ndarray,
    upscale_factor: float = 3.0,
    clahe_clip_limit: float = 3.0,
    clahe_tile_grid_size: Tuple[int, int] = (8, 8),
) -> np.ndarray:
    """
    Enhance a license plate crop for OCR.

    Pipeline:
      1. Upscale  — increase pixel density for small plates.
      2. Grayscale — remove colour information irrelevant to OCR.
      3. CLAHE    — equalise local contrast to handle glare and shadows.
      4. Otsu binarisation — produce a clean black-and-white image.

    Args:
        roi: BGR crop of the detected plate.
        upscale_factor: Multiplier applied to both dimensions.
        clahe_clip_limit: Contrast limit for CLAHE.
        clahe_tile_grid_size: Tile size for CLAHE.

    Returns:
        Binary (0/255) single-channel image ready for OCR.
    """
    roi = cv2.resize(roi, None, fx=upscale_factor, fy=upscale_factor,
                     interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit,
                             tileGridSize=clahe_tile_grid_size)
    gray = clahe.apply(gray)
    _, binary = cv2.threshold(gray, 0, 255,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def compute_centroid(moments: dict) -> Tuple[int, int]:
    """
    Compute the (x, y) centroid from pre-calculated image moments.

    Args:
        moments: Dict returned by cv2.moments().

    Returns:
        Integer (x, y) centroid coordinates.

    Raises:
        ZeroDivisionError: If m00 is zero (degenerate contour).
    """
    if moments["m00"] == 0:
        raise ZeroDivisionError("Zero-area contour has no well-defined centroid.")
    cx = int(moments["m10"] / moments["m00"])
    cy = int(moments["m01"] / moments["m00"])
    return cx, cy
