"""
OCR-based license plate text recognizer.

Responsibility: Given a preprocessed plate image, return raw text
candidates. This module does NOT validate or correct the text — that
is the Validator's job.
"""

from typing import List

import numpy as np
import torch
import easyocr

from config.settings import RecognizerConfig, DEFAULT_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class PlateRecognizer:
    """
    Wraps EasyOCR to extract raw text strings from a preprocessed
    license-plate image.

    GPU acceleration is enabled automatically when CUDA is available.
    The reader is instantiated once and reused across all frames to
    avoid the significant overhead of repeated initialisation.

    Args:
        config: OCR hyperparameters. Defaults to system defaults.
    """

    def __init__(self, config: RecognizerConfig = DEFAULT_CONFIG.recognizer):
        self._cfg = config
        self._use_gpu = torch.cuda.is_available()

        logger.info(
            "Initialising EasyOCR reader  |  GPU=%s  |  languages=%s",
            self._use_gpu,
            config.languages,
        )
        self._reader = easyocr.Reader(config.languages, gpu=self._use_gpu)
        logger.info("EasyOCR reader ready.")

    @property
    def use_gpu(self) -> bool:
        """True if the recognizer is running on a CUDA-capable GPU."""
        return self._use_gpu

    def read(self, plate_image: np.ndarray) -> List[str]:
        """
        Extract text candidates from a preprocessed (binary) plate image.

        Args:
            plate_image: Single-channel binary image produced by
                         ``utils.image_utils.preprocess_plate``.

        Returns:
            List of raw text strings detected by OCR, in confidence order
            (highest first). May be empty if nothing is detected.
        """
        if plate_image is None or plate_image.size == 0:
            logger.warning("Empty plate image passed to recognizer — skipping.")
            return []

        results: List[str] = self._reader.readtext(
            plate_image,
            detail=0,
            allowlist=self._cfg.allowlist,
        )
        logger.debug("OCR raw results: %s", results)
        return results
