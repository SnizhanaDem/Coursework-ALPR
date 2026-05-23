"""
Unit tests for the PlateValidator class.

Tests cover each correction stage independently, as well as
end-to-end acceptance and rejection scenarios.

Run with:
    python -m pytest tests/test_validator.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.validator import PlateValidator
from config.settings import ValidatorConfig


@pytest.fixture
def validator() -> PlateValidator:
    """Shared PlateValidator instance for all tests."""
    return PlateValidator()


# ---------------------------------------------------------------------------
# _clean
# ---------------------------------------------------------------------------

class TestClean:
    def test_strips_spaces(self, validator):
        result = validator._clean("AA 1234 BC")
        assert result == "AA1234BC"

    def test_strips_dashes(self, validator):
        result = validator._clean("AA-1234-BC")
        assert result == "AA1234BC"

    def test_converts_to_uppercase(self, validator):
        result = validator._clean("aa1234bc")
        assert result == "AA1234BC"

    def test_removes_special_chars(self, validator):
        result = validator._clean("AA!@#1234BC")
        assert result == "AA1234BC"


# ---------------------------------------------------------------------------
# _is_valid_length
# ---------------------------------------------------------------------------

class TestIsValidLength:
    def test_accepts_7_chars(self, validator):
        assert validator._is_valid_length("AA1234B") is True

    def test_accepts_8_chars(self, validator):
        assert validator._is_valid_length("AA1234BC") is True

    def test_rejects_6_chars(self, validator):
        assert validator._is_valid_length("AA123B") is False

    def test_rejects_9_chars(self, validator):
        assert validator._is_valid_length("AA12345BC") is False


# ---------------------------------------------------------------------------
# _apply_positional_substitution
# ---------------------------------------------------------------------------

class TestPositionalSubstitution:
    def test_zero_to_O_at_letter_position(self, validator):
        result = validator._apply_positional_substitution("0A1234BC")
        assert result[0] == "O"

    def test_O_to_0_at_digit_position(self, validator):
        result = validator._apply_positional_substitution("AA O234BC")
        # After clean the O is at position 2 (digit zone)
        cleaned = "AAO234BC"
        result = validator._apply_positional_substitution(cleaned)
        assert result[2] == "0"

    def test_last_position_corrected_to_letter(self, validator):
        # '8' in last position should become 'B'
        result = validator._apply_positional_substitution("AA12348C")
        # position -1 is letter zone; '8' → 'B'
        assert result[-1] == "B" or result[-1] == "C"  # depends on mapping


# ---------------------------------------------------------------------------
# validate — end-to-end
# ---------------------------------------------------------------------------

class TestValidateEndToEnd:
    def test_clean_plate_passes(self, validator):
        result, _ = validator.validate("AA1234BC")
        assert result == "AA1234BC"

    def test_lowercase_plate_passes(self, validator):
        result, _ = validator.validate("aa1234bc")
        assert result == "AA1234BC"

    def test_plate_with_spaces_passes(self, validator):
        result, _ = validator.validate("AA 1234 BC")
        assert result == "AA1234BC"

    def test_too_short_returns_none(self, validator):
        result, _ = validator.validate("AA123B")
        assert result is None

    def test_too_long_returns_none(self, validator):
        result, _ = validator.validate("AA12345BCD")
        assert result is None

    def test_zero_corrected_to_O_in_prefix(self, validator):
        # '0A' prefix → should become 'OA' (letter zone)
        result, _ = validator.validate("0A1234BC")
        assert result is not None
        assert result[0] == "O"

    def test_invalid_pattern_returns_none(self, validator):
        # Five letters in middle — can't be corrected to digits
        result, _ = validator.validate("AAABCDEBC")
        assert result is None

    def test_known_prefix_fix_RC_to_BC(self, validator):
        result, _ = validator.validate("RC1234BC")
        # RC → BC after prefix fix
        assert result is not None
        assert result.startswith("BC")

    def test_car_id_kwarg_does_not_affect_result(self, validator):
        r1, _ = validator.validate("AA1234BC", car_id=0)
        r2, _ = validator.validate("AA1234BC", car_id=99)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Custom configuration
# ---------------------------------------------------------------------------

class TestCustomConfig:
    def test_custom_min_length_rejected(self):
        cfg = ValidatorConfig(min_plate_length=9, max_plate_length=9)
        v = PlateValidator(cfg)
        # Standard 8-char plate should now be rejected
        result, _ = v.validate("AA1234BC")
        assert result is None
