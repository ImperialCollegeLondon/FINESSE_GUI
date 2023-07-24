"""Tests for SerialControl and associated code."""
from collections import namedtuple
from collections.abc import Sequence
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtWidgets import QComboBox, QGridLayout
from pytestqt.qtbot import QtBot

from finesse.gui.serial_view import (
    DUMMY_DEVICE_PORT,
    Device,
    DeviceControls,
    SerialPortControl,
    get_default_ports,
    get_usb_serial_ports,
)

DEVICE_NAME = "device"
"""The name to use for the mock serial device."""

PORT_KEY = f"serial/{DEVICE_NAME}/port"
BAUDRATE_KEY = f"serial/{DEVICE_NAME}/baudrate"


@pytest.fixture
def device_controls(qtbot: QtBot) -> DeviceControls:
    """A fixture providing a DeviceControls object."""
    ports = ("COM0",)
    baudrates = range(3)
    return DeviceControls(
        QGridLayout(), 0, Device("My device", DEVICE_NAME, 1), ports, baudrates
    )


MockPortInfo = namedtuple("MockPortInfo", "device vid")


@pytest.mark.parametrize(
    "devices,expected",
    (
        # One USB serial device
        (
            [MockPortInfo(device="COM1", vid=1)],
            ["COM1"],
        ),
        # One non-USB serial device
        (
            [MockPortInfo(device="COM1", vid=None)],
            [],
        ),
        # Two USB serial devices, unsorted
        (
            [
                MockPortInfo(device="COM2", vid=1),
                MockPortInfo(device="COM1", vid=1),
            ],
            ["COM1", "COM2"],
        ),
    ),
)
@patch("finesse.gui.serial_view.comports")
def test_get_usb_serial_ports(
    comports_mock: Mock, devices: list[MockPortInfo], expected: list[str]
) -> None:
    """Test the get_usb_serial_ports() function."""
    comports_mock.return_value = devices
    assert get_usb_serial_ports() == expected


@patch("finesse.gui.serial_view.get_usb_serial_ports")
@patch("finesse.gui.serial_view.ALLOW_DUMMY_DEVICES", True)
def test_get_default_ports_dummy(get_usb_mock: Mock) -> None:
    """Test the get_default_ports() function with a dummy device."""
    get_usb_mock.return_value = ["COM1"]
    assert DUMMY_DEVICE_PORT in get_default_ports()


@patch("finesse.gui.serial_view.get_usb_serial_ports")
@patch("finesse.gui.serial_view.ALLOW_DUMMY_DEVICES", False)
def test_get_default_ports_no_dummy(get_usb_mock: Mock) -> None:
    """Test the get_default_ports() function when there should be no dummy devices."""
    get_usb_mock.return_value = ["COM1"]
    assert DUMMY_DEVICE_PORT not in get_default_ports()


def items_equal(combo: QComboBox, values: Sequence[Any]) -> bool:
    """Check that all items of a QComboBox match those in a Sequence."""
    if combo.count() != len(values):
        return False

    items = (combo.itemText(i) for i in range(combo.count()))
    return all(item == str(val) for item, val in zip(items, values))


@patch("finesse.gui.serial_view.QPushButton")
@patch("finesse.gui.serial_view.settings")
def test_device_controls_init(
    settings_mock: Mock, btn_mock: Mock, subscribe_mock: MagicMock, qtbot: QtBot
) -> None:
    """Test DeviceControls' constructor."""
    PORT_DEFAULT = "COM0"
    PORT_SETTINGS = "COM1"
    BAUDRATE_DEFAULT = 1
    BAUDRATE_SETTINGS = 2

    settings_get_mock = MagicMock()

    def get_setting(key, *args, **kwargs):
        settings_get_mock(key, *args, **kwargs)
        settings_values = {PORT_KEY: PORT_SETTINGS, BAUDRATE_KEY: BAUDRATE_SETTINGS}
        return settings_values[key]

    settings_mock.value = get_setting

    btn = MagicMock()
    btn_mock.return_value = btn
    ports = ("COM0", "COM1")
    baudrates = range(3)

    controls = DeviceControls(
        MagicMock(),
        0,
        Device("My device", DEVICE_NAME, BAUDRATE_DEFAULT),
        ports,
        baudrates,
    )

    settings_get_mock.assert_any_call(PORT_KEY, PORT_DEFAULT)
    settings_get_mock.assert_any_call(BAUDRATE_KEY, BAUDRATE_DEFAULT)

    assert items_equal(controls.ports, ports)
    assert items_equal(controls.baudrates, baudrates)
    assert controls.baudrates.currentText() == "2"

    btn.clicked.connect.assert_called_once_with(controls._on_open_close_clicked)

    subscribe_mock.assert_any_call(
        controls._on_device_opened, f"serial.{DEVICE_NAME}.opened"
    )
    subscribe_mock.assert_any_call(
        controls._on_device_closed, f"serial.{DEVICE_NAME}.close"
    )
    subscribe_mock.assert_any_call(
        controls._show_error_message, f"serial.{DEVICE_NAME}.error"
    )


