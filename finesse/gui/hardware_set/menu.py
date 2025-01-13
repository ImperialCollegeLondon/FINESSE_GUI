"""Provides a menu for working with hardware sets."""

from pathlib import Path

from pubsub import pub
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMenu

from finesse.gui.error_message import show_error_message
from finesse.gui.hardware_set.hardware_set import HardwareSet

from finesse.gui.hardware_set.hardware_set import get_hardware_sets


class HardwareSetsMenu(QMenu):
    """A menu for performing operations on hardware sets."""

    def __init__(self) -> None:
        """Create a new HardwareSetsMenu."""
        super().__init__("Hardware sets")

        import_action = QAction("Import from file", self)
        import_action.triggered.connect(self._import_hardware_set)
        self.addAction(import_action)

        self._remove_menu = QMenu("Remove hardware set")
        self._remove_menu.aboutToShow.connect(self._update_remove_menu)
        self.addMenu(self._remove_menu)

    def _import_hardware_set(self) -> None:
        """Import a hardware set from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import hardware set config file", filter="*.yaml"
        )
        if not file_path:
            return

        try:
            hw_set = HardwareSet.load(Path(file_path))
        except Exception:
            show_error_message(
                self,
                "Could not load hardware set config file. Is it in the correct format?",
                "Could not load config file",
            )
        else:
            pub.sendMessage("hardware_set.add", hw_set=hw_set)

    def _update_remove_menu(self) -> None:
        self._remove_menu.clear()

        for hw_set in get_hardware_sets():
            action = QAction(str(hw_set), self)
            self._remove_menu.addAction(action)
