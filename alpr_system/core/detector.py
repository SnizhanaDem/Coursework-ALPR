"""
License plate region detector based on edge detection and contour analysis.

Responsibility: Given a raw video frame, return a list of candidate
plate regions as four-point polygons. This module does NOT perform OCR
or any text-level processing.
"""

from dataclasses import dataclass
from typing import List, Optional

import cv2
import imutils
import numpy as np

from config.settings import DetectorConfig, DEFAULT_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DetectedRegion:
    """
    A single candidate license-plate region found in one video frame.

    Attributes:
        contour: Array of shape (4, 1, 2) — four corner points.
        area: Contour area in pixels (pre-filter: must exceed min_contour_area).
        centroid: (cx, cy) pixel coordinates of the contour centroid.
    """
    contour: np.ndarray
    area: float
    centroid: tuple


class PlateDetector:
    """
    Detects candidate license-plate regions in BGR frames using the
    Canny edge → contour → quadrilateral filter pipeline.

    The detector is intentionally permissive: it returns any quadrilateral
    that is large enough to be a plate. False-positive suppression is
    delegated to downstream stages (OCR + validation).

    Args:
        config: Detector hyperparameters. Defaults to system defaults.
    """

    def __init__(self, config: DetectorConfig = DEFAULT_CONFIG.detector):
        self._cfg = config
        logger.debug("PlateDetector initialised with config: %s", config)

    def detect(self, frame: np.ndarray) -> List[DetectedRegion]:
        """
        Find candidate plate regions in a single video frame.

        Args:
            frame: BGR image as a NumPy array.

        Returns:
            List of DetectedRegion objects sorted by area (largest first).
            May be empty if no suitable quadrilaterals are found.
        """
        edge_map = self._build_edge_map(frame)
        contours = self._find_contours(edge_map)
        regions = self._filter_quadrilaterals(contours)
        logger.debug("Detected %d candidate region(s) in frame.", len(regions))
        return regions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_edge_map(self, frame: np.ndarray) -> np.ndarray:
        """
        Convert a colour frame to a Canny edge map.

        A bilateral filter is applied first to suppress noise while
        preserving the sharp edges of licence-plate characters.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        smoothed = cv2.bilateralFilter(
            gray,
            self._cfg.bilateral_diameter,
            self._cfg.bilateral_sigma_color,
            self._cfg.bilateral_sigma_space,
        )
        return cv2.Canny(
            smoothed,
            self._cfg.canny_low_threshold,
            self._cfg.canny_high_threshold,
        )

    def _find_contours(self, edge_map: np.ndarray) -> list:
        """
        Extract and sort the N largest contours from the edge map.
        """
        raw = cv2.findContours(
            edge_map.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = imutils.grab_contours(raw)
        return sorted(contours, key=cv2.contourArea, reverse=True)[
            : self._cfg.top_contours_count
        ]

    def _filter_quadrilaterals(self, contours: list) -> List[DetectedRegion]:
        """
        Keep only contours that approximate to exactly four vertices
        and satisfy the minimum area threshold.
        """
        regions: List[DetectedRegion] = []
        for contour in contours:
            approx = cv2.approxPolyDP(
                contour, self._cfg.contour_approximation_epsilon, True
            )
            area = cv2.contourArea(contour)

            if len(approx) != self._cfg.required_polygon_vertices:
                continue
            if area < self._cfg.min_contour_area:
                continue

            centroid = self._safe_centroid(approx)
            if centroid is None:
                continue

            regions.append(DetectedRegion(contour=approx, area=area, centroid=centroid))

        return regions

    @staticmethod
    def _safe_centroid(approx: np.ndarray) -> Optional[tuple]:
        """
        Compute the centroid of a polygon, returning None for degenerate cases.
        """
        M = cv2.moments(approx)
        if M["m00"] == 0:
            return None
        return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
