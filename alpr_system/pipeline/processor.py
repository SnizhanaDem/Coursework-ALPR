"""
ALPR processing pipeline — the system's orchestration layer.

This module ties together all specialist components and defines
the per-frame processing loop. It contains *no* business logic of
its own: every non-trivial operation is delegated to a dedicated class.

Pipeline (per frame)
--------------------
1. Detector  → find candidate plate regions as 4-corner polygons.
2. Tracker   → assign a stable car_id to each centroid (tick first).
3. Image utils → perspective-warp and preprocess each region.
4. Recognizer → extract raw text from the preprocessed image.
5. Validator  → correct and verify each raw string.
6. History    → maintain a rolling vote window; elect the best plate.
7. Renderer   → draw results onto the frame for display.
"""

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np

from config.settings import SystemConfig, DEFAULT_CONFIG
from core.detector import PlateDetector
from core.recognizer import PlateRecognizer
from core.tracker import CentroidTracker
from core.validator import PlateValidator
from utils.image_utils import perspective_warp, preprocess_plate
from utils.logger import get_logger
from visualization.renderer import DisplayEntry, Renderer

# Optimise for Blackwell (RTX 50xx) architecture when available
os.environ.setdefault("TORCH_CUDA_ARCH_LIST", "8.9")
os.environ.setdefault("CUDA_MODULE_LOADING", "LAZY")

logger = get_logger(__name__)


@dataclass
class FrameResult:
    """
    Lightweight summary of what was detected in a single frame.
    Returned by ``ALPRPipeline.process_frame`` for testing / logging.
    """
    car_id: int
    raw_text: str
    validated_plate: str
    attempts: list = field(default_factory=list)  # List of all OCR attempts


class ALPRPipeline:
    """
    Automatic License Plate Recognition pipeline.

    Combines detection, tracking, OCR, validation, and rendering into a
    single coherent processing loop while keeping each concern isolated
    in its own component class.

    Args:
        config: Full system configuration. Defaults to ``DEFAULT_CONFIG``.
    """

    def __init__(self, config: SystemConfig = DEFAULT_CONFIG):
        self._cfg = config
        self._detector = PlateDetector(config.detector)
        self._recognizer = PlateRecognizer(config.recognizer)
        self._tracker = CentroidTracker(config.tracker)
        self._validator = PlateValidator(config.validator)
        self._renderer = Renderer(config.renderer)

        # Per-car vote history: car_id → list of validated plate strings
        self._histories: Dict[int, List[str]] = defaultdict(list)

        # Per-car last validated plate: car_id → last successfully recognized plate
        self._last_validated: Dict[int, str] = {}

        # Per-car display state: car_id → DisplayEntry
        self._display: Dict[int, DisplayEntry] = {}

        logger.info("ALPRPipeline ready.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> List[FrameResult]:
        """
        Run the full pipeline on one video frame.

        Args:
            frame: BGR image as a NumPy uint8 array.

        Returns:
            List of FrameResult for every validated plate found this frame.
        """
        self._tracker.tick()
        self._expire_display_entries()

        results: List[FrameResult] = []
        regions = self._detector.detect(frame)

        for region in regions:
            car_id = self._tracker.update(region.centroid)
            frame_results = self._process_region(frame, region, car_id)
            results.extend(frame_results)

        # Update display entries with latest known plates for all active cars
        for car_id, entry in self._display.items():
            if car_id in self._last_validated:
                # Update the text with the latest validated plate
                entry.text = self._last_validated[car_id]

        return results

    def get_annotated_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Return a copy of *frame* annotated with all active detections.
        """
        return self._renderer.render(frame, self._display)

    @property
    def final_report(self) -> Dict[int, str]:
        """
        Best (most-voted) plate per tracked vehicle across the entire run.

        Returns:
            Dict mapping car_id → most-voted plate string.
        """
        return {
            car_id: Counter(history).most_common(1)[0][0]
            for car_id, history in self._histories.items()
            if history
        }

    # ------------------------------------------------------------------
    # Private per-region processing
    # ------------------------------------------------------------------

    def _process_region(
        self,
        frame: np.ndarray,
        region,
        car_id: int,
    ) -> List[FrameResult]:
        """
        Warp, preprocess, OCR, validate, and update history for one region.
        """
        results: List[FrameResult] = []

        try:
            warped = perspective_warp(frame, region.contour.reshape(4, 2))
            processed = preprocess_plate(
                warped,
                upscale_factor=self._cfg.detector.upscale_factor,
                clahe_clip_limit=self._cfg.detector.clahe_clip_limit,
                clahe_tile_grid_size=self._cfg.detector.clahe_tile_grid_size,
            )
        except (ValueError, cv2.error) as exc:
            logger.debug("Region preprocessing failed for ID %d: %s", car_id, exc)
            return results

        raw_texts = self._recognizer.read(processed)

        for raw_text in raw_texts:
            validated, attempt_info = self._validator.validate(raw_text, car_id)
            
            # Track all attempts (successful or failed)
            attempts = [attempt_info] if attempt_info else []
            
            if validated is None:
                # Still return the failed attempt info
                results.append(FrameResult(
                    car_id=car_id,
                    raw_text=raw_text,
                    validated_plate="",
                    attempts=attempts,
                ))
                continue

            # Store this validated plate
            self._histories[car_id].append(validated)
            self._last_validated[car_id] = validated  # Update latest recognized plate
            
            # Display the LAST RECOGNIZED plate (what was just read), not the voted one
            self._update_display(car_id, validated, region.contour)

            results.append(FrameResult(
                car_id=car_id,
                raw_text=raw_text,
                validated_plate=validated,
                attempts=attempts,
            ))

        return results

    def _update_display(
        self,
        car_id: int,
        plate_text: str,
        bbox: np.ndarray,
    ) -> None:
        self._display[car_id] = DisplayEntry(
            text=plate_text,
            bbox=bbox,
            ttl=self._cfg.tracker.ttl_frames,
        )

    def _expire_display_entries(self) -> None:
        """
        Decrement TTL counters and removes stale display entries.
        Called once per frame before processing new detections.
        """
        expired = [
            cid for cid, entry in self._display.items() if entry.ttl <= 0
        ]
        for cid in expired:
            logger.debug("Display entry for ID %d expired.", cid)
            del self._display[cid]

        for entry in self._display.values():
            entry.ttl -= 1
