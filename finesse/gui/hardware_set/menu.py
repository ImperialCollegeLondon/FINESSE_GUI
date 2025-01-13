"""Provides a menu for working with hardware sets."""

from PySide6.QtWidgets import QMenu


class HardwareSetsMenu(QMenu):
    """A menu for performing operations on hardware sets."""

    def __init__(self) -> None:
        """Create a new HardwareSetsMenu."""
        super().__init__("Hardware sets")
