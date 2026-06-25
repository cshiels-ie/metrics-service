"""
Coverage-focused test fixtures supplementing tests/conftest.py.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_dispatcherd():
    """Patch dispatcherd.publish so no real broker connection is needed."""
    with patch("dispatcherd.publish.submit_task") as mock_submit:
        yield mock_submit


@pytest.fixture
def mock_dispatcherd_config():
    """Patch ensure_dispatcherd_configured to a no-op."""
    with patch("apps.tasks.dispatcherd_config.ensure_dispatcherd_configured"):
        yield


@pytest.fixture
def mock_lock_acquired():
    """Patch metrics_utility lock so it immediately yields True (acquired)."""

    @contextmanager
    def _fake_lock(key, wait=True, db=None):
        yield True

    with patch("metrics_utility.library.lock.lock", side_effect=_fake_lock):
        yield


@pytest.fixture
def mock_lock_not_acquired():
    """Patch metrics_utility lock so it immediately yields False (not acquired)."""

    @contextmanager
    def _fake_lock(key, wait=True, db=None):
        yield False

    with patch("metrics_utility.library.lock.lock", side_effect=_fake_lock):
        yield


@pytest.fixture
def mock_apscheduler():
    """Mock BackgroundScheduler so no real threads are spawned."""
    with patch("apps.tasks.cron_scheduler.BackgroundScheduler") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.running = True
        mock_cls.return_value = mock_instance
        yield mock_instance
