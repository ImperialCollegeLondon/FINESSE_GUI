"""Tests for the interface to the EM27's OPUS control program."""
from itertools import product
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtNetwork import QNetworkReply

from finesse.config import OPUS_IP
from finesse.hardware.plugins.spectrometer.opus_interface import (
    OPUSError,
    OPUSInterface,
    parse_response,
)
from finesse.spectrometer_status import SpectrometerStatus


@pytest.fixture
def opus(qtbot) -> OPUSInterface:
    """Fixture for OPUSInterface."""
    return OPUSInterface()


def test_request_status(opus: OPUSInterface, qtbot) -> None:
    """Test OPUSInterface's request_status() method."""
    with patch.object(opus, "_requester") as requester_mock:
        opus.request_command("status")
        assert requester_mock.make_request.call_count == 1
        assert (
            requester_mock.make_request.call_args[0][0]
            == f"http://{OPUS_IP}/opusrs/stat.htm"
        )


def test_request_command(opus: OPUSInterface, qtbot) -> None:
    """Test OPUSInterface's request_command() method."""
    with patch.object(opus, "_requester") as requester_mock:
        opus.request_command("hello")
        assert requester_mock.make_request.call_count == 1
        assert (
            requester_mock.make_request.call_args[0][0]
            == f"http://{OPUS_IP}/opusrs/cmd.htm?opusrshello"
        )


def _format_td(name: str, value: Any) -> str:
    if value is None:
        return ""
    return f'<td id="{name}">{str(value)}</td>'


def _get_opus_html(
    status: int | None,
    errcode: int | None = None,
    errtext: str | None = None,
    extra_text: str = "",
    text: str | None = "status text",
) -> str:
    return f"""
    <html>
        <body>
            <table>
                <tr>
                    {extra_text}
                    {_format_td("STATUS", status)}
                    {_format_td("TEXT", text)}
                    {_format_td("ERRCODE", errcode)}
                    {_format_td("ERRTEXT", errtext)}
                </tr>
            </table>
        </body>
    </html>
    """


@pytest.mark.parametrize(
    "status", (SpectrometerStatus.IDLE, SpectrometerStatus.CONNECTING)
)
def test_parse_response_no_error(status: SpectrometerStatus) -> None:
    """Test parse_response() works when no error has occurred."""
    response = _get_opus_html(status.value)
    assert parse_response(response) == status


@pytest.mark.parametrize("errcode,errtext", product(range(2), ("", "error text")))
def test_parse_response_error(errcode: int, errtext: str) -> None:
    """Test parse_response() works when an error has occurred."""
    response = _get_opus_html(SpectrometerStatus.CONNECTING.value, errcode, errtext)
    with pytest.raises(OPUSError):
        parse_response(response)


@pytest.mark.parametrize("status,text", ((None, "text"), (1, None), (None, None)))
def test_parse_response_missing_fields(status: int | None, text: str | None) -> None:
    """Test parse_response() raises an error if fields are missing."""
    response = _get_opus_html(status, text=text)
    with pytest.raises(OPUSError):
        parse_response(response)


def test_parse_response_no_id(opus: OPUSInterface) -> None:
    """Test that parse_response() can handle <td> tags without an id."""
    response = _get_opus_html(
        SpectrometerStatus.CONNECTING.value, 1, "errtext", "<td>something</td>"
    )
    with pytest.raises(OPUSError):
        parse_response(response)


@patch("finesse.hardware.plugins.spectrometer.opus_interface.logging.warning")
def test_parse_response_bad_id(warning_mock: Mock) -> None:
    """Test that parse_response() can handle <td> tags with unexpected id values."""
    response = _get_opus_html(
        SpectrometerStatus.CONNECTING.value,
        1,
        "errtext",
        '<td id="MADE_UP">something</td>',
    )
    with pytest.raises(OPUSError):
        parse_response(response)
    warning_mock.assert_called()


@patch("finesse.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_no_error(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test the _on_reply_received() method works when no error occurs."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.NoError

    # NB: This value is of the wrong type, but it doesn't matter here
    parse_response_mock.return_value = "status"

    # Check the correct pubsub message is sent
    assert opus._on_reply_received(reply) == "status"


@patch("finesse.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_network_error(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test the _on_reply_received() method handles network errors."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.HostNotFoundError
    reply.errorString.return_value = "Something went wrong"

    with pytest.raises(OPUSError):
        opus._on_reply_received(reply)


@patch("finesse.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_exception(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test that the _on_reply_received() method catches parsing errors."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.NoError

    # Make parse_response() raise an exception
    parse_response_mock.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        opus._on_reply_received(reply)