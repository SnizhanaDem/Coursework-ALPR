"""
Logging configuration for the ALPR system.

Uses Python's standard logging module with a consistent format across all modules.
Supports both console and file output.
"""

import logging
import sys
from pathlib import Path


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Create or retrieve a named logger with consistent formatting.

    Args:
        name: Logger name, typically __name__ of the calling module.
        level: Logging level (default: DEBUG).

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured — avoid duplicate handlers

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(handler)

    return logger


def add_file_handler(logger: logging.Logger, log_path: str) -> None:
    """
    Attach a file handler to an existing logger.

    Args:
        logger: Target logger.
        log_path: Path to the output log file.
    """
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(file_handler)
