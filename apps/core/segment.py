"""Segment integration utilities."""

import logging
import os
from pathlib import Path


def read_segment_key_from_path(path: Path) -> str | None:
    """Read SEGMENT_WRITE_KEY from a single file. Returns the key or None."""
    logger = logging.getLogger(__name__)
    try:
        if not path.is_file():
            return None
        key = path.read_text().strip()
        return key if key else None
    except OSError as e:
        filename = getattr(e, "filename", path)
        logger.exception(
            "Failed to read segment write key from %s: %s",
            filename,
            e,
        )
        return None


def load_segment_write_key_from_file(
    path: Path | None = None,
    dynaconf_instance=None,
) -> None:
    """Load SEGMENT_WRITE_KEY from file and set on Dynaconf. Used at module load and in tests."""
    logger = logging.getLogger(__name__)

    if path is None:
        _segment_write_key_path = os.environ.get(
            "METRICS_SERVICE_SEGMENT_WRITE_KEY_FILE",
            "/etc/ansible-automation-platform/metrics/segment-write-key",
        )
        path = Path(_segment_write_key_path)

    # Respect env/settings precedence: do not overwrite if already set
    env_key = os.environ.get("METRICS_SERVICE_SEGMENT_WRITE_KEY", "").strip()
    if env_key:
        logger.debug("SEGMENT_WRITE_KEY already set in environment, skipping file load")
        return

    if dynaconf_instance is not None:
        existing_key = dynaconf_instance.get("SEGMENT_WRITE_KEY")
        if existing_key:
            logger.debug("SEGMENT_WRITE_KEY already set in settings, skipping file load")
            return

    if not path.exists():
        logger.debug(f"Segment key file does not exist: {path}")
        return

    key = read_segment_key_from_path(path)

    if key and dynaconf_instance is not None:
        logger.debug(f"Setting SEGMENT_WRITE_KEY from file: {path}")
        dynaconf_instance.set("SEGMENT_WRITE_KEY", key)
    elif not key:
        logger.warning(f"Failed to read segment key from: {path}")
    elif dynaconf_instance is None:
        logger.warning("Cannot set SEGMENT_WRITE_KEY: dynaconf_instance is None")
