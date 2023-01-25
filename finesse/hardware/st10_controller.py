"""Code for interfacing with the ST10-Q-NN stepper motor controller.

Applied Motions have their own bespoke programming language ("Q") for interfacing with
their devices, of which we're only using a small portion here.

The specification is available online:
    https://appliedmotion.s3.amazonaws.com/Host-Command-Reference_920-0002W_0.pdf
"""

import logging
from typing import Any, Optional

from serial import Serial, SerialException, SerialTimeoutException

from .stepper_motor_base import StepperMotorBase


class ST10ControllerError(SerialException):
    """Indicates that an error has occurred with the ST10 controller."""


class ST10Controller(StepperMotorBase):
    """An interface for the ST10-Q-NN stepper motor controller.

    This class allows for moving the mirror to arbitrary positions and retrieving its
    current position.
    """

    STEPS_PER_ROTATION = 50800
    """The total number of steps in one full rotation of the mirror."""

    def __init__(self, serial: Serial) -> None:
        """Create a new ST10Controller.

        Args:
            serial: The serial device to communicate with the ST10 controller

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        self.serial = serial

        # Check that we are connecting to an ST10
        self._check_device_id()

        # Move mirror to home position
        self.home()

        super().__init__()

    @staticmethod
    def create(
        port: str,
        baudrate: int = 9600,
        timeout: float = 1.0,
        *serial_args: Any,
        **serial_kwargs: Any,
    ):
        """Create a new ST10Controller with the specified serial device properties.

        Args:
            port: Serial port name
            baudrate: Serial port baudrate
            timeout: How long to wait for read operations (seconds)
            serial_args: Extra arguments to Serial constructor
            serial_kwargs: Extra keyword arguments to Serial constructor
        """
        if "write_timeout" not in serial_kwargs:
            serial_kwargs["write_timeout"] = timeout

        serial = Serial(port, baudrate, *serial_args, timeout=timeout, **serial_kwargs)
        return ST10Controller(serial)

    def __del__(self) -> None:
        """Leave mirror facing downwards when finished.

        This prevents dust accumulating.
        """
        try:
            self.move_to("nadir")
        except Exception as e:
            logging.error(f"Failed to reset mirror to downward position: {e}")

    def _check_device_id(self) -> None:
        """Check that the ID is the correct one for an ST10.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: The device ID is not for an ST10
        """
        self._write("MV")
        if self._read() != "107F024":
            raise ST10ControllerError("Device ID indicates this is not an ST10")

    def _get_input_status(self, index: int) -> bool:
        """Read the value of the device's input status.

        The input status is a boolean array represented as zeros and ones. I don't know
        what it actually corresponds to on the device, but it is used in a couple of
        places in the old program.

        Args:
            index: Which boolean value in the input status array to check
        """
        input_status = self._request_value("IS")
        return input_status[index] == "1"

    @property
    def steps_per_rotation(self) -> int:
        """Get the number of steps that correspond to a full rotation."""
        return self.STEPS_PER_ROTATION

    def home(self) -> None:
        """Return the stepper motor to its home position.

        The device's internal counter is also reset to zero.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        # If the third (boolean) value of the input status array is set, then move the
        # motor first. I don't know what the input status actually means, but this is
        # how it was done in the old program, so I'm copying it here.
        if self._get_input_status(3):
            self._relative_move(-5000)

        # Send home command; leaves mirror facing upwards
        self._write_check("SH6H")

        # Turn mirror so it's facing down
        self._relative_move(-30130)

        # Tell the controller that this is step 0
        self._write_check("SP0")

    def _relative_move(self, steps: int) -> None:
        """Move the stepper motor to the specified relative position.

        Args:
            steps: Number of steps to move by

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        self._write_check(f"FL{steps}")

    @property
    def step(self) -> int:
        """The current state of the device's step counter.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        step = self._request_value("SP")
        try:
            return int(step)
        except ValueError:
            raise ST10ControllerError(f"Invalid value for step received: {step}")

    @step.setter
    def step(self, step: int) -> None:
        """Move the stepper motor to the specified absolute position.

        Args:
            step: Which step position to move to

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        self._write_check(f"FP{step}")

    def _send_string(self, string: str) -> None:
        """Request that the device sends string when operations have completed.

        Args:
            string: String to be returned by the device
        """
        self._write_check(f"SS{string}")

    def _read(self) -> str:
        """Read the next message from the device.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        raw = self.serial.read_until(b"\r")

        # Check that it hasn't timed out
        if not raw:
            raise SerialTimeoutException()

        logging.debug(f"(ST10) <<< {repr(raw)}")

        try:
            return raw[:-1].decode("ascii")
        except UnicodeDecodeError:
            raise ST10ControllerError(f"Invalid message received: {repr(raw)}")

    def _write(self, message: str) -> None:
        """Send the specified message to the device.

        Raises:
            SerialException: Error communicating with device
            UnicodeEncodeError: Malformed message
        """
        data = f"{message}\r".encode("ascii")
        logging.debug(f"(ST10) >>> {repr(data)}")
        self.serial.write(data)

    def _write_check(self, message: str) -> None:
        """Send the specified message and check whether the device returns an error.

        Args:
            message: ASCII-formatted message

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
            UnicodeEncodeError: Message to be sent is malformed
        """
        self._write(message)
        self._check_response()

    def _check_response(self) -> None:
        """Check whether the device has returned an error.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        response = self._read()

        # These values are referred to as "ack" and "qack" in the old program (nack is
        # "?"). I don't know what qack is. Could it mean clockwise/anticlockwise
        # movement?
        if response == "%" or response == "*":
            return

        # An error occurred
        if response[0] == "?":
            raise ST10ControllerError(
                f"Device returned an error (code: {response[1:]})"
            )

        raise ST10ControllerError(f"Unexpected response from device: {response}")

    def _request_value(self, name: str) -> str:
        """Request a named value from the device.

        You can request the values of various variables, which all seem to have
        two-letter names.

        Args:
            name: Variable name

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
            UnicodeEncodeError: Message to be sent is malformed
        """
        self._write(name)
        response = self._read()
        if not response.startswith(f"{name}="):
            raise ST10ControllerError(f"Unexpected response when querying value {name}")

        return response[len(name) + 1 :]

    def wait_until_stopped(self, timeout: Optional[float] = None) -> None:
        """Wait until the motor has stopped moving.

        Args:
            timeout: Time to wait for motor to finish moving (None == forever)

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for motor to finish moving
            ST10ControllerError: Malformed message received from device
        """
        # Tell device to send "X" when current operations are complete
        self._send_string("X")

        # Set temporary timeout
        old_timeout, self.serial.timeout = self.serial.timeout, timeout
        try:
            if self._read() != "X":
                raise ST10ControllerError(
                    "Invalid response received when waiting for X"
                )
        finally:
            # Restore previous timeout setting
            self.serial.timeout = old_timeout


if __name__ == "__main__":
    import sys

    print(f"Connecting to device {sys.argv[1]}...")
    dev = ST10Controller.create(sys.argv[1])
    print("Done. Homing...")

    dev.wait_until_stopped()
    print("Homing complete")
    print(f"Current angle: {dev.angle}°")

    angles = (0.0, 90.0, 180.0, "hot_bb")
    for ang in angles:
        print(f"Moving to {ang}")
        dev.move_to(ang)
        dev.wait_until_stopped()
        print(f"Current angle: {dev.angle}°")
