"""Provides the base class for stepper motor implementations."""
from abc import abstractmethod
from typing import Optional, Union

from pubsub import pub

from ...config import ANGLE_PRESETS, STEPPER_MOTOR_TOPIC
from ..device_base import DeviceBase


class StepperMotorBase(DeviceBase):
    """A base class for stepper motor implementations."""

    def __init__(self) -> None:
        """Create a new StepperMotorBase.

        Subscribe to stepper.move messages.
        """
        pub.subscribe(
            self._move_to,
            f"serial.{STEPPER_MOTOR_TOPIC}.move.begin",
        )
        pub.subscribe(self._stop_moving, f"serial.{STEPPER_MOTOR_TOPIC}.stop")
        pub.subscribe(
            self._notify_on_stopped, f"serial.{STEPPER_MOTOR_TOPIC}.notify_on_stopped"
        )

    @staticmethod
    def send_error_message(error: BaseException) -> None:
        """Send an error message when a device error has occurred."""
        pub.sendMessage(f"serial.{STEPPER_MOTOR_TOPIC}.error", error=error)

    @staticmethod
    def preset_angle(name: str) -> float:
        """Get the angle for one of the preset positions.

        Args:
            name: Name of preset angle

        Returns:
            The angle in degrees
        """
        try:
            return ANGLE_PRESETS[name]
        except KeyError as e:
            raise ValueError(f"{name} is not a valid preset") from e

    @property
    @abstractmethod
    def steps_per_rotation(self) -> int:
        """The number of steps that correspond to a full rotation."""

    @property
    @abstractmethod
    def step(self) -> int:
        """The current state of the device's step counter."""

    @step.setter
    @abstractmethod
    def step(self, step: int) -> None:
        """Move the stepper motor to the specified absolute position.

        Args:
            step: Which step position to move to
        """

    @abstractmethod
    def stop_moving(self) -> None:
        """Immediately stop moving the motor."""

    @abstractmethod
    def wait_until_stopped(self, timeout: Optional[float] = None) -> None:
        """Wait until the motor has stopped moving.

        Args:
            timeout: Time to wait for motor to finish moving (None == forever)
        """

    @abstractmethod
    def notify_on_stopped(self) -> None:
        """Wait until the motor has stopped moving and send a message when done.

        The message is stepper.move.end.
        """

    @property
    def angle(self) -> float:
        """The current angle of the motor in degrees."""
        return self.step * 360.0 / self.steps_per_rotation

    def move_to(self, target: Union[float, str]) -> None:
        """Move the motor to a specified rotation and send message when complete.

        Sends a stepper.move.end message when finished.

        Args:
            target: The target angle (in degrees) or the name of a preset
        """
        if isinstance(target, str):
            target = self.preset_angle(target)

        if target < 0.0 or target > 270.0:
            raise ValueError("Angle must be between 0° and 270°")

        self.step = round(self.steps_per_rotation * target / 360.0)

    def _move_to(self, target: Union[float, str]) -> None:
        try:
            self.move_to(target)
        except Exception as error:
            self.send_error_message(error)

    def _stop_moving(self) -> None:
        try:
            self.stop_moving()
        except Exception as error:
            self.send_error_message(error)

    def _notify_on_stopped(self) -> None:
        try:
            self.notify_on_stopped()
        except Exception as error:
            self.send_error_message(error)
