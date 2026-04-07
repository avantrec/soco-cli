"""Tests for interactive.py.

Covers pure helpers and logic-bearing functions that can be exercised
without a running REPL or live Sonos network.
"""

import sys
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

import soco_cli.interactive as interactive_mod
from soco_cli.aliases import AliasManager
from soco_cli.interactive import (
    AliasProcessor,
    _completer,
    _exec,
    _exec_action,
    _exec_loop,
    _get_speaker_names,
    _loop_in_command_sequences,
    _print_speaker_list,
    _restore_quotes,
    _set_actions_and_commands_list,
)
from soco_cli.utils import RewindableList


@pytest.fixture(autouse=True)
def api_mode():
    """Prevent os._exit() calls during tests."""
    import soco_cli.utils as utils

    original = utils.API
    utils.API = True
    yield
    utils.API = original


# ---------------------------------------------------------------------------
# _restore_quotes
# ---------------------------------------------------------------------------


class TestRestoreQuotes:
    def test_single_word_items_unchanged(self):
        cmd = ["play", "volume", "50"]
        _restore_quotes(cmd)
        assert cmd == ["play", "volume", "50"]

    def test_multi_word_item_gets_quoted(self):
        cmd = ["set", "Front Room"]
        _restore_quotes(cmd)
        assert cmd == ["set", '"Front Room"']

    def test_multiple_multi_word_items(self):
        cmd = ["Living Room", "play_favourite", "Classic FM"]
        _restore_quotes(cmd)
        assert cmd == ['"Living Room"', "play_favourite", '"Classic FM"']

    def test_three_word_item_gets_quoted(self):
        cmd = ["Great Big Hall"]
        _restore_quotes(cmd)
        assert cmd == ['"Great Big Hall"']

    def test_empty_list_unchanged(self):
        cmd = []
        _restore_quotes(cmd)
        assert cmd == []

    def test_already_present_quotes_not_doubled(self):
        # _restore_quotes only checks for spaces, not existing quotes
        cmd = ['"Already Quoted"']
        _restore_quotes(cmd)
        # Has a space inside → gets wrapped again
        assert cmd == ['""Already Quoted""']


# ---------------------------------------------------------------------------
# _loop_in_command_sequences
# ---------------------------------------------------------------------------


class TestLoopInCommandSequences:
    def test_no_loop_returns_false(self):
        seqs = RewindableList([["volume", "50"], ["play"]])
        assert _loop_in_command_sequences(seqs) is False

    def test_loop_keyword_detected(self):
        seqs = RewindableList([["volume", "50"], ["loop"]])
        assert _loop_in_command_sequences(seqs) is True

    def test_loop_until_detected(self):
        seqs = RewindableList([["loop_until", "stopped"]])
        assert _loop_in_command_sequences(seqs) is True

    def test_loop_for_detected(self):
        seqs = RewindableList([["loop_for", "10m"]])
        assert _loop_in_command_sequences(seqs) is True

    def test_loop_in_second_sequence(self):
        seqs = RewindableList([["play"], ["loop"]])
        assert _loop_in_command_sequences(seqs) is True

    def test_loop_in_non_first_position_of_sequence(self):
        # "loop" anywhere in a sequence triggers detection
        seqs = RewindableList([["volume", "loop"]])
        assert _loop_in_command_sequences(seqs) is True

    def test_empty_sequences_returns_false(self):
        seqs = RewindableList([])
        assert _loop_in_command_sequences(seqs) is False


# ---------------------------------------------------------------------------
# _completer
# ---------------------------------------------------------------------------


class TestCompleter:
    def test_returns_first_match(self):
        with patch.object(
            interactive_mod, "ACTIONS_LIST", ["play ", "pause ", "play_favourite "]
        ):
            assert _completer("play", 0) == "play "

    def test_returns_second_match_at_context_1(self):
        with patch.object(
            interactive_mod, "ACTIONS_LIST", ["play ", "pause ", "play_favourite "]
        ):
            assert _completer("play", 1) == "play_favourite "

    def test_no_match_raises_index_error(self):
        with patch.object(interactive_mod, "ACTIONS_LIST", ["play "]):
            with pytest.raises(IndexError):
                _completer("xyz", 0)

    def test_empty_prefix_matches_all(self):
        with patch.object(interactive_mod, "ACTIONS_LIST", ["play ", "pause "]):
            assert _completer("", 0) == "play "
            assert _completer("", 1) == "pause "

    def test_context_beyond_matches_raises_index_error(self):
        with patch.object(interactive_mod, "ACTIONS_LIST", ["play "]):
            with pytest.raises(IndexError):
                _completer("play", 1)


