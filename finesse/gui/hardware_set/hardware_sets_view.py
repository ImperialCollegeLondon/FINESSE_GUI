"""Provides a panel for choosing between hardware sets and (dis)connecting."""

from collections.abc import Mapping, Set
from dataclasses import dataclass
from typing import Any, cast

from frozendict import frozendict
from pubsub import pub
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from finesse.device_info import DeviceInstanceRef
from finesse.gui.error_message import show_error_message
from finesse.gui.hardware_set.device import ConnectionStatus, OpenDeviceArgs
from finesse.gui.hardware_set.device_view import DeviceControl
from finesse.gui.hardware_set.hardware_set import (
    HardwareSet,
    get_hardware_sets,
)
from finesse.gui.hardware_set.hardware_sets_combo_box import HardwareSetsComboBox
from finesse.settings import settings


@dataclass
class ActiveDeviceProperties:
    """The properties of a device that is connecting or connected."""

    args: OpenDeviceArgs
    """Arguments used to open the device."""
    state: ConnectionStatus
    """Whether the device is connecting or connected."""

    def __post_init__(self) -> None:
        """Check whether user attempted to create for a disconnected device."""
        if self.state == ConnectionStatus.DISCONNECTED:
            raise ValueError(
                "Cannot create ActiveDeviceProperties for disconnected device"
            )


def _get_last_selected_hardware_set() -> HardwareSet | None:
    last_selected_path = cast(str | None, settings.value("hardware_set/selected"))
    if not last_selected_path:
        return None

    try:
        return next(
            hw_set
            for hw_set in get_hardware_sets()
            if str(hw_set.file_path) == last_selected_path
        )
    except StopIteration:
        # No hardware set matching this path
        return None


class ManageDevicesDialog(QDialog):
    """A dialog for manually opening, closing and configuring devices."""

    def __init__(self, connected_devices: Set[OpenDeviceArgs]) -> None:
        """Create a new ManageDevicesDialog.

        Args:
            connected_devices: Which devices are already connected
        """
        super().__init__()
        self.setWindowTitle("Manage devices")
        self.setModal(True)

        layout = QVBoxLayout()
        layout.addWidget(DeviceControl(connected_devices))
        self.setLayout(layout)


