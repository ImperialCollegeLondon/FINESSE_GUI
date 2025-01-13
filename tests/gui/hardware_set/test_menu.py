"""Tests for the HardwareSetsMenu class."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from finesse.gui.hardware_set.hardware_set import (
    HardwareSet,
)
from finesse.gui.hardware_set.menu import HardwareSetsMenu


@pytest.fixture()
def hw_menu(qtbot) -> HardwareSetsMenu:
    """A fixture providing a HardwareSetsMenu."""
    return HardwareSetsMenu()


@patch.object(HardwareSet, "load")
@patch("finesse.gui.hardware_set.menu.show_error_message")
@patch("finesse.gui.hardware_set.menu.QFileDialog.getOpenFileName")
def test_import_hardware_set_success(
    open_file_mock: Mock,
    error_message_mock: Mock,
    load_mock: Mock,
    hw_menu: HardwareSetsMenu,
    sendmsg_mock: MagicMock,
    qtbot,
) -> None:
    """Test the _import_hardware_set() method when a file is loaded successfully."""
    path = Path("dir/file.txt")
    hw_set = MagicMock()
    load_mock.return_value = hw_set
    open_file_mock.return_value = (str(path), None)
    hw_menu._import_hardware_set()
    load_mock.assert_called_once_with(path)
    sendmsg_mock.assert_called_once_with("hardware_set.add", hw_set=hw_set)
    error_message_mock.assert_not_called()


@patch.object(HardwareSet, "load")
@patch("finesse.gui.hardware_set.menu.show_error_message")
@patch("finesse.gui.hardware_set.menu.QFileDialog.getOpenFileName")
def test_import_hardware_set_cancelled(
    open_file_mock: Mock,
    error_message_mock: Mock,
    load_mock: Mock,
    hw_menu: HardwareSetsMenu,
    sendmsg_mock: MagicMock,
    qtbot,
) -> None:
    """Test the _import_hardware_set() method when the dialog is closed."""
    open_file_mock.return_value = (None, None)
    hw_menu._import_hardware_set()
    sendmsg_mock.assert_not_called()
    error_message_mock.assert_not_called()
    load_mock.assert_not_called()


@patch.object(HardwareSet, "load")
@patch("finesse.gui.hardware_set.menu.show_error_message")
@patch("finesse.gui.hardware_set.menu.QFileDialog.getOpenFileName")
def test_import_hardware_set_error(
    open_file_mock: Mock,
    error_message_mock: Mock,
    load_mock: Mock,
    hw_menu: HardwareSetsMenu,
    sendmsg_mock: MagicMock,
    qtbot,
) -> None:
    """Test the _import_hardware_set() method when a file fails to load."""
    path = Path("dir/file.txt")
    load_mock.side_effect = RuntimeError
    open_file_mock.return_value = (str(path), None)
    hw_menu._import_hardware_set()
    load_mock.assert_called_once_with(path)
    sendmsg_mock.assert_not_called()
    error_message_mock.assert_called_once()