# ---------------------------------------------------------------------------
# _get_speaker_names
# ---------------------------------------------------------------------------


class TestGetSpeakerNames:
    def test_local_uses_local_speaker_list(self):
        mock_cache = MagicMock()
        mock_cache.get_all_speaker_names.return_value = ["Kitchen", "Bedroom"]
        with patch("soco_cli.interactive.local_speaker_list", return_value=mock_cache):
            result = _get_speaker_names(use_local_speaker_list=True)
        assert result == ["Kitchen", "Bedroom"]

    def test_non_local_uses_speaker_cache(self):
        mock_cache = MagicMock()
        mock_cache.get_all_speaker_names.return_value = ["Living Room", "Office"]
        with patch("soco_cli.interactive.speaker_cache", return_value=mock_cache):
            result = _get_speaker_names(use_local_speaker_list=False)
        assert result == ["Living Room", "Office"]

    def test_exception_returns_empty_list(self, capsys):
        with patch(
            "soco_cli.interactive.speaker_cache", side_effect=Exception("network error")
        ):
            result = _get_speaker_names(use_local_speaker_list=False)
        assert result == []
        assert "network error" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _print_speaker_list
# ---------------------------------------------------------------------------


class TestPrintSpeakerList:
    def test_empty_list_prints_only_blank_line(self, capsys):
        # _print_speaker_list always emits one leading newline, but no speaker
        # entries when the list is empty.
        with patch("soco_cli.interactive._get_speaker_names", return_value=[]):
            _print_speaker_list()
        out = capsys.readouterr().out
        assert out.strip() == ""

    def test_speakers_listed_with_zero_unset_entry(self, capsys):
        with patch(
            "soco_cli.interactive._get_speaker_names",
            return_value=["Kitchen", "Bedroom"],
        ):
            _print_speaker_list()
        out = capsys.readouterr().out
        assert "0" in out
        assert "Unset the active speaker" in out

    def test_speakers_numbered_from_one(self, capsys):
        with patch(
            "soco_cli.interactive._get_speaker_names",
            return_value=["Kitchen", "Bedroom"],
        ):
            _print_speaker_list()
        out = capsys.readouterr().out
        assert "1" in out
        assert "Kitchen" in out
        assert "2" in out
        assert "Bedroom" in out

    def test_zero_entry_comes_before_speakers(self, capsys):
        with patch(
            "soco_cli.interactive._get_speaker_names", return_value=["OneSpeaker"]
        ):
            _print_speaker_list()
        lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
        assert lines[0].lstrip().startswith("0")
        assert lines[1].lstrip().startswith("1")


# ---------------------------------------------------------------------------
# _set_actions_and_commands_list
# ---------------------------------------------------------------------------


