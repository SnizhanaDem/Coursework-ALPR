"""
Ukrainian license plate validator and corrector.

Responsibility: Given a raw OCR string, apply positional character
substitution rules to produce a candidate that conforms to the
Ukrainian standard format, then verify it against a whitelist.

Ukrainian standard format (post-2004):
    XX####XX
    where X = Latin letter, # = decimal digit.

Design notes
------------
* The module contains *no* I/O logic — it is a pure function transformer.
* All correction rules live in ``config.settings.ValidatorConfig`` so
  they can be tuned without modifying this module.
* Each correction stage is a separate method so it can be unit-tested
  independently.
"""

import re
from typing import Optional
from collections import Counter

from config.settings import ValidatorConfig, DEFAULT_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class PlateValidator:
    """
    Validates and auto-corrects raw OCR text into a valid Ukrainian
    license plate number.

    Correction pipeline (applied in order):
      1. Strip non-alphanumeric characters and convert to uppercase.
      2. Reject strings whose length is outside [min, max].
      3. Apply positional substitution:
           - Positions 0, 1, -2, -1  →  force to valid letters.
           - Positions 2 … -3        →  force to valid digits.
      4. Apply known prefix/suffix corrections from the lookup table.
      5. Validate suffix against the regional code whitelist.
      6. Match against the final regex pattern.

    Args:
        config: Validation rules. Defaults to system defaults.
    """

    def __init__(self, config: ValidatorConfig = DEFAULT_CONFIG.validator):
        self._cfg = config
        self._pattern = re.compile(config.plate_pattern)

    def validate(self, raw_text: str, car_id: int = 0) -> tuple:
        """
        Attempt to correct and validate a raw OCR string.

        Args:
            raw_text: Raw string returned by the OCR stage.
            car_id: Optional tracker ID used for logging only.

        Returns:
            Tuple of (validated_plate, attempt_info) where:
            - validated_plate: A validated plate string (format XX####XX) on success, or None if failed.
            - attempt_info: Dict with keys 'raw_text', 'corrected', 'success', 'reason' (if failed).
        """
        cleaned = self._clean(raw_text)
        
        # Check length
        if not self._is_valid_length(cleaned):
            return None, {
                "car_id": car_id,
                "raw_text": raw_text,
                "corrected": cleaned,
                "success": False,
                "reason": "невалідна довжина"
            }

        corrected = self._apply_positional_substitution(cleaned)
        corrected = self._apply_prefix_suffix_fixes(corrected)
        corrected = self._apply_suffix_whitelist(corrected)

        if not self._pattern.match(corrected):
            logger.debug(
                "[ID %d] '%s' → '%s' — failed final pattern check.",
                car_id, raw_text, corrected,
            )
            print(f"🔍 [ID {car_id}] Спроба: '{raw_text}' -> '{corrected}' ❌ (невалідний формат)")
            return None, {
                "car_id": car_id,
                "raw_text": raw_text,
                "corrected": corrected,
                "success": False,
                "reason": "невалідний формат"
            }

        logger.debug(
            "[ID %d] '%s' → '%s' — accepted.", car_id, raw_text, corrected
        )
        print(f"🔍 [ID {car_id}] Спроба: '{raw_text}' -> ✅ {corrected}")
        
        return corrected, {
            "car_id": car_id,
            "raw_text": raw_text,
            "corrected": corrected,
            "success": True,
            "reason": ""
        }

    # ------------------------------------------------------------------
    # Private correction stages
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """Strip everything except A-Z and 0-9, then uppercase."""
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    def _is_valid_length(self, text: str) -> bool:
        return self._cfg.min_plate_length <= len(text) <= self._cfg.max_plate_length

    def _apply_positional_substitution(self, text: str) -> str:
        """
        Enforce the expected character class at each position.

        Positions 0, 1 and the last two must be letters.
        The middle positions must be digits.
        OCR often confuses visually similar characters (e.g. '0' vs 'O'),
        so we apply the appropriate substitution table at each position.
        """
        chars = list(text)
        n = len(chars)
        letter_positions = {0, 1, n - 2, n - 1}
        digit_positions = set(range(2, n - 2))

        for i in letter_positions:
            chars[i] = self._cfg.digit_to_letter_map.get(chars[i], chars[i])

        for i in digit_positions:
            chars[i] = self._cfg.letter_to_digit_map.get(chars[i], chars[i])

        return "".join(chars)

    def _apply_prefix_suffix_fixes(self, text: str) -> str:
        """
        Replace known misread two-letter prefixes and suffixes.
        """
        prefix = self._cfg.common_prefix_fixes.get(text[:2], text[:2])
        suffix = self._cfg.common_suffix_fixes.get(text[-2:], text[-2:])
        return prefix + text[2:-2] + suffix

    def _apply_suffix_whitelist(self, text: str) -> str:
        """
        If the suffix is not in the regional-code whitelist, try
        common fallback corrections and return the original if none match.
        """
        suffix = text[-2:]
        if suffix in self._cfg.valid_suffixes:
            return text

        # Attempt legacy one-off fixes not covered by common_suffix_fixes
        fallback = {"EZ": "EC", "G8": "IH", "GB": "IH"}.get(suffix, suffix)
        logger.debug("Suffix '%s' not in whitelist — tried fallback '%s'.", suffix, fallback)
        return text[:-2] + fallback
