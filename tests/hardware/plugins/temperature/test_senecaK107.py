"""Tests for the Seneca K107 device."""
from unittest.mock import MagicMock, patch

import numpy
import pytest

from finesse.hardware.plugins.temperature.senecak107 import SenecaK107, SenecaK107Error

_SERIAL_ARGS = ("0403:6001 AB0LMVI5A", 57600)


@pytest.fixture
def dev(serial_mock: MagicMock) -> SenecaK107:
    """Get an instance of a Seneca K107 object."""
    return SenecaK107(*_SERIAL_ARGS)


@pytest.fixture
def data() -> bytes:
    """Get raw test data."""
    return b"\x01\x03\x101d1p\xff\xfa\xff\xf81u\xff\xfa1d\xff\xfa]Z"


def test_init(serial_mock: MagicMock) -> None:
    """Test Seneca K107's constructor."""
    # Test default values
    dev = SenecaK107(*_SERIAL_ARGS)
    assert dev.MIN_TEMP == -80
    assert dev.MAX_TEMP == 105
    assert dev.MIN_MILLIVOLT == 4
    assert dev.MAX_MILLIVOLT == 20

    # Test arg values
    dev = SenecaK107(*_SERIAL_ARGS, 1, 2, 3, 4)
    assert dev.MIN_TEMP == 1
    assert dev.MAX_TEMP == 2
    assert dev.MIN_MILLIVOLT == 3
    assert dev.MAX_MILLIVOLT == 4


def test_write(dev: SenecaK107) -> None:
    """Test SenecaK107.write()."""
    dev.request_read()
    dev.serial.write.assert_called_once_with(bytearray([1, 3, 0, 2, 0, 8, 229, 204]))


def test_write_error(dev: SenecaK107) -> None:
    """Test SenecaK107.write() error handling."""
    dev.serial.write.side_effect = RuntimeError
    with pytest.raises(SenecaK107Error):
        dev.request_read()


def test_read(dev: SenecaK107, data: bytes) -> None:
    """Test SenecaK107.read()."""
    with patch.object(dev.serial, "read") as mock:
        mock.return_value = data
        assert data == dev.read()
        mock.assert_called_once()


@pytest.mark.parametrize(
    "message",
    (
        b"\x01\x03\x101d1p\xff\xfa\xff\xf81u\xff\xfa1d\xff",
        b"\x01\x03\x101d1p\xff\xfa\xff\xf81u\xff\xfa1d\xff\xfa]Z\x01\x03",
    ),
)
def test_read_error(dev: SenecaK107, message: bytes) -> None:
    """Test SenecaK107.read() error handling."""
    with pytest.raises(SenecaK107Error):
        with patch.object(dev.serial, "read") as mock:
            mock.return_value = message
            dev.read()


def test_parse_data(dev: SenecaK107, data: bytes) -> None:
    """Test SenecaK107.parse_data()."""
    expected = [
        19.946250000000006,
        20.085000000000008,
        631.4406250000001,
        631.4175,
        20.14281249999999,
        631.4406250000001,
        19.946250000000006,
        631.4406250000001,
    ]
    parsed = dev.parse_data(data)

    assert numpy.allclose(parsed, expected)