"""Tests for the HardwareSetsControl class."""

from collections.abc import Iterable, Sequence
from contextlib import nullcontext as does_not_raise
from itertools import chain
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest

from finesse.device_info import DeviceInstanceRef
from finesse.gui.hardware_set.device import ConnectionStatus, OpenDeviceArgs
from finesse.gui.hardware_set.hardware_set import (
    HardwareSet,
)
from finesse.gui.hardware_set.hardware_sets_view import (
    ActiveDeviceProperties,
    HardwareSetsControl,
    _get_last_selected_hardware_set,
)


@pytest.fixture
@patch.object(HardwareSetsControl, "_update_control_state")
@patch("finesse.gui.hardware_set.hardware_sets_view._get_last_selected_hardware_set")
@patch("finesse.gui.hardware_set.hardware_sets_view.get_hardware_sets")
def hw_control(
    get_hw_sets_mock: Mock,
    last_selected_mock: Mock,
    update_mock: Mock,
    hw_sets: Sequence[HardwareSet],
    sendmsg_mock: MagicMock,
    subscribe_mock: MagicMock,
    qtbot,
) -> HardwareSetsControl:
    """A fixture for the control."""
    last_selected_mock.return_value = None
    get_hw_sets_mock.return_value = hw_sets
    return HardwareSetsControl()


def _dev_to_connected(
    devices: Iterable[OpenDeviceArgs],
) -> dict[DeviceInstanceRef, ActiveDeviceProperties]:
    return {
        d.instance: ActiveDeviceProperties(d, ConnectionStatus.CONNECTED)
        for d in devices
    }


def _dev_to_connecting(
    devices: Iterable[OpenDeviceArgs],
) -> dict[DeviceInstanceRef, ActiveDeviceProperties]:
    return {
        d.instance: ActiveDeviceProperties(d, ConnectionStatus.CONNECTING)
        for d in devices
    }