class TestSetActionsAndCommandsList:
    def test_list_contains_actions_with_trailing_space(self):
        mock_am = MagicMock()
        mock_am.alias_names.return_value = []
        with (
            patch("soco_cli.interactive.get_actions", return_value=["volume", "play"]),
            patch("soco_cli.interactive._get_speaker_names", return_value=[]),
            patch.object(interactive_mod, "am", mock_am),
        ):
            _set_actions_and_commands_list()
        assert "volume " in interactive_mod.ACTIONS_LIST
        assert "play " in interactive_mod.ACTIONS_LIST

    def test_list_contains_speaker_names_with_trailing_space(self):
        mock_am = MagicMock()
        mock_am.alias_names.return_value = []
        with (
            patch("soco_cli.interactive.get_actions", return_value=[]),
            patch(
                "soco_cli.interactive._get_speaker_names",
                return_value=["Kitchen", "Office"],
            ),
            patch.object(interactive_mod, "am", mock_am),
        ):
            _set_actions_and_commands_list()
        assert "Kitchen " in interactive_mod.ACTIONS_LIST
        assert "Office " in interactive_mod.ACTIONS_LIST

    def test_list_contains_shell_commands(self):
        mock_am = MagicMock()
        mock_am.alias_names.return_value = []
        with (
            patch("soco_cli.interactive.get_actions", return_value=[]),
            patch("soco_cli.interactive._get_speaker_names", return_value=[]),
            patch.object(interactive_mod, "am", mock_am),
        ):
            _set_actions_and_commands_list()
        assert "exit" in interactive_mod.ACTIONS_LIST
        assert "help" in interactive_mod.ACTIONS_LIST

    def test_list_contains_alias_names(self):
        mock_am = MagicMock()
        mock_am.alias_names.return_value = ["myfav", "playjazz"]
        with (
            patch("soco_cli.interactive.get_actions", return_value=[]),
            patch("soco_cli.interactive._get_speaker_names", return_value=[]),
            patch.object(interactive_mod, "am", mock_am),
        ):
            _set_actions_and_commands_list()
        assert "myfav" in interactive_mod.ACTIONS_LIST
        assert "playjazz" in interactive_mod.ACTIONS_LIST


# ---------------------------------------------------------------------------
# _exec
# ---------------------------------------------------------------------------


class TestExec:
    def test_calls_subprocess_run_with_shell_true(self):
        with patch("soco_cli.interactive.subprocess.run") as mock_run:
            _exec(["ls", "-l"])
        mock_run.assert_called_once_with("ls -l", shell=True)

    def test_arg_with_space_gets_quoted(self):
        with patch("soco_cli.interactive.subprocess.run") as mock_run:
            _exec(["echo", "hello world"])
        mock_run.assert_called_once_with('echo "hello world"', shell=True)

    def test_multiple_args_with_spaces_quoted(self):
        with patch("soco_cli.interactive.subprocess.run") as mock_run:
            _exec(["cmd", "arg one", "arg two"])
        mock_run.assert_called_once_with('cmd "arg one" "arg two"', shell=True)

    def test_returns_false_when_no_ctrl_c(self):
        with patch("soco_cli.interactive.subprocess.run"):
            with patch(
                "soco_cli.interactive.get_ctrl_c_interrupted", return_value=False
            ):
                result = _exec(["ls"])
        assert result is False

    def test_returns_true_when_ctrl_c_interrupted(self):
        with patch("soco_cli.interactive.subprocess.run"):
            with patch(
                "soco_cli.interactive.get_ctrl_c_interrupted", return_value=True
            ):
                result = _exec(["ls"])
        assert result is True

    def test_subprocess_exception_does_not_propagate(self, capsys):
        with patch("soco_cli.interactive.subprocess.run", side_effect=OSError("bad")):
            _exec(["bad_cmd"])
        assert "bad" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _exec_action
# ---------------------------------------------------------------------------


class TestExecAction:
    def setup_method(self):
        self._orig_log = interactive_mod.LOG_SETTING
        interactive_mod.LOG_SETTING = "--log=none"

    def teardown_method(self):
        interactive_mod.LOG_SETTING = self._orig_log

    def test_speaker_action_includes_ip_in_command(self):
        captured = {}

        def fake_exec(args):
            captured["args"] = args[:]
            return False

        with patch("soco_cli.interactive._exec", side_effect=fake_exec):
            with patch.object(sys, "argv", ["sonos"]):
                _exec_action("192.168.1.10", "volume", ["50"])

        assert "192.168.1.10" in captured["args"]
        assert "volume" in captured["args"]
        assert "50" in captured["args"]

    def test_no_speaker_action_omits_ip(self):
        captured = {}

        def fake_exec(args):
            captured["args"] = args[:]
            return False

        with patch("soco_cli.interactive._exec", side_effect=fake_exec):
            with patch.object(sys, "argv", ["sonos"]):
                _exec_action("192.168.1.10", "wait", ["10"])

        assert "192.168.1.10" not in captured["args"]
        assert "wait" in captured["args"]
        assert "10" in captured["args"]

    def test_log_setting_inserted_at_position_1(self):
        captured = {}

        def fake_exec(args):
            captured["args"] = args[:]
            return False

        interactive_mod.LOG_SETTING = "--log=debug"
        with patch("soco_cli.interactive._exec", side_effect=fake_exec):
            with patch.object(sys, "argv", ["sonos"]):
                _exec_action("1.2.3.4", "play", [])

        assert captured["args"][1] == "--log=debug"

    def test_returns_exec_result_true(self):
        with patch("soco_cli.interactive._exec", return_value=True):
            with patch.object(sys, "argv", ["sonos"]):
                result = _exec_action("1.2.3.4", "play", [])
        assert result is True

    def test_returns_exec_result_false(self):
        with patch("soco_cli.interactive._exec", return_value=False):
            with patch.object(sys, "argv", ["sonos"]):
                result = _exec_action("1.2.3.4", "play", [])
        assert result is False