@patch("finesse.gui.serial_view.settings")
def test_on_device_opened(settings_mock: Mock, device_controls: DeviceControls) -> None:
    """Test the _on_device_opened() method."""
    with patch.object(device_controls.ports, "currentText") as ports_mock:
        ports_mock.return_value = "COM0"
        with patch.object(device_controls.baudrates, "currentText") as baudrates_mock:
            baudrates_mock.return_value = "1234"
            with patch.object(device_controls, "open_close_btn") as btn_mock:
                device_controls._on_device_opened()
                btn_mock.setText.assert_called_once_with("Close")

                # Check that the settings were updated
                settings_mock.setValue.assert_any_call(PORT_KEY, "COM0")
                settings_mock.setValue.assert_any_call(BAUDRATE_KEY, 1234)


def test_on_device_closed(device_controls: DeviceControls) -> None:
    """Test the _on_device_closed() method."""
    with patch.object(device_controls, "open_close_btn") as btn_mock:
        device_controls._on_device_closed()
        btn_mock.setText.assert_called_once_with("Open")


@patch("finesse.gui.serial_view.QMessageBox")
def test_show_error_message(msgbox_mock: Mock, device_controls: DeviceControls) -> None:
    """Test the _show_error_message() method."""
    msgbox = MagicMock()
    msgbox_mock.return_value = msgbox
    device_controls._show_error_message(RuntimeError("hello"))
    msgbox.exec.assert_called_once_with()


def test_on_open_close_clicked(device_controls: DeviceControls, qtbot: QtBot) -> None:
    """Test the open/close button."""
    # Device starts off closed
    assert device_controls.open_close_btn.text() == "Open"
    assert not device_controls.open_close_btn.isChecked()

    with patch.object(device_controls, "_open_device") as open_mock:
        with patch.object(device_controls, "_close_device") as close_mock:
            # Try to open the device
            device_controls._on_open_close_clicked()
            open_mock.assert_called_once()
            close_mock.assert_not_called()

            # Signal that the device opened successfully
            device_controls._on_device_opened()

            # Check that we can close it again successfully
            open_mock.reset_mock()
            close_mock.reset_mock()
            device_controls._on_open_close_clicked()
            open_mock.assert_not_called()
            close_mock.assert_called_once()


def test_open_device(
    device_controls: DeviceControls,
    sendmsg_mock: MagicMock,
    qtbot: QtBot,
) -> None:
    """Test _open_device()."""
    with patch.object(device_controls.ports, "currentText") as ports_mock:
        ports_mock.return_value = "COM0"
        with patch.object(device_controls.baudrates, "currentText") as baudrates_mock:
            baudrates_mock.return_value = "1234"
            device_controls._open_device()

            # Check that the appropriate command was sent to the backend
            sendmsg_mock.assert_any_call(
                f"serial.{DEVICE_NAME}.open", port="COM0", baudrate=1234
            )


def test_close_device(
    device_controls: DeviceControls, qtbot: QtBot, sendmsg_mock: MagicMock
) -> None:
    """Test the _close_device() method."""
    device_controls._close_device()
    sendmsg_mock.assert_any_call(f"serial.{DEVICE_NAME}.close")


@patch("finesse.gui.serial_view.QGridLayout")
@patch("finesse.gui.serial_view.DeviceControls")
def test_serial_port_control_init(
    controls_mock: Mock, grid_mock: Mock, qtbot: QtBot
) -> None:
    """Test SerialPortControl's constructor."""
    # Make the constructor return *this* QGridLayout
    layout = QGridLayout()
    grid_mock.return_value = layout

    devices = (Device("device1", "DEVICE1", 1), Device("device2", "DEVICE2", 1))
    avail_ports = ("port1", "port2")
    avail_baudrates = range(2)
    SerialPortControl(devices, avail_ports, avail_baudrates)

    # Check that the appropriate DeviceControls have been created
    for i, device in enumerate(devices):
        controls_mock.assert_any_call(layout, i, device, avail_ports, avail_baudrates)
