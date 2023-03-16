"""Configuration for pytest."""
import os
from unittest.mock import MagicMock

import pytest
from pubsub import pub


@pytest.fixture
def subscribe_mock(monkeypatch) -> MagicMock:
    """Fixture for pub.subscribe."""
    mock = MagicMock()
    monkeypatch.setattr(pub, "subscribe", mock)
    return mock


@pytest.fixture
def sendmsg_mock(monkeypatch) -> MagicMock:
    """Fixture for pub.sendMessage."""
    mock = MagicMock()
    monkeypatch.setattr(pub, "sendMessage", mock)
    return mock


# Don't actually raise windows etc.
os.environ["QT_QPA_PLATFORM"] = "offscreen"