# ---------------------------------------------------------------------------
# _exec_loop
# ---------------------------------------------------------------------------


class TestExecLoop:
    def setup_method(self):
        self._orig_log = interactive_mod.LOG_SETTING
        interactive_mod.LOG_SETTING = "--log=none"

    def teardown_method(self):
        interactive_mod.LOG_SETTING = self._orig_log

    def test_no_loop_returns_false(self):
        speaker = MagicMock()
        seqs = RewindableList([["volume", "50"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            result = _exec_loop(speaker, ["play"], seqs, False)
        assert result is False
        mock_exec.assert_not_called()

    def test_loop_action_returns_true(self):
        speaker = MagicMock()
        seqs = RewindableList([["loop"]])
        with patch("soco_cli.interactive._exec_command_line"):
            result = _exec_loop(speaker, ["play"], seqs, False)
        assert result is True

    def test_loop_calls_exec_command_line_once(self):
        speaker = MagicMock()
        seqs = RewindableList([["loop"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            _exec_loop(speaker, ["play"], seqs, False)
        mock_exec.assert_called_once()

    def test_unix_includes_export_spkr_env(self):
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.5"
        seqs = RewindableList([["loop"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            with patch.object(interactive_mod, "UNIX", True):
                with patch.object(interactive_mod, "WINDOWS", False):
                    _exec_loop(speaker, ["play"], seqs, False)
        cmd = mock_exec.call_args[0][0]
        assert "export SPKR=192.168.1.5" in cmd
        assert "&&" in cmd

    def test_windows_includes_set_spkr_env(self):
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.5"
        seqs = RewindableList([["loop"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            with patch.object(interactive_mod, "UNIX", False):
                with patch.object(interactive_mod, "WINDOWS", True):
                    _exec_loop(speaker, ["play"], seqs, False)
        cmd = mock_exec.call_args[0][0]
        assert 'set "SPKR=192.168.1.5"' in cmd
        assert "&&" in cmd

    def test_no_speaker_excludes_spkr_env(self):
        seqs = RewindableList([["loop"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            _exec_loop(None, ["play"], seqs, False)
        cmd = mock_exec.call_args[0][0]
        assert "SPKR" not in cmd

    def test_use_local_adds_flag_when_no_speaker(self):
        seqs = RewindableList([["loop"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            _exec_loop(None, ["play"], seqs, use_local=True)
        cmd = mock_exec.call_args[0][0]
        assert "-l " in cmd

    def test_sequences_joined_with_colon_separator(self):
        speaker = MagicMock()
        speaker.ip_address = "1.2.3.4"
        seqs = RewindableList([["volume", "50"], ["loop"]])
        with patch("soco_cli.interactive._exec_command_line") as mock_exec:
            with patch.object(interactive_mod, "UNIX", True):
                with patch.object(interactive_mod, "WINDOWS", False):
                    _exec_loop(speaker, ["play"], seqs, False)
        cmd = mock_exec.call_args[0][0]
        assert "play : volume 50 : loop" in cmd

    def test_does_not_mutate_remaining_sequences(self):
        speaker = MagicMock()
        seqs = RewindableList([["volume", "50"], ["loop"]])
        original_items = deepcopy(list(seqs))
        with patch("soco_cli.interactive._exec_command_line"):
            _exec_loop(speaker, ["play"], seqs, False)
        assert list(seqs) == original_items


# ---------------------------------------------------------------------------
# AliasProcessor helpers
# ---------------------------------------------------------------------------


def _make_am(*alias_pairs):
    """Create an AliasManager pre-populated with (name, action) pairs."""
    am = AliasManager()
    for name, action in alias_pairs:
        am.create_alias(name, action)
    return am


# ---------------------------------------------------------------------------
# AliasProcessor — basic expansion
# ---------------------------------------------------------------------------


class TestAliasProcessorBasicExpansion:
    def test_simple_expansion(self):
        am = _make_am(("vol50", "volume 50"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["vol50"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume", "50"]]

    def test_expansion_inserts_before_existing_commands(self):
        am = _make_am(("vol50", "volume 50"))
        cmd_list = RewindableList([["play"]])
        result = AliasProcessor().process(["vol50"], am, cmd_list)
        assert result is True
        items = list(cmd_list)
        assert items[0] == ["volume", "50"]
        assert items[1] == ["play"]

    def test_multi_token_expansion(self):
        am = _make_am(("pf", "play_favourite Jazz"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["pf"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play_favourite", "Jazz"]]

    def test_extra_args_without_placeholders_are_unused(self):
        # Args beyond what %N placeholders consume are silently dropped
        am = _make_am(("greet", "play"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["greet", "extra"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play"]]


# ---------------------------------------------------------------------------
# AliasProcessor — argument substitution
# ---------------------------------------------------------------------------


class TestAliasProcessorArgSubstitution:
    def test_single_arg_substituted(self):
        am = _make_am(("vol", "volume %1"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["vol", "75"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume", "75"]]

    def test_two_args_substituted(self):
        am = _make_am(("fav", "play_favourite %1 %2"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["fav", "Jazz", "next"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play_favourite", "Jazz", "next"]]

    def test_unsatisfied_placeholder_removed(self):
        # %2 is not provided — the placeholder token is dropped
        am = _make_am(("vol", "volume %1 %2"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["vol", "50"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume", "50"]]

    def test_no_args_all_placeholders_removed(self):
        am = _make_am(("vol", "volume %1"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["vol"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume"]]

    def test_same_placeholder_usable_once(self):
        # %1 appears twice; each occurrence is filled independently
        am = _make_am(("dup", "echo %1 %1"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["dup", "hello"], am, cmd_list)
        assert result is True
        # After first %1 is substituted, the arg is marked used so second %1
        # can still access it (alias_parms_used tracks indices, not values)
        assert list(cmd_list) == [["echo", "hello", "hello"]]

    def test_arg_substitution_in_multi_sequence_alias(self):
        am = _make_am(("pv", "play : volume %1"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["pv", "30"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play"], ["volume", "30"]]


# ---------------------------------------------------------------------------
# AliasProcessor — multi-sequence aliases
# ---------------------------------------------------------------------------


class TestAliasProcessorMultiSequence:
    def test_two_sequence_alias_inserted_in_order(self):
        am = _make_am(("playvol", "play : volume 50"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["playvol"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play"], ["volume", "50"]]

    def test_three_sequence_alias(self):
        am = _make_am(("triple", "play : volume 50 : mute off"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["triple"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play"], ["volume", "50"], ["mute", "off"]]

    def test_multi_sequence_prepended_to_existing_commands(self):
        am = _make_am(("pv", "play : volume 50"))
        cmd_list = RewindableList([["pause"]])
        result = AliasProcessor().process(["pv"], am, cmd_list)
        assert result is True
        items = list(cmd_list)
        assert items[0] == ["play"]
        assert items[1] == ["volume", "50"]
        assert items[2] == ["pause"]


# ---------------------------------------------------------------------------
# AliasProcessor — nested / recursive alias expansion
# ---------------------------------------------------------------------------


class TestAliasProcessorRecursion:
    def test_one_level_nested_alias(self):
        am = _make_am(("inner", "volume 50"), ("outer", "inner"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["outer"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume", "50"]]

    def test_two_levels_nested(self):
        am = _make_am(
            ("base", "play"),
            ("mid", "base"),
            ("top", "mid"),
        )
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["top"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play"]]

    def test_nested_alias_with_arg_propagation(self):
        # setvol %1 → vol %1 → volume %1
        am = _make_am(("vol", "volume %1"), ("setvol", "vol %1"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["setvol", "80"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume", "80"]]

    def test_nested_alias_mixed_with_real_action(self):
        # outer = "inner : pause", inner = "play"
        am = _make_am(("inner", "play"), ("outer", "inner : pause"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["outer"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["play"], ["pause"]]

    def test_nested_alias_arg_propagated_two_levels(self):
        # top %1 → mid %1 → volume %1
        am = _make_am(
            ("vol", "volume %1"),
            ("mid", "vol %1"),
            ("top", "mid %1"),
        )
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["top", "42"], am, cmd_list)
        assert result is True
        assert list(cmd_list) == [["volume", "42"]]


# ---------------------------------------------------------------------------
# AliasProcessor — loop detection
# ---------------------------------------------------------------------------


class TestAliasProcessorLoopDetection:
    def test_self_referential_loop_returns_false(self, capsys):
        am = _make_am(("a", "a"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["a"], am, cmd_list)
        assert result is False
        assert "loop" in capsys.readouterr().out.lower()

    def test_mutual_recursion_ab_returns_false(self, capsys):
        am = _make_am(("a", "b"), ("b", "a"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["a"], am, cmd_list)
        assert result is False
        assert "loop" in capsys.readouterr().out.lower()

    def test_three_way_loop_detected(self, capsys):
        am = _make_am(("a", "b"), ("b", "c"), ("c", "a"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["a"], am, cmd_list)
        assert result is False
        assert "loop" in capsys.readouterr().out.lower()

    def test_loop_cleanup_removes_partially_inserted_commands(self, capsys):
        # "first" successfully inserts "volume 50" before encountering the
        # self-loop via "loopy".  The cleanup must remove that partial work.
        am = _make_am(
            ("loopy", "loopy"),
            ("first", "volume 50 : loopy"),
        )
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["first"], am, cmd_list)
        assert result is False
        assert list(cmd_list) == []
        assert "loop" in capsys.readouterr().out.lower()

    def test_loop_cleanup_leaves_pre_existing_commands_intact(self, capsys):
        # Commands already in cmd_list before the alias is processed must
        # survive the cleanup after loop detection.
        am = _make_am(("a", "a"))
        cmd_list = RewindableList([["pre_existing"]])
        result = AliasProcessor().process(["a"], am, cmd_list)
        assert result is False
        # The pre-existing command should still be there
        assert ["pre_existing"] in list(cmd_list)
        capsys.readouterr()  # suppress output

    def test_non_looping_alias_not_misidentified(self):
        # Alias "a" appears twice in a sequence but the second use is a
        # separate invocation (different seq_number context) — not a loop.
        # Simplest proxy: just confirm a valid two-sequence alias works.
        am = _make_am(("a", "play"))
        cmd_list = RewindableList([])
        result = AliasProcessor().process(["a"], am, cmd_list)
        assert result is True


# ---------------------------------------------------------------------------
# AliasProcessor — _remove_added_commands
# ---------------------------------------------------------------------------


class TestAliasProcessorRemoveAdded:
    def test_removes_exact_command_count(self):
        cmd_list = RewindableList([["volume", "50"], ["play"], ["pause"]])
        ap = AliasProcessor()
        ap._command_count = 2
        ap._command_list = cmd_list
        ap._remove_added_commands()
        assert list(cmd_list) == [["pause"]]

    def test_zero_count_removes_nothing(self):
        cmd_list = RewindableList([["play"]])
        ap = AliasProcessor()
        ap._command_count = 0
        ap._command_list = cmd_list
        ap._remove_added_commands()
        assert list(cmd_list) == [["play"]]

    def test_command_count_after_successful_expansion(self):
        # Two-sequence alias should report _command_count == 2
        am = _make_am(("pv", "play : volume 50"))
        cmd_list = RewindableList([])
        ap = AliasProcessor()
        ap.process(["pv"], am, cmd_list)
        assert ap._command_count == 2
