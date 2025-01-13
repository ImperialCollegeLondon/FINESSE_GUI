"""Code for FINESSE's main GUI window."""

from pubsub import pub
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from finesse.config import (
    APP_NAME,
    APP_VERSION,
    TEMPERATURE_MONITOR_COLD_BB_IDX,
    TEMPERATURE_MONITOR_HOT_BB_IDX,
)
from finesse.gui.data_file_view import DataFileControl
from finesse.gui.docs_view import DocsViewer
from finesse.gui.hardware_set.hardware_sets_view import HardwareSetsControl
from finesse.gui.hardware_set.menu import HardwareSetsMenu
from finesse.gui.logs_view import LogLocationOpen, LogOpen
from finesse.gui.measure_script.script_view import ScriptControl
from finesse.gui.sensors_panel import SensorsPanel
from finesse.gui.spectrometer_view import SpectrometerControl
from finesse.gui.stepper_motor_view import StepperMotorControl
from finesse.gui.temperature_controller_view import TemperatureControllerControl
from finesse.gui.temperature_monitor_view import TemperatureMonitorControl
from finesse.gui.temperature_plot import TemperaturePlot
from finesse.gui.uncaught_exceptions import set_uncaught_exception_handler


class MainWindow(QMainWindow):
    """The main window for FINESSE."""

    def __init__(self) -> None:
        """Create a new MainWindow."""
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")

        set_uncaught_exception_handler(self)

        hw_sets_menu = HardwareSetsMenu()
        self.menuBar().addMenu(hw_sets_menu)

        open_log = LogOpen(self)
        open_log_location = LogLocationOpen(self)
        logsmenu = QMenu("Logs", self)
        logsmenu.addAction(open_log)
        logsmenu.addAction(open_log_location)
        self.menuBar().addMenu(logsmenu)

        docs_viewer = DocsViewer(self)
        helpmenu = QMenu("Help", self)
        helpmenu.addAction(docs_viewer)
        self.menuBar().addMenu(helpmenu)

        layout_left = QVBoxLayout()

        # For choosing hardware set
        hardware_sets = HardwareSetsControl()

        # Setup for measure script panel
        measure_script = ScriptControl()

        # Setup for stepper motor control
        stepper_motor = StepperMotorControl()

        # Setup for spectrometer
        spectrometer: QGroupBox = SpectrometerControl()

        # Setup for interferometer monitor
        sensors = SensorsPanel()
        sensors.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Setup for data file widgets
        data_file = DataFileControl()

        mid_left_layout = QHBoxLayout()
        mid_left_layout.addWidget(stepper_motor)
        mid_left_layout.addWidget(spectrometer)

        layout_left.addWidget(hardware_sets)
        layout_left.addWidget(measure_script)
        layout_left.addLayout(mid_left_layout)
        layout_left.addWidget(sensors)
        layout_left.addWidget(data_file)

        layout_right = QGridLayout()

        bb_monitor: QGroupBox = TemperaturePlot()
        temp_monitor: QGroupBox = TemperatureMonitorControl()
        tc_hot: QGroupBox = TemperatureControllerControl(
            "hot", TEMPERATURE_MONITOR_HOT_BB_IDX, allow_update=True
        )
        tc_cold: QGroupBox = TemperatureControllerControl(
            "cold", TEMPERATURE_MONITOR_COLD_BB_IDX, allow_update=False
        )

        layout_right.addWidget(bb_monitor, 1, 0, 1, 2)
        layout_right.addWidget(temp_monitor, 2, 0, 1, 2)
        layout_right.addWidget(tc_hot, 3, 0, 1, 1)
        layout_right.addWidget(tc_cold, 3, 1, 1, 1)

        # Display widgets in two columns
        left = QWidget()
        left.setLayout(layout_left)
        right = QWidget()
        right.setLayout(layout_right)
        layout = QHBoxLayout()
        layout.addWidget(left)
        layout.addWidget(right)

        central = QWidget()
        central.setLayout(layout)

        self.setCentralWidget(central)

    def showEvent(self, event: QShowEvent) -> None:
        """Send window.opened message."""
        pub.sendMessage("window.opened")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Send window.closed message."""
        pub.sendMessage("window.closed")
