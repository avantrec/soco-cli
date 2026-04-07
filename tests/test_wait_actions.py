"""Tests for wait_actions.py."""

from unittest.mock import patch

import pytest

import soco_cli.utils as utils
from soco_cli.wait_actions import process_wait


@pytest.fixture(autouse=True)
def api_mode():
    original = utils.API
    utils.API = True
    yield
    utils.API = original


class TestProcessWaitAndWaitFor:
    @pytest.mark.parametrize("action", ["wait", "wait_for"])
    def test_waits_for_given_seconds(self, action):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait([action, "30s"])
        mock_sleep.assert_called_once_with(30.0)

    def test_wait_minutes(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "2m"])
        mock_sleep.assert_called_once_with(120.0)

    def test_wait_hours(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "1h"])
        mock_sleep.assert_called_once_with(3600.0)

    def test_wait_hh_mm_ss_format(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "00:01:30"])
        mock_sleep.assert_called_once_with(90.0)

    def test_wait_hh_mm_format(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "01:00"])
        mock_sleep.assert_called_once_with(3600.0)

    def test_missing_parameter_skips_sleep(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait"])
        mock_sleep.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_too_many_parameters_skips_sleep(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "10s", "extra"])
        mock_sleep.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_invalid_duration_reports_error_then_sleeps_zero(self, capsys):
        # Invalid duration: error_report is called, but duration stays 0
        # and time.sleep(0) is still called (no early return after ValueError)
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "invalid"])
        assert "Error" in capsys.readouterr().err
        mock_sleep.assert_called_once_with(0)


class TestProcessWaitUntil:
    def test_waits_until_given_time(self):
        with patch("soco_cli.wait_actions.seconds_until", return_value=300) as mock_su:
            with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
                process_wait(["wait_until", "12:30"])
        mock_su.assert_called_once_with("12:30")
        mock_sleep.assert_called_once_with(300)

    def test_missing_parameter_skips_sleep(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait_until"])
        mock_sleep.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_too_many_parameters_skips_sleep(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait_until", "12:30", "extra"])
        mock_sleep.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_invalid_time_format_reports_error_no_sleep(self, capsys):
        # seconds_until raises ValueError for bad input; caught → error_report, no sleep
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait_until", "notatime"])
        assert "Error" in capsys.readouterr().err
        mock_sleep.assert_not_called()
