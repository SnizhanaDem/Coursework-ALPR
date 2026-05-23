"""
Centralized configuration for the ALPR system.
All tunable parameters are defined here to avoid magic numbers in business logic.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class DetectorConfig:
    """Parameters for the license plate detection stage."""
    bilateral_diameter: int = 11
    bilateral_sigma_color: int = 17
    bilateral_sigma_space: int = 17
    canny_low_threshold: int = 30
    canny_high_threshold: int = 200
    contour_approximation_epsilon: int = 10
    min_contour_area: int = 800
    top_contours_count: int = 10
    required_polygon_vertices: int = 4
    upscale_factor: float = 3.0
    clahe_clip_limit: float = 3.0
    clahe_tile_grid_size: Tuple[int, int] = (8, 8)


@dataclass(frozen=True)
class TrackerConfig:
    """Parameters for the centroid-based vehicle tracker."""
    max_centroid_distance: int = 120
    ttl_frames: int = 25


@dataclass(frozen=True)
class RecognizerConfig:
    """Parameters for the EasyOCR-based text recognizer."""
    languages: List[str] = field(default_factory=lambda: ['en'])
    allowlist: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


@dataclass(frozen=True)
class ValidatorConfig:
    """
    Rules for Ukrainian license plate validation and correction.
    Format: XX####XX where X=letter, #=digit.
    """
    min_plate_length: int = 7
    max_plate_length: int = 8
    plate_pattern: str = r'^[A-Z]{2}\d{4}[A-Z]{2}$'

    # Characters that look like letters but are actually digits in letter positions
    digit_to_letter_map: dict = field(default_factory=lambda: {
        '0': 'O', '1': 'I', '2': 'Z', '5': 'S',
        '8': 'B', '3': 'B', '4': 'A', '7': 'T',
        '6': 'G', 'J': 'B', 'R': 'B',
    })

    # Characters that look like digits but are actually letters in digit positions
    letter_to_digit_map: dict = field(default_factory=lambda: {
        'O': '0', 'D': '0', 'I': '1', 'J': '1',
        'S': '5', 'B': '8', 'A': '4', 'Z': '2',
        'G': '6', 'T': '7',
    })

    # Known misread prefixes/suffixes that should be corrected
    common_prefix_fixes: dict = field(default_factory=lambda: {
        'XE': 'KE',
        'RC': 'BC',
        'KC': 'MC',
    })

    common_suffix_fixes: dict = field(default_factory=lambda: {
        'EZ': 'EC',
        'G8': 'IH',
        'GB': 'IH',
        'KC': 'MC',  
    })

    valid_suffixes: List[str] = field(default_factory=lambda: [
        'AA', 'AB', 'AC', 'AE', 'AH', 'AI', 'AK', 'AM', 'AO', 'AP', 'AT', 'AX',
        'BA', 'BB', 'BC', 'BE', 'BH', 'BI', 'BK', 'BM', 'BO', 'BT', 'BX',
        'CA', 'CB', 'CC', 'CE', 'CH', 'CI', 'CK', 'CM', 'CO', 'CP', 'CT', 'CX',
        'IA', 'IB', 'IC', 'IE', 'IH', 'II', 'IK', 'IM', 'IO', 'IP', 'IT', 'IX',
        'PX', 'KX', 'EX', 'HX', 'AX',
        'MC', 'ME', 'MH', 'MI', 'MK', 'MM', 'MO', 'MP', 'MT', 'MX',
    ])


@dataclass(frozen=True)
class RendererConfig:
    """Visual parameters for the on-screen display."""
    box_color: Tuple[int, int, int] = (0, 255, 0)
    box_thickness: int = 2
    label_bg_color: Tuple[int, int, int] = (0, 255, 0)
    label_text_color: Tuple[int, int, int] = (0, 0, 0)
    label_height: int = 35
    label_width: int = 220
    font_scale: float = 0.8
    font_thickness: int = 2
    window_title: str = "ALPR — Automatic License Plate Recognition"


@dataclass(frozen=True)
class SystemConfig:
    """Top-level system configuration that groups all sub-configs."""
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    recognizer: RecognizerConfig = field(default_factory=RecognizerConfig)
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)
    renderer: RendererConfig = field(default_factory=RendererConfig)
    history_window: int = 25


# Default singleton config used throughout the system
DEFAULT_CONFIG = SystemConfig()
