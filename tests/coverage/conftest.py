from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_dispatcherd():
    with patch("dispatcherd.publish.submit_task") as mock:
        yield mock


@pytest.fixture
def mock_dispatcherd_config():
    with patch("apps.tasks.dispatcherd_config.ensure_dispatcherd_configured"):
        yield


@pytest.fixture
def mock_lock_acquired():
    mock_lock = MagicMock()
    mock_lock.__enter__ = MagicMock(return_value=True)
    mock_lock.__exit__ = MagicMock(return_value=False)
    with patch("metrics_utility.library.lock.lock", return_value=mock_lock):
        yield


@pytest.fixture
def mock_lock_not_acquired():
    mock_lock = MagicMock()
    mock_lock.__enter__ = MagicMock(return_value=False)
    mock_lock.__exit__ = MagicMock(return_value=False)
    with patch("metrics_utility.library.lock.lock", return_value=mock_lock):
        yield