@pytest.mark.parametrize("last_selected", (None, "some/path.yaml"))
@patch(
    "finesse.gui.hardware_set.hardware_sets_view"
    ".HardwareSetsComboBox.current_hardware_set",
    new_callable=PropertyMock,
)
@patch.object(HardwareSetsControl, "_update_control_state")
@patch("finesse.gui.hardware_set.hardware_sets_view._get_last_selected_hardware_set")
def test_init(
    load_last_mock: Mock,
    update_mock: Mock,
    cur_hw_set_mock: PropertyMock,
    last_selected: str | None,
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test the constructor."""
    load_last_mock.return_value = last_selected
    hw_sets = HardwareSetsControl()
    load_last_mock.assert_called_once_with()
    update_mock.assert_called_once_with()
    if last_selected:
        cur_hw_set_mock.assert_called_once()
    else:
        cur_hw_set_mock.assert_not_called()

    # HardwareSetsComboBox's constructor will also call pub.subscribe
    subscribe_mock.assert_any_call(hw_sets._on_device_open_end, "device.after_opening")
    subscribe_mock.assert_any_call(hw_sets._on_device_closed, "device.closed")


@patch("finesse.gui.hardware_set.hardware_sets_view.get_hardware_sets")
@patch("finesse.gui.hardware_set.hardware_sets_view.settings")
def test_get_last_selected_hardware_set_cached_success(
    settings_mock: Mock, get_hw_sets_mock: Mock, hw_sets: Sequence[HardwareSet], qtbot
) -> None:
    """Test _get_last_selected_hardware_set() when there is a valid value cached."""
    get_hw_sets_mock.return_value = hw_sets[0:1]
    settings_mock.value.return_value = str(hw_sets[0].file_path)
    assert _get_last_selected_hardware_set() is hw_sets[0]
    settings_mock.value.assert_called_once_with("hardware_set/selected")


@patch("finesse.gui.hardware_set.hardware_sets_view.get_hardware_sets")
@patch("finesse.gui.hardware_set.hardware_sets_view.settings")
def test_get_last_selected_hardware_set_cached_fail(
    settings_mock: Mock, get_hw_sets_mock: Mock, hw_sets: Sequence[HardwareSet], qtbot
) -> None:
    """Test _get_last_selected_hardware_set() with an unknown path cached."""
    get_hw_sets_mock.return_value = hw_sets[0:1]
    settings_mock.value.return_value = str(hw_sets[1].file_path)
    assert _get_last_selected_hardware_set() is None
    settings_mock.value.assert_called_once_with("hardware_set/selected")


@patch("finesse.gui.hardware_set.hardware_sets_view.settings")
def test_get_last_selected_hardware_set_no_cached(settings_mock: Mock, qtbot) -> None:
    """Test _get_last_selected_hardware_set() when no value is cached."""
    settings_mock.value.return_value = None
    assert _get_last_selected_hardware_set() is None
    settings_mock.value.assert_called_once_with("hardware_set/selected")


DEVICES = [
    OpenDeviceArgs.create(f"type{i}", f"class{i}", {"my_param": "my_value"})
    for i in range(2)
]


def _get_devices(indexes: Sequence[int]) -> set[OpenDeviceArgs]:
    return {DEVICES[idx] for idx in indexes}


@pytest.mark.parametrize(
    "connect_enabled,disconnect_enabled,connecting_devices,connected_devices,hardware_set",
    chain.from_iterable(
        (
            (True, False, connecting, (), range(2)),
            (False, True, connecting, range(2), range(2)),
            (True, True, connecting, (1,), range(2)),
            (False, False, connecting, (), ()),
        )
        for connecting in map(range, range(3))
    ),
)
def test_update_control_state(
    connect_enabled: bool,
    disconnect_enabled: bool,
    connecting_devices: Sequence[int],
    connected_devices: Sequence[int],
    hardware_set: Sequence[int],
    hw_control: HardwareSetsControl,
    sendmsg_mock: MagicMock,
    qtbot,
) -> None:
    """Test the _update_control_state() method."""
    # The connect button should never be enabled while any devices are still connecting
    if connecting_devices:
        connect_enabled = False

    hw_control._active_devices = _dev_to_connecting(
        _get_devices(connecting_devices)
    ) | _dev_to_connected(_get_devices(connected_devices))

    with patch(
        "finesse.gui.hardware_set.hardware_sets_view"
        ".HardwareSetsComboBox.current_hardware_set_devices",
        new_callable=PropertyMock,
    ) as hw_set_mock:
        hw_set_mock.return_value = _get_devices(hardware_set)
        with patch.object(hw_control._connect_btn, "setEnabled") as connect_enable_mock:
            with patch.object(
                hw_control._disconnect_btn, "setEnabled"
            ) as disconnect_enable_mock:
                hw_control._update_control_state()
                connect_enable_mock.assert_called_once_with(connect_enabled)
                disconnect_enable_mock.assert_called_once_with(disconnect_enabled)


@pytest.mark.parametrize(
    "connected_devices,hardware_set,open_called",
    (((), range(2), range(2)), (range(2), range(2), ()), ((0,), range(2), (1,))),
)
@patch("finesse.gui.hardware_set.hardware_sets_view.settings")
@patch("finesse.gui.hardware_set.device.open_device")
def test_connect_btn(
    open_mock: Mock,
    settings_mock: Mock,
    connected_devices: Sequence[int],
    hardware_set: Sequence[int],
    open_called: Sequence[int],
    hw_control: HardwareSetsControl,
    qtbot,
) -> None:
    """Test the connect button."""
    file_path = Path("path/test.yaml")
    with patch.object(hw_control, "_combo") as combo_mock:
        combo_mock.current_hardware_set_devices = _get_devices(hardware_set)
        combo_mock.current_hardware_set.file_path = file_path
        with patch.object(
            hw_control,
            "_active_devices",
            _dev_to_connected(_get_devices(connected_devices)),
        ):
            hw_control._connect_btn.click()

            open_mock.assert_has_calls(
                [
                    call(dev.class_name, dev.instance, dev.params)
                    for dev in _get_devices(open_called)
                ],
                any_order=True,
            )

            settings_mock.setValue.assert_called_once_with(
                "hardware_set/selected", str(file_path)
            )


def test_disconnect_button(
    hw_control: HardwareSetsControl, sendmsg_mock: Mock, qtbot
) -> None:
    """Test the disconnect button."""
    with patch.object(hw_control, "_update_control_state") as update_mock:
        with patch.object(hw_control, "_active_devices", _dev_to_connected(DEVICES)):
            hw_control._disconnect_btn.setEnabled(True)
            hw_control._disconnect_btn.click()
            sendmsg_mock.assert_has_calls(
                [call("device.close", instance=d.instance) for d in DEVICES]
            )
            update_mock.assert_called_once_with()


def test_on_device_open_start(hw_control: HardwareSetsControl, qtbot) -> None:
    """Test the _on_device_open_start() method."""
    device = DEVICES[0]
    assert not hw_control._active_devices
    hw_control._on_device_open_start(device.instance, device.class_name, device.params)
    assert hw_control._active_devices == {
        device.instance: ActiveDeviceProperties(device, ConnectionStatus.CONNECTING)
    }


@patch("finesse.gui.hardware_set.hardware_sets_view.settings")
def test_on_device_open_end(
    settings_mock: Mock, hw_control: HardwareSetsControl, qtbot
) -> None:
    """Test the _on_device_open_end() method."""
    device = DEVICES[0]
    assert not hw_control._active_devices
    hw_control._active_devices[device.instance] = ActiveDeviceProperties(
        device, ConnectionStatus.CONNECTING
    )
    with patch.object(hw_control, "_update_control_state") as update_mock:
        hw_control._on_device_open_end(
            instance=device.instance, class_name=device.class_name
        )
        assert hw_control._active_devices == {
            device.instance: ActiveDeviceProperties(device, ConnectionStatus.CONNECTED)
        }
        update_mock.assert_called_once_with()
        settings_mock.setValue.assert_has_calls(
            [
                call(f"device/type/{device.instance!s}", device.class_name),
                call(f"device/params/{device.class_name}", device.params),
            ]
        )


def test_on_device_closed(hw_control: HardwareSetsControl, qtbot) -> None:
    """Test the _on_device_closed() method."""
    device = DEVICES[0]
    assert not hw_control._active_devices
    with patch.object(hw_control, "_update_control_state") as update_mock:
        hw_control._active_devices = {
            device.instance: ActiveDeviceProperties(device, ConnectionStatus.CONNECTED)
        }
        hw_control._on_device_closed(device.instance)
        assert not hw_control._active_devices
        update_mock.assert_called_once_with()


def test_on_device_closed_not_found(hw_control: HardwareSetsControl, qtbot) -> None:
    """Test that _on_device_closed() does not raise an error if device is not found."""
    device = DEVICES[0]
    assert not hw_control._active_devices
    with does_not_raise():
        hw_control._on_device_closed(device.instance)


@patch("finesse.gui.hardware_set.hardware_sets_view.show_error_message")
def test_on_device_error(
    error_message_mock: Mock, hw_control: HardwareSetsControl, qtbot
) -> None:
    """Test the _on_device_error() method."""
    hw_control._on_device_error(DeviceInstanceRef("base_type"), RuntimeError("boo"))
    error_message_mock.assert_called_once()


def test_show_manage_devices_dialog(hw_control: HardwareSetsControl, qtbot) -> None:
    """Test the _show_manage_devices_dialog() method."""
    # Check that the dialog is created if it doesn't exist
    assert not hasattr(hw_control, "_manage_devices_dialog")
    hw_control._show_manage_devices_dialog()
    dialog = hw_control._manage_devices_dialog
    assert not dialog.isHidden()

    # If it already exists, check it is shown
    dialog.hide()
    hw_control._show_manage_devices_dialog()
    assert not dialog.isHidden()
    assert hw_control._manage_devices_dialog is dialog


def test_remove_hw_set_btn(
    hw_control: HardwareSetsControl, sendmsg_mock: Mock, qtbot
) -> None:
    """Test that _remove_hw_set_btn works."""
    with patch.object(hw_control._combo, "currentData") as data_mock:
        hw_set = MagicMock()
        data_mock.return_value = hw_set
        hw_control._remove_hw_set_btn.click()
        sendmsg_mock.assert_called_once_with("hardware_set.remove", hw_set=hw_set)
