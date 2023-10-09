"""Tests for the interface to the TC4820 device."""
from contextlib import nullcontext as does_not_raise
from decimal import Decimal
from itertools import chain
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture
from serial import SerialException

from finesse.config import TEMPERATURE_CONTROLLER_TOPIC
from finesse.hardware.plugins.temperature.tc4820 import TC4820, MalformedMessageError


@pytest.fixture
def dev(mocker: MockerFixture) -> TC4820:
    """Get an instance of a TC4820 object."""
    serial = mocker.patch("serial.Serial")
    return TC4820(serial, "hot_bb")


@pytest.mark.parametrize("name", ("hot_bb", "cold_bb"))
def test_init(name: str, subscribe_mock: MagicMock) -> None:
    """Test TC4820's constructor."""
    dev = TC4820(MagicMock(), name)
    assert dev.max_attempts == 3
    subscribe_mock.assert_any_call(
        dev._request_properties, f"device.{TEMPERATURE_CONTROLLER_TOPIC}.{name}.request"
    )
    subscribe_mock.assert_any_call(
        dev._change_set_point,
        f"device.{TEMPERATURE_CONTROLLER_TOPIC}.{name}.change_set_point",
    )


def test_get_properties(dev: TC4820) -> None:
    """Test the get_properties() method."""
    expected = {
        "power": 0,
        "alarm_status": 0,
        "temperature": Decimal(0),
        "set_point": Decimal(0),
    }

    with patch.object(dev, "request_int") as mock_int:
        mock_int.return_value = 0
        assert dev.get_properties() == expected


def checksum(message: int) -> int:
    """Calculate the checksum as an int."""
    return sum(f"{message:0{4}x}".encode("ascii")) & 0xFF


def format_message(message: int, checksum: int, eol: str = "^") -> bytes:
    """Format the message as the device would."""
    assert 0 <= checksum <= 0xFF
    return f"*{message:0{4}x}{checksum:0{2}x}{eol}".encode("ascii")


_MESSAGE = "012345678"


def _get_message(len: int) -> tuple[int, bytes, Any]:
    substr = _MESSAGE[:len]
    value = int(substr, base=16)
    return (
        value,
        f"*{substr}{checksum(value):0{2}x}^".encode("ascii"),
        does_not_raise() if len == 4 else pytest.raises(MalformedMessageError),
    )


_TERM_CHARS = set("*^")
"""Some random ASCII characters, plus the correct start and terminator chars."""

for c in range(0, 128, 10):
    _TERM_CHARS.add(chr(c))


@pytest.mark.parametrize(
    "value,message,raises",
    chain(
        # This is a special message indicating that we provided a bad checksum to the
        # device
        [(0, b"*XXXX60^", pytest.raises(MalformedMessageError))],
        # Non-hex value for number
        [(0, b"*$$$$90^", pytest.raises(MalformedMessageError))],
        # Check that only valid start and end terminators work
        [
            (
                0,
                f"{start}0000c0{end}".encode("ascii"),
                does_not_raise()
                if start == "*" and end == "^"
                else pytest.raises(MalformedMessageError),
            )
            for end in _TERM_CHARS
            for start in _TERM_CHARS
        ],
        # Message length
        [_get_message(len) for len in range(1, len(_MESSAGE))],
        # Test checksums
        [
            (
                value,
                format_message(value, csum),
                does_not_raise()
                if checksum(value) == csum
                else pytest.raises(MalformedMessageError),
            )
            for value in (0x0000, 0x1234, 0x5678)
            for csum in range(0x100)
        ],
    ),
)
def test_read(
    value: int, message: bytes, raises: Any, dev: TC4820, mocker: MockerFixture
) -> None:
    """Test TC4820.read()."""
    with raises:
        m = mocker.patch("serial.Serial.read_until", return_value=message)
        assert value == dev.read()
        m.assert_called_once_with(b"^", size=8)


@pytest.mark.parametrize("value", range(0, 0xFFFF, 200))
def test_write(value: int, dev: TC4820, mocker: MockerFixture) -> None:
    """Test TC4820.write()."""
    str_value = f"{value:0{4}x}"
    m = mocker.patch("serial.Serial.write")
    dev.write(str_value)
    m.assert_called_once_with(format_message(value, checksum(value), eol="\r"))


@pytest.mark.parametrize(
    "max_attempts,fail_max,raises",
    [
        (
            max_attempts,
            fail_max,
            pytest.raises(SerialException)
            if fail_max >= max_attempts
            else does_not_raise(),
        )
        for fail_max in range(5)
        for max_attempts in range(1, 5)
    ],
)
def test_request_int(
    max_attempts: int, fail_max: int, raises: Any, mocker: MockerFixture
) -> None:
    """Test TC4820.request_int().

    Check that the retrying of requests works.
    """
    serial = mocker.patch("serial.Serial")
    dev = TC4820(serial, "hot_bb", max_attempts)

    fail_count = 0

    def my_read():
        """Raise an error the first fail_count times called."""
        nonlocal fail_count
        if fail_count < fail_max:
            fail_count += 1
            raise MalformedMessageError()

        return 0

    mocker.patch.object(dev, "read", my_read)
    write = mocker.patch("finesse.hardware.plugins.temperature.tc4820.TC4820.write")
    with raises:
        assert dev.request_int("some string") == 0

    write.assert_called_with("some string")


@pytest.mark.parametrize(
    "name,command,type",
    [
        ("temperature", "010000", "decimal"),
        ("power", "020000", "int"),
        ("alarm_status", "030000", "int"),
        ("set_point", "500000", "decimal"),
    ],
)
def test_property_getters(
    name: str, command: str, type: str, dev: TC4820, mocker: MockerFixture
) -> None:
    """Check that the getters for properties work."""
    m = mocker.patch(
        f"finesse.hardware.plugins.temperature.tc4820.TC4820.request_{type}"
    )
    getattr(dev, name)
    m.assert_called_once_with(command)
