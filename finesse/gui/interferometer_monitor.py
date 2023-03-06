"""Panel and widgets related to monitoring the interferometer."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .led_icons import LEDIcon


@dataclass
class EM27Property:
    """Class for representing EM27 monitored properties.

    Args:
        name: name of the physical quantity
        value: value of the physical quantity
        unit: unit in which the value is presented
    """

    name: str
    value: Decimal
    unit: str


def get_vals_from_server() -> list[EM27Property]:
    """Placeholder function for retrieving interferometer properties.

    Returns:
        data_table: A list containing the physical properties being monitored
    """
    data_table = [
        EM27Property("PSF27 Temp", Decimal(28.151062), "deg. C"),
        EM27Property("Cryo Temp", Decimal(0.0), "deg. K"),
        EM27Property("Blackbody Hum", Decimal(2.463968), "%"),
        EM27Property("Source Temp", Decimal(70.007156), "deg. C"),
        EM27Property("Aux Volt", Decimal(6.285875), "V"),
        EM27Property("Aux Curr", Decimal(0.910230), "A"),
        EM27Property("Laser Curr", Decimal(0.583892), "A"),
    ]
    return data_table


class EM27Monitor(QGroupBox):
    """Panel containing widgets to view the EM27 properties."""

    def __init__(self) -> None:
        """Creates the attributes required to view properties monitored by the EM27."""
        super().__init__("EM27 SOH Monitor")

        self._prop_names: list[str] = []
        self._val_lineedits: Dict[str, QLineEdit] = {}
        self._data_table: list[EM27Property] = []

        self._poll_light = LEDIcon.create_poll_icon()
        self._poll_light._timer.timeout.connect(self.poll_server)  # type: ignore
        self._poll_light._timer.start(2000)

        self._poll_wid_layout = QHBoxLayout()
        self._poll_wid_layout.addWidget(QLabel("POLL Server"))
        self._poll_wid_layout.addWidget(self._poll_light)
        self._poll_light.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed  # type: ignore
        )

        self._prop_wid_layout = QGridLayout()
        top = QWidget()
        top.setLayout(self._prop_wid_layout)
        bottom = QWidget()
        bottom.setLayout(self._poll_wid_layout)

        self._layout = QVBoxLayout()
        self._layout.addWidget(top)
        self._layout.addWidget(bottom)
        self.setLayout(self._layout)

    def _display_props(self) -> None:
        """Creates and populates the widgets to view the EM27 properties."""
        for prop in self._data_table:
            if prop.name not in self._prop_names:
                num_props = len(self._prop_names)

                # Update list of monitored properties and create corresponding label
                self._prop_names.append(prop.name)
                prop_label = QLabel(prop.name)
                self._prop_wid_layout.addWidget(prop_label, num_props, 0)

                # Create corresponding box to display value and unit
                val_lineedit = QLineEdit()
                val_lineedit.setText(f"{prop.value:.6f} {prop.unit}")
                val_lineedit.setReadOnly(True)
                val_lineedit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._val_lineedits[prop.name] = val_lineedit
                self._prop_wid_layout.addWidget(val_lineedit, num_props, 1)
            else:
                self._val_lineedits[prop.name].setText(f"{prop.value:.6f} {prop.unit}")

    def poll_server(self) -> None:
        """Polls the server to obtain the latest values."""
        self._poll_light._flash()
        self._data_table = get_vals_from_server()
        self._display_props()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    window = QMainWindow()
    em27_monitor = EM27Monitor()

    window.setCentralWidget(em27_monitor)
    window.show()
    app.exec()
