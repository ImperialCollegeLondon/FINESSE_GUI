"""Panel and widgets related to monitoring the interferometer."""

from collections.abc import Sequence

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from finesse.config import SENSORS_TOPIC
from finesse.gui.device_panel import DevicePanel
from finesse.gui.led_icon import LEDIcon
from finesse.sensor_reading import SensorReading


class SensorsPanel(DevicePanel):
    """Panel containing widgets to view sensor readings."""

    def __init__(self) -> None:
        """Create a new SensorsPanel."""
        super().__init__(SENSORS_TOPIC, "Sensor readings")

        self._val_lineedits: dict[str, QLineEdit] = {}

        self._poll_light = LEDIcon.create_green_icon()

        self._create_layouts()

        self._poll_wid_layout.addWidget(QLabel("POLL Server"))
        self._poll_wid_layout.addWidget(self._poll_light)
        self._poll_light.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.setLayout(self._layout)

        # Listen for properties sent by backend
        pub.subscribe(self._on_properties_received, f"device.{SENSORS_TOPIC}.data")

    def _create_layouts(self) -> None:
        """Creates layouts to house the widgets."""
        self._poll_wid_layout = QHBoxLayout()
        self._prop_wid_layout = QGridLayout()

        top = QWidget()
        top.setLayout(self._prop_wid_layout)
        bottom = QWidget()
        bottom.setLayout(self._poll_wid_layout)

        self._layout = QVBoxLayout()
        self._layout.addWidget(top)
        self._layout.addWidget(bottom)

    def _get_prop_lineedit(self, prop: SensorReading) -> QLineEdit:
        """Create and populate the widgets for displaying a given property.

        Args:
            prop: the property to display

        Returns:
            QLineEdit: the QLineEdit widget corresponding to the property
        """
        if prop.description not in self._val_lineedits:
            prop_label = QLabel(prop.description)
            prop_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            val_lineedit = QLineEdit()
            val_lineedit.setReadOnly(True)
            val_lineedit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lineedit.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
            )

            self._val_lineedits[prop.description] = val_lineedit

            num_props = len(self._val_lineedits)
            self._prop_wid_layout.addWidget(prop_label, num_props, 0)
            self._prop_wid_layout.addWidget(val_lineedit, num_props, 1)

        return self._val_lineedits[prop.description]

    def _on_properties_received(self, readings: Sequence[SensorReading]):
        """Receive the data table from the backend and update the GUI.

        Args:
            readings: the latest sensor readings received
        """
        self._poll_light.flash()
        for prop in readings:
            lineedit = self._get_prop_lineedit(prop)
            lineedit.setText(prop.val_str())
