"""
On-screen rendering for the ALPR system.

Responsibility: Draw bounding boxes and plate labels onto video frames.
This module contains *only* display logic — it does not mutate any
application state.
"""

from dataclasses import dataclass
from typing import Dict

import cv2
import numpy as np

from config.settings import RendererConfig, DEFAULT_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DisplayEntry:
    """
    Everything the renderer needs to draw one detected plate.

    Attributes:
        text: Validated plate string to display.
        bbox: Contour array of shape (4, 1, 2) returned by OpenCV.
        ttl: Remaining time-to-live in frames (informational; not used
             by the renderer itself).
    """
    text: str
    bbox: np.ndarray
    ttl: int


class Renderer:
    """
    Draws bounding polygons and plate-number labels over a video frame.

    The renderer operates on a *copy* of the frame so the pipeline can
    safely display the annotated copy while retaining the original for
    further processing if needed.

    Args:
        config: Visual style parameters. Defaults to system defaults.
    """

    def __init__(self, config: RendererConfig = DEFAULT_CONFIG.renderer):
        self._cfg = config

    def render(
        self,
        frame: np.ndarray,
        display_entries: Dict[int, DisplayEntry],
    ) -> np.ndarray:
        """
        Annotate a frame with all active detections.

        Args:
            frame: Original BGR frame (not modified).
            display_entries: Mapping of car_id → DisplayEntry for every
                             track that should be drawn.

        Returns:
            A new BGR frame with all annotations overlaid.
        """
        output = frame.copy()
        for car_id, entry in display_entries.items():
            self._draw_box(output, entry.bbox)
            self._draw_label(output, entry.bbox, car_id, entry.text)
        return output

    # ------------------------------------------------------------------
    # Private drawing helpers
    # ------------------------------------------------------------------

    def _draw_box(self, frame: np.ndarray, bbox: np.ndarray) -> None:
        """Draw the quadrilateral outline around the plate region."""
        cv2.drawContours(
            frame, [bbox], -1,
            self._cfg.box_color,
            self._cfg.box_thickness,
        )

    def _draw_label(
        self,
        frame: np.ndarray,
        bbox: np.ndarray,
        car_id: int,
        text: str,
    ) -> None:
        """
        Draw a filled rectangle label near the bounding box.

        The label shows the tracker ID and the plate number.
        Automatically repositions if it would go out of bounds.
        """
        h, w = frame.shape[:2]
        
        # Anchor to the first corner point of bbox
        bbox_x, bbox_y = int(bbox[0][0][0]), int(bbox[0][0][1])
        
        # Calculate label dimensions
        label_w = self._cfg.label_width
        label_h = self._cfg.label_height
        
        # Try to place label above bbox
        label_x = bbox_x
        label_y_top = bbox_y - label_h
        label_y_bottom = bbox_y
        
        # If label goes above frame, place below bbox instead
        if label_y_top < 0:
            bbox_points = bbox.reshape(-1, 2)
            bbox_bottom = int(max(bbox_points[:, 1]))
            label_y_top = min(bbox_bottom, h - label_h)
            label_y_bottom = min(label_y_top + label_h, h)
        
        # If label goes right of frame, move it left
        if label_x + label_w > w:
            label_x = max(0, w - label_w)
        
        # Clamp coordinates
        label_x = max(0, label_x)
        label_y_top = max(0, label_y_top)
        label_x_end = min(w, label_x + label_w)
        label_y_bottom = min(h, label_y_bottom)

        # Draw background rectangle
        cv2.rectangle(
            frame,
            (label_x, label_y_top),
            (label_x_end, label_y_bottom),
            self._cfg.label_bg_color,
            -1,  # filled
        )

        # Draw text (centered vertically in label)
        text_x = label_x + 5
        text_y = label_y_top + (label_h // 2) + 5
        
        label = f"ID{car_id}: {text}"
        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_DUPLEX,
            self._cfg.font_scale,
            self._cfg.label_text_color,
            self._cfg.font_thickness,
        )

    @property
    def window_title(self) -> str:
        """Window title used by cv2.imshow."""
        return self._cfg.window_title