class HardwareSetsControl(QGroupBox):
    """A panel for choosing between hardware sets and (dis)connecting."""

    def __init__(self) -> None:
        """Create a new HardwareSetsControl."""
        super().__init__("Hardware set")

        self._active_devices: dict[DeviceInstanceRef, ActiveDeviceProperties] = {}
        pub.subscribe(self._on_device_open_start, "device.before_opening")
        pub.subscribe(self._on_device_open_end, "device.after_opening")
        pub.subscribe(self._on_device_closed, "device.closed")
        pub.subscribe(self._on_device_error, "device.error")

        self._combo = HardwareSetsComboBox()
        """A combo box for the different hardware sets."""
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        if last_selected := _get_last_selected_hardware_set():
            self._combo.current_hardware_set = last_selected

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self._connect_btn.pressed.connect(self._on_connect_btn_pressed)
        self._disconnect_btn = QPushButton("Disconnect all")
        self._disconnect_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self._disconnect_btn.pressed.connect(self._on_disconnect_btn_pressed)

        self._remove_hw_set_btn = QPushButton("Remove")
        self._remove_hw_set_btn.pressed.connect(self._remove_current_hardware_set)

        manage_devices_btn = QPushButton("Manage devices")
        manage_devices_btn.pressed.connect(self._show_manage_devices_dialog)
        self._manage_devices_dialog: ManageDevicesDialog

        row1 = QHBoxLayout()
        row1.addWidget(self._combo)
        row1.addWidget(self._connect_btn)
        row1.addWidget(self._disconnect_btn)
        row2 = QHBoxLayout()
        row2.addWidget(self._remove_hw_set_btn)
        row2.addWidget(manage_devices_btn)

        layout = QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        self.setLayout(layout)

        self._update_control_state()

        self._combo.currentIndexChanged.connect(self._update_control_state)

    def _get_connected_devices(self) -> set[OpenDeviceArgs]:
        """Get active devices which are connected (not connecting)."""
        return set(
            props.args
            for props in self._active_devices.values()
            if props.state == ConnectionStatus.CONNECTED
        )

    def _remove_current_hardware_set(self) -> None:
        """Remove the currently selected hardware set."""
        pub.sendMessage("hardware_set.remove", hw_set=self._combo.current_hardware_set)

    def _show_manage_devices_dialog(self) -> None:
        """Show a dialog for managing devices manually.

        The dialog is created lazily.
        """
        if not hasattr(self, "_manage_devices_dialog"):
            self._manage_devices_dialog = ManageDevicesDialog(
                self._get_connected_devices()
            )

        self._manage_devices_dialog.show()

    def _update_control_state(self) -> None:
        """Enable or disable the connect and disconnect buttons as appropriate."""
        # Enable the "Connect" button if there are any devices left to connect for this
        # hardware set
        connected_devices = self._get_connected_devices()
        all_connected = connected_devices.issuperset(
            self._combo.current_hardware_set_devices
        )
        any_devices_connecting = len(connected_devices) < len(self._active_devices)
        self._connect_btn.setEnabled(not any_devices_connecting and not all_connected)

        # Enable the "Disconnect all" button if there are *any* devices connected at all
        self._disconnect_btn.setEnabled(bool(connected_devices))

        # Enable the "Remove" button only if the hardware set is not a built in one
        hw_set = self._combo.current_hardware_set
        self._remove_hw_set_btn.setEnabled(hw_set is not None and not hw_set.built_in)

    def _on_connect_btn_pressed(self) -> None:
        """Connect to all devices in current hardware set.

        If a device has already been opened with the same type and parameters, then we
        skip it. If a device of the same type but with different parameters has been
        opened, then it will be closed as we open the new device.
        """
        # Something in the combo box will have been selected, so it won't be None
        path = self._combo.current_hardware_set.file_path  # type: ignore[union-attr]

        # Remember which hardware set was selected for next time we run the program
        settings.setValue(
            "hardware_set/selected",
            str(path),
        )

        # Open each of the devices in turn
        for device in self._combo.current_hardware_set_devices.difference(
            self._active_devices
        ):
            device.open()

        self._update_control_state()

    def _on_disconnect_btn_pressed(self) -> None:
        """Disconnect from all devices in current hardware set."""
        # We need to make a copy because keys will be removed as we close devices
        for device in list(self._active_devices.keys()):
            pub.sendMessage("device.close", instance=device)

        self._update_control_state()

    def _on_device_open_start(
        self, instance: DeviceInstanceRef, class_name: str, params: Mapping[str, Any]
    ) -> None:
        """Store device open parameters and update GUI."""
        args = OpenDeviceArgs(instance, class_name, frozendict(params))
        dev_props = ActiveDeviceProperties(args, ConnectionStatus.CONNECTING)
        self._active_devices[instance] = dev_props

        self._update_control_state()

    def _on_device_open_end(self, instance: DeviceInstanceRef, class_name: str) -> None:
        """Add instance to _connected_devices and update GUI."""
        dev_props = self._active_devices[instance]
        dev_props.state = ConnectionStatus.CONNECTED
        assert dev_props.args.class_name == class_name

        # Remember last opened device
        settings.setValue(f"device/type/{instance!s}", class_name)
        if dev_props.args.params:
            settings.setValue(f"device/params/{class_name}", dev_props.args.params)

        self._update_control_state()

    def _on_device_closed(self, instance: DeviceInstanceRef) -> None:
        """Remove instance from _connected devices and update GUI."""
        try:
            # Remove the device matching this instance type (there should be only one)
            del self._active_devices[instance]
        except KeyError:
            # No device of this type found
            pass
        else:
            self._update_control_state()

    def _on_device_error(
        self, instance: DeviceInstanceRef, error: BaseException
    ) -> None:
        """Show an error message when something has gone wrong with the device.

        Todo:
            The name of the device isn't currently very human readable.
        """
        show_error_message(
            self,
            f"A fatal error has occurred with the {instance!s} device: {error!s}",
            title="Device error",
        )
