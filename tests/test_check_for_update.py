"""Tests for check_for_update.py."""

from io import BytesIO
from unittest.mock import patch

import pytest

import soco_cli.utils as utils
from soco_cli.check_for_update import (
    get_latest_version,
    print_update_status,
    update_available,
)


@pytest.fixture(autouse=True)
def api_mode():
    original = utils.API
    utils.API = True
    yield
    utils.API = original


def _fake_urlopen(lines):
    """Return a mock file-like object yielding the given byte lines."""
    return BytesIO(b"\n".join(line.encode() for line in lines))


class TestGetLatestVersion:
    def test_successful_fetch_returns_version(self):
        content = _fake_urlopen(['__version__ = "1.2.3"'])
        with patch("soco_cli.check_for_update.urlopen", return_value=content):
            result = get_latest_version()
        assert result == "1.2.3"

    def test_version_string_without_spaces(self):
        content = _fake_urlopen(['__version__ = "0.4.86"'])
        with patch("soco_cli.check_for_update.urlopen", return_value=content):
            result = get_latest_version()
        assert result == "0.4.86"

    def test_version_line_with_trailing_newline_stripped(self):
        content = BytesIO(b'__version__ = "1.0.0"\n')
        with patch("soco_cli.check_for_update.urlopen", return_value=content):
            result = get_latest_version()
        assert result == "1.0.0"

    def test_no_version_line_returns_none(self):
        content = _fake_urlopen(["# no version here", "some_other = 42"])
        with patch("soco_cli.check_for_update.urlopen", return_value=content):
            result = get_latest_version()
        assert result is None

    def test_network_error_returns_none(self, capsys):
        with patch(
            "soco_cli.check_for_update.urlopen", side_effect=Exception("timeout")
        ):
            result = get_latest_version()
        assert result is None
        assert "Error" in capsys.readouterr().err


class TestPrintUpdateStatus:
    def test_up_to_date(self, capsys):
        import soco_cli.check_for_update as m

        with patch.object(m, "__version__", "1.0.0"):
            with patch(
                "soco_cli.check_for_update.get_latest_version", return_value="1.0.0"
            ):
                result = print_update_status()
        assert result is True
        assert "up to date" in capsys.readouterr().out

    def test_update_available(self, capsys):
        import soco_cli.check_for_update as m

        with patch.object(m, "__version__", "1.0.0"):
            with patch(
                "soco_cli.check_for_update.get_latest_version", return_value="1.1.0"
            ):
                result = print_update_status()
        assert result is True
        assert "1.1.0" in capsys.readouterr().out

    def test_network_failure_returns_false(self):
        with patch("soco_cli.check_for_update.get_latest_version", return_value=None):
            result = print_update_status()
        assert result is False


class TestUpdateAvailable:
    def test_same_version_returns_false(self):
        import soco_cli.check_for_update as m

        with patch.object(m, "__version__", "1.0.0"):
            with patch(
                "soco_cli.check_for_update.get_latest_version", return_value="1.0.0"
            ):
                assert update_available() is False

    def test_different_version_returns_true(self):
        import soco_cli.check_for_update as m

        with patch.object(m, "__version__", "1.0.0"):
            with patch(
                "soco_cli.check_for_update.get_latest_version", return_value="1.1.0"
            ):
                assert update_available() is True

    def test_none_version_returns_true(self):
        # get_latest_version() returns None on network error; None != any version
        import soco_cli.check_for_update as m

        with patch.object(m, "__version__", "1.0.0"):
            with patch(
                "soco_cli.check_for_update.get_latest_version", return_value=None
            ):
                assert update_available() is True
