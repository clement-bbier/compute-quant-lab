"""Logging standard du labo. Jamais de `print` dans `core/` (rule python-quality)."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Renvoie un logger configuré (handler unique, pas de double-logging)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
