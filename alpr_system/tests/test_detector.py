"""
Unit tests for the PlateDetector class.

Because detection quality depends on real images, these tests focus on
the *contract* of the detector: correct return types, edge cases (blank
frames, tiny contours), and that configuration is respected.

For real detection accuracy, use integration tests with sample video frames.

Run with:
    python -m pytest tests/test_detector.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
import cv2

from core.detector import PlateDetector, DetectedRegion
from config.settings import DetectorConfig


@pytest.fixture
def detector() -> PlateDetector:
    return PlateDetector()


class TestReturnType:
    def test_returns_list(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        assert isinstance(result, list)

    def test_each_item_is_detected_region(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        for item in result:
            assert isinstance(item, DetectedRegion)


class TestBlankFrame:
    def test_blank_frame_returns_empty(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        assert result == []


class TestMinAreaFiltering:
    def test_small_rectangle_rejected(self):
        """A quadrilateral with area < min_contour_area must be ignored."""
        cfg = DetectorConfig(min_contour_area=5000)
        detector = PlateDetector(cfg)

        # Synthesise a frame with a visible small white rectangle
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (100, 100), (120, 120), (255, 255, 255), -1)

        result = detector.detect(frame)
        # The small rectangle should not pass the area filter
        assert all(r.area >= cfg.min_contour_area for r in result)


class TestDetectedRegionFields:
    def test_detected_region_has_required_fields(self):
        dummy_contour = np.array([[[0, 0]], [[10, 0]], [[10, 5]], [[0, 5]]])
        region = DetectedRegion(
            contour=dummy_contour,
            area=50.0,
            centroid=(5, 2),
        )
        assert region.contour is not None
        assert isinstance(region.area, float)
        assert len(region.centroid) == 2


class TestSafeCentroid:
    def test_degenerate_contour_returns_none(self):
        """Zero-area contour should return None from _safe_centroid."""
        contour = np.array([[[0, 0]], [[0, 0]], [[0, 0]], [[0, 0]]])
        result = PlateDetector._safe_centroid(contour)
        assert result is None

    def test_valid_contour_returns_tuple(self):
        contour = np.array([[[0, 0]], [[100, 0]], [[100, 50]], [[0, 50]]])
        result = PlateDetector._safe_centroid(contour)
        assert result is not None
        assert len(result) == 2
