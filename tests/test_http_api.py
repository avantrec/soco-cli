"""Tests for the HTTP API server (http_api.py).

Covers: ActiveAsyncOps, pure helper functions, macro loading/substitution,
_process_macro (sync and async), command_core, and FastAPI endpoints via
TestClient. No live Sonos network or running server required.
"""

import os
import tempfile
from subprocess import CalledProcessError
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

import soco_cli.http_api as http_api
from soco_cli.http_api import (
    ASYNC_PREFIX,
    ActiveAsyncOps,
    _load_macros,
    _lookup_macro,
    _process_macro,
    _quote_if_contains_space,
    _substitute_variables,
    command_core,
    sc_app,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_globals():
    """Restore mutated module-level globals after each test."""
    original_macros = dict(http_api.MACROS)
    original_use_local = http_api.USE_LOCAL
    http_api.ASYNC_OPS.active_async_ops.clear()
    http_api.ASYNC_MACRO_OPS.active_async_ops.clear()
    yield
    http_api.MACROS.clear()
    http_api.MACROS.update(original_macros)
    http_api.USE_LOCAL = original_use_local
    http_api.ASYNC_OPS.active_async_ops.clear()
    http_api.ASYNC_MACRO_OPS.active_async_ops.clear()


@pytest.fixture
def client():
    return TestClient(sc_app)


@pytest.fixture
def loaded_macros():
    """Populate MACROS with a small set of test macros."""
    http_api.MACROS.clear()
    http_api.MACROS.update(
        {
            "__": "%1 %2 %3 %4 %5 %6 %7 %8 %9 %10 %11 %12",
            "vol": "Kitchen volume %1",
            "morning": "Kitchen play_favourite Radio4 : Bedroom group Kitchen",
            "two_rooms": "%1 volume %2 : %3 volume %4",
        }
    )
    return http_api.MACROS


# ===========================================================================
# ActiveAsyncOps
# ===========================================================================


class TestActiveAsyncOps:
    def test_add_and_get(self):
        ops = ActiveAsyncOps()
        ops.add_async_pid("192.168.0.1", 1234)
        assert ops.get_async_pid("192.168.0.1") == 1234

    def test_get_missing_returns_none(self):
        ops = ActiveAsyncOps()
        assert ops.get_async_pid("192.168.0.99") is None

    def test_remove_returns_pid_and_clears(self):
        ops = ActiveAsyncOps()
        ops.add_async_pid("192.168.0.1", 5678)
        pid = ops.remove_async_pid("192.168.0.1")
        assert pid == 5678
        assert ops.get_async_pid("192.168.0.1") is None

    def test_remove_missing_returns_none(self):
        ops = ActiveAsyncOps()
        assert ops.remove_async_pid("192.168.0.99") is None

    def test_stop_sends_sigint_and_removes(self):
        ops = ActiveAsyncOps()
        ops.add_async_pid("192.168.0.1", 9999)
        with patch("soco_cli.http_api.kill") as mock_kill:
            from signal import SIGINT

            pid = ops.stop_async_process("192.168.0.1")
        mock_kill.assert_called_once_with(9999, SIGINT)
        assert pid == 9999
        assert ops.get_async_pid("192.168.0.1") is None

    def test_stop_missing_returns_none(self):
        ops = ActiveAsyncOps()
        assert ops.stop_async_process("192.168.0.99") is None

    def test_overwrite_pid(self):
        ops = ActiveAsyncOps()
        ops.add_async_pid("192.168.0.1", 100)
        ops.add_async_pid("192.168.0.1", 200)
        assert ops.get_async_pid("192.168.0.1") == 200

    def test_multiple_keys_are_independent(self):
        ops = ActiveAsyncOps()
        ops.add_async_pid("192.168.0.1", 1)
        ops.add_async_pid("192.168.0.2", 2)
        assert ops.get_async_pid("192.168.0.1") == 1
        assert ops.get_async_pid("192.168.0.2") == 2
        ops.remove_async_pid("192.168.0.1")
        assert ops.get_async_pid("192.168.0.2") == 2


# ===========================================================================
# _quote_if_contains_space
# ===========================================================================


class TestQuoteIfContainsSpace:
    def test_no_space(self):
        assert _quote_if_contains_space("Kitchen") == "Kitchen"

    def test_with_space(self):
        assert _quote_if_contains_space("Living Room") == '"Living Room"'

    def test_empty_string(self):
        assert _quote_if_contains_space("") == ""

    def test_multiple_spaces(self):
        assert _quote_if_contains_space("a b c") == '"a b c"'


# ===========================================================================
# _substitute_variables
# ===========================================================================


class TestSubstituteVariables:
    def test_no_parameters(self):
        assert _substitute_variables("Kitchen volume 30", ()) == "Kitchen volume 30"

    def test_single_substitution(self):
        result = _substitute_variables("Kitchen volume %1", ("40",))
        assert result == "Kitchen volume 40"

    def test_multiple_substitutions(self):
        result = _substitute_variables("%1 volume %2", ("Kitchen", "50"))
        assert result == "Kitchen volume 50"

    def test_unused_args_are_ignored(self):
        result = _substitute_variables("Kitchen volume %1", ("30", "extra"))
        assert result == "Kitchen volume 30"

    def test_unsatisfied_parameter_omitted(self):
        result = _substitute_variables("Kitchen volume %1 : Bedroom volume %2", ("30",))
        assert result == "Kitchen volume 30 : Bedroom volume"

    def test_underscore_arg_is_skipped(self):
        # An underscore argument causes the positional parameter to be omitted
        result = _substitute_variables("%1 volume %2", ("Kitchen", "_"))
        assert result == "Kitchen volume"

    def test_arg_with_space_is_quoted(self):
        result = _substitute_variables("%1 volume 30", ("Living Room",))
        assert result == '"Living Room" volume 30'

    def test_all_twelve_params(self):
        macro = " ".join("%{}".format(i) for i in range(1, 13))
        args = tuple(str(i) for i in range(1, 13))
        result = _substitute_variables(macro, args)
        assert result == " ".join(str(i) for i in range(1, 13))


# ===========================================================================
# _load_macros
# ===========================================================================


class TestLoadMacros:
    def test_loads_valid_file(self):
        macros = {}
        content = "# comment\nvol = Kitchen volume %1\nmorning = Kitchen play_favourite Radio4\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            name = f.name
        try:
            result = _load_macros(macros, name)
            assert result is True
            assert macros["vol"] == "Kitchen volume %1"
            assert macros["morning"] == "Kitchen play_favourite Radio4"
            # Generic macro always added
            assert "__" in macros
        finally:
            os.unlink(name)

    def test_ignores_blank_lines_and_comments(self):
        macros = {}
        content = "# header\n\nvol = Kitchen volume %1\n\n# tail\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            name = f.name
        try:
            _load_macros(macros, name)
            assert list(k for k in macros if k != "__") == ["vol"]
        finally:
            os.unlink(name)

    def test_missing_file_returns_false(self):
        macros = {}
        result = _load_macros(macros, "/nonexistent/path/macros.txt")
        assert result is False
        # Generic macro is still added even when file is missing
        assert macros["__"] == "%1 %2 %3 %4 %5 %6 %7 %8 %9 %10 %11 %12"

    def test_malformed_line_is_skipped(self):
        macros = {}
        content = "bad line without equals\nvol = Kitchen volume %1\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            name = f.name
        try:
            _load_macros(macros, name)
            assert "vol" in macros
            assert "bad line without equals" not in macros
        finally:
            os.unlink(name)

    def test_strips_whitespace_from_name_and_value(self):
        macros = {}
        content = "  vol  =  Kitchen volume %1  \n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            name = f.name
        try:
            _load_macros(macros, name)
            assert macros["vol"] == "Kitchen volume %1"
        finally:
            os.unlink(name)


# ===========================================================================
# _lookup_macro
# ===========================================================================


class TestLookupMacro:
    def test_found(self, loaded_macros):
        assert _lookup_macro("vol") == "Kitchen volume %1"

    def test_not_found_raises_key_error(self):
        with pytest.raises(KeyError):
            _lookup_macro("no_such_macro")


# ===========================================================================
# _process_macro — synchronous
# ===========================================================================


class TestProcessMacroSync:
    def test_unknown_macro_returns_error(self):
        command, result = _process_macro("no_such_macro")
        assert command == ""
        assert "not found" in result

    def test_successful_sync_execution(self, loaded_macros):
        with patch("soco_cli.http_api.check_output", return_value=b"30") as mock_co:
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                command, result = _process_macro("vol", "30")
        assert result == "30"
        assert "sonos" in command
        assert mock_co.called

    def test_sync_failure_returns_error_output(self, loaded_macros):
        exc = CalledProcessError(1, "sonos", output=b"error detail")
        with patch("soco_cli.http_api.check_output", side_effect=exc):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                command, result = _process_macro("vol", "30")
        assert result == "error detail"

    def test_use_local_prepends_flag(self, loaded_macros):
        http_api.USE_LOCAL = True
        with patch("soco_cli.http_api.check_output", return_value=b"") as mock_co:
            command, _ = _process_macro("morning")
        args = mock_co.call_args[0][0]
        assert args[1] == "-l"

    def test_command_contains_substituted_arg(self, loaded_macros):
        with patch("soco_cli.http_api.check_output", return_value=b"") as mock_co:
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                command, _ = _process_macro("vol", "99")
        assert "99" in command


# ===========================================================================
# _process_macro — async
# ===========================================================================


class TestProcessMacroAsync:
    def test_async_runs_popen_not_check_output(self, loaded_macros):
        mock_proc = MagicMock()
        mock_proc.pid = 1111
        with patch("soco_cli.http_api.Popen", return_value=mock_proc) as mock_popen:
            with patch("soco_cli.http_api.check_output") as mock_co:
                with patch(
                    "soco_cli.http_api._substitute_speaker_ips",
                    side_effect=lambda x, **kw: x,
                ):
                    command, result = _process_macro("async_vol", "50")
        mock_popen.assert_called_once()
        mock_co.assert_not_called()
        assert result == ""

    def test_async_returns_immediately_with_empty_result(self, loaded_macros):
        mock_proc = MagicMock()
        mock_proc.pid = 2222
        with patch("soco_cli.http_api.Popen", return_value=mock_proc):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                command, result = _process_macro("async_vol", "40")
        assert result == ""
        assert "sonos" in command

    def test_async_strips_prefix_before_macro_lookup(self, loaded_macros):
        # "async_vol" should resolve to the "vol" macro, not fail
        mock_proc = MagicMock()
        mock_proc.pid = 3333
        with patch("soco_cli.http_api.Popen", return_value=mock_proc):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                command, result = _process_macro("async_vol", "20")
        assert "not found" not in result

    def test_async_unknown_macro_returns_error(self):
        command, result = _process_macro("async_no_such_macro")
        assert command == ""
        assert "not found" in result

    def test_async_pid_is_tracked(self, loaded_macros):
        mock_proc = MagicMock()
        mock_proc.pid = 4444
        with patch("soco_cli.http_api.Popen", return_value=mock_proc):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                _process_macro("async_vol", "30")
        assert http_api.ASYNC_MACRO_OPS.get_async_pid("vol|30") == 4444

    def test_async_same_name_and_args_cancels_previous(self, loaded_macros):
        mock_proc = MagicMock()
        mock_proc.pid = 5555
        with patch("soco_cli.http_api.Popen", return_value=mock_proc):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                _process_macro("async_vol", "30")

        mock_proc2 = MagicMock()
        mock_proc2.pid = 6666
        with patch("soco_cli.http_api.Popen", return_value=mock_proc2):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                with patch("soco_cli.http_api.kill") as mock_kill:
                    _process_macro("async_vol", "30")
        from signal import SIGINT

        mock_kill.assert_called_once_with(5555, SIGINT)
        assert http_api.ASYNC_MACRO_OPS.get_async_pid("vol|30") == 6666

    def test_async_different_args_run_concurrently(self, loaded_macros):
        """Same macro with different args should NOT cancel each other."""
        mock_proc_a = MagicMock()
        mock_proc_a.pid = 7777
        mock_proc_b = MagicMock()
        mock_proc_b.pid = 8888

        with patch("soco_cli.http_api.Popen", return_value=mock_proc_a):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                _process_macro("async_vol", "30")

        with patch("soco_cli.http_api.Popen", return_value=mock_proc_b):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                with patch("soco_cli.http_api.kill") as mock_kill:
                    _process_macro("async_vol", "40")

        mock_kill.assert_not_called()
        assert http_api.ASYNC_MACRO_OPS.get_async_pid("vol|30") == 7777
        assert http_api.ASYNC_MACRO_OPS.get_async_pid("vol|40") == 8888

    def test_async_popen_failure_returns_error(self, loaded_macros):
        with patch("soco_cli.http_api.Popen", side_effect=OSError("boom")):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                command, result = _process_macro("async_vol", "30")
        assert "boom" in result


# ===========================================================================
# command_core
# ===========================================================================


class TestCommandCore:
    def _make_device(self, name="Kitchen", ip="192.168.0.10"):
        device = MagicMock()
        device.player_name = name
        device.ip_address = ip
        return device

    def test_speaker_not_found_returns_exit_code_1(self):
        with patch("soco_cli.http_api.get_speaker", return_value=(None, "not found")):
            result = command_core("Nonexistent", "volume")
        assert result["exit_code"] == 1

    def test_successful_sync_action(self):
        device = self._make_device()
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch(
                "soco_cli.http_api.sc_run", return_value=(0, "30", "")
            ) as mock_run:
                result = command_core("Kitchen", "volume")
        assert result["exit_code"] == 0
        assert result["result"] == "30"
        assert result["speaker"] == "Kitchen"
        mock_run.assert_called_once()

    def test_sync_action_failure(self):
        device = self._make_device()
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch("soco_cli.http_api.sc_run", return_value=(1, "", "bad action")):
                result = command_core("Kitchen", "bad_action")
        assert result["exit_code"] == 1

    def test_async_action_uses_popen(self):
        device = self._make_device()
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch("soco_cli.http_api.Popen", return_value=mock_proc) as mock_popen:
                with patch("soco_cli.http_api.sc_run") as mock_run:
                    result = command_core("Kitchen", "async_play_file", "track.mp3")
        mock_popen.assert_called_once()
        mock_run.assert_not_called()
        assert result["exit_code"] == 0

    def test_async_action_tracks_pid(self):
        device = self._make_device(ip="192.168.0.20")
        mock_proc = MagicMock()
        mock_proc.pid = 9876
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch("soco_cli.http_api.Popen", return_value=mock_proc):
                command_core("Kitchen", "async_play_file", "track.mp3")
        assert http_api.ASYNC_OPS.get_async_pid("192.168.0.20") == 9876

    def test_speaker_name_with_spaces_is_quoted_in_log(self, capsys):
        device = self._make_device(name="Living Room", ip="192.168.0.30")
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch("soco_cli.http_api.sc_run", return_value=(0, "", "")):
                command_core("Living Room", "volume")
        out = capsys.readouterr().out
        assert '"Living Room"' in out


# ===========================================================================
# FastAPI endpoints
# ===========================================================================


class TestEndpoints:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "info" in response.json()

    def test_macros_list_empty(self, client):
        http_api.MACROS.clear()
        response = client.get("/macros/list")
        assert response.status_code == 200
        assert response.json() == {}

    def test_macros_list_populated(self, client, loaded_macros):
        response = client.get("/macros/list")
        assert response.status_code == 200
        data = response.json()
        assert "vol" in data
        assert "morning" in data

    def test_macro_not_found(self, client):
        response = client.get("/macro/no_such_macro")
        assert response.status_code == 200
        data = response.json()
        assert "not found" in data["result"]

    def test_macro_sync_success(self, client, loaded_macros):
        with patch("soco_cli.http_api.check_output", return_value=b"30"):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                response = client.get("/macro/vol/30")
        assert response.status_code == 200
        assert response.json()["result"] == "30"

    def test_macro_async_success(self, client, loaded_macros):
        mock_proc = MagicMock()
        mock_proc.pid = 1111
        with patch("soco_cli.http_api.Popen", return_value=mock_proc):
            with patch(
                "soco_cli.http_api._substitute_speaker_ips",
                side_effect=lambda x, **kw: x,
            ):
                response = client.get("/macro/async_vol/50")
        assert response.status_code == 200
        assert response.json()["result"] == ""

    def test_macros_reload(self, client):
        with patch("soco_cli.http_api._load_macros") as mock_load:
            response = client.get("/macros/reload")
        assert response.status_code == 200
        mock_load.assert_called_once()

    def test_speaker_action_endpoint(self, client):
        device = MagicMock()
        device.player_name = "Kitchen"
        device.ip_address = "192.168.0.10"
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch("soco_cli.http_api.sc_run", return_value=(0, "25", "")):
                response = client.get("/Kitchen/volume")
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert data["result"] == "25"

    def test_speaker_action_with_arg(self, client):
        device = MagicMock()
        device.player_name = "Kitchen"
        device.ip_address = "192.168.0.10"
        with patch("soco_cli.http_api.get_speaker", return_value=(device, "")):
            with patch(
                "soco_cli.http_api.sc_run", return_value=(0, "", "")
            ) as mock_run:
                response = client.get("/Kitchen/volume/40")
        assert response.status_code == 200
        assert mock_run.called

    def test_speakers_endpoint(self, client):
        with patch(
            "soco_cli.http_api.get_all_speaker_names",
            return_value=["Kitchen", "Bedroom"],
        ):
            response = client.get("/speakers")
        assert response.status_code == 200
        assert response.json()["speakers"] == ["Kitchen", "Bedroom"]
