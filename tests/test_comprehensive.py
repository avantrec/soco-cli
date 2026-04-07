"""Comprehensive unit tests for SoCo-CLI utilities.

Tests cover all pure-Python logic that does not require a live Sonos network:
time conversion, name matching, the RewindableList sequence, CLIParser, the
parameter-count decorators, AliasManager, action registry helpers, the
interrupt-flag mechanism, wait-action dispatch, and more.
"""

import datetime
import types
from unittest.mock import MagicMock, call, patch

import pytest
from soco.exceptions import SoCoUPnPException

import soco_cli.utils as utils
from soco_cli.action_processor import (
    SonosFunction,
    add_sharelink_to_queue,
    get_actions,
    play_sharelink,
)
from soco_cli.aliases import AliasManager
from soco_cli.cmd_parser import CLIParser
from soco_cli.match_speaker_names import speaker_name_matches
from soco_cli.utils import (
    RewindableList,
    check_args,
    convert_to_seconds,
    convert_true_false,
    create_list_of_items_from_range,
    create_time_from_str,
    get_ctrl_c_interrupted,
    playback_state,
    pretty_print_values,
    set_ctrl_c_interrupted,
    set_suspend_sighandling,
)
from soco_cli.wait_actions import process_wait

# ---------------------------------------------------------------------------
# Fixture: run every test in API mode so error_report() never calls os._exit
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def api_mode():
    """Prevent os._exit() calls by enabling API mode for the duration of each test."""
    original = utils.API
    utils.API = True
    yield
    utils.API = original


# ===========================================================================
# convert_to_seconds
# ===========================================================================


class TestConvertToSeconds:
    def test_hh_mm_ss(self):
        assert convert_to_seconds("00:01:01") == 61
        assert convert_to_seconds("01:00:00") == 3600
        assert convert_to_seconds("00:00:00") == 0
        assert convert_to_seconds("00:61:65") == (61 * 60) + 65

    def test_hh_mm(self):
        assert convert_to_seconds("01:30") == 90 * 60
        assert convert_to_seconds("00:00") == 0
        assert convert_to_seconds("02:00") == 7200

    def test_seconds_suffix(self):
        assert convert_to_seconds("12s") == 12
        assert convert_to_seconds("0s") == 0
        assert convert_to_seconds("1.5s") == 1.5

    def test_minutes_suffix(self):
        assert convert_to_seconds("3m") == 3 * 60
        assert convert_to_seconds("0.5m") == 30

    def test_hours_suffix(self):
        assert convert_to_seconds("2h") == 2 * 3600
        assert convert_to_seconds("0.5h") == 1800

    def test_plain_number_defaults_to_seconds(self):
        assert convert_to_seconds("10") == 10
        assert convert_to_seconds("0") == 0

    def test_uppercase_suffix_accepted(self):
        # lower() is applied before suffix checks
        assert convert_to_seconds("5S") == 5
        assert convert_to_seconds("2M") == 120
        assert convert_to_seconds("1H") == 3600

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            convert_to_seconds("")
        with pytest.raises(ValueError):
            convert_to_seconds("abc")
        with pytest.raises(ValueError):
            convert_to_seconds("1x")


# ===========================================================================
# create_time_from_str
# ===========================================================================


class TestCreateTimeFromStr:
    def test_hh_mm(self):
        t = create_time_from_str("09:30")
        assert t == datetime.time(9, 30, 0)

    def test_hh_mm_ss(self):
        t = create_time_from_str("23:59:59")
        assert t == datetime.time(23, 59, 59)

    def test_midnight(self):
        assert create_time_from_str("00:00:00") == datetime.time(0, 0, 0)
        assert create_time_from_str("00:00") == datetime.time(0, 0, 0)

    def test_no_colon_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("1200")

    def test_out_of_range_hour_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("24:00:00")

    def test_out_of_range_minute_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("12:60:00")

    def test_out_of_range_second_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("12:00:60")

    def test_too_many_parts_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("01:02:03:04")

    def test_too_few_parts_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("12")


# ===========================================================================
# convert_true_false
# ===========================================================================


class TestConvertTrueFalse:
    def test_yes_or_no_true(self):
        assert convert_true_false(True) == "Yes"

    def test_yes_or_no_false(self):
        assert convert_true_false(False) == "No"

    def test_on_or_off_true(self):
        assert convert_true_false(True, "onoroff") == "on"

    def test_on_or_off_false(self):
        assert convert_true_false(False, "onoroff") == "off"

    def test_unknown_conversion_returns_none(self):
        assert convert_true_false(True, "unknown_mode") is None
        assert convert_true_false(False, "unknown_mode") is None


# ===========================================================================
# playback_state
# ===========================================================================


class TestPlaybackState:
    def test_stopped(self):
        assert playback_state("STOPPED") == "stopped"

    def test_paused(self):
        assert playback_state("PAUSED_PLAYBACK") == "paused"

    def test_playing(self):
        assert playback_state("PLAYING") == "in progress"

    def test_transitioning(self):
        assert playback_state("TRANSITIONING") == "in a transitioning state"

    def test_unknown_state(self):
        assert playback_state("SOMETHING_ELSE") == "unknown"
        assert playback_state("") == "unknown"


# ===========================================================================
# create_list_of_items_from_range
# ===========================================================================


class TestCreateListOfItemsFromRange:
    def test_single_item(self):
        assert create_list_of_items_from_range("3", 10) == [3]

    def test_comma_separated(self):
        assert create_list_of_items_from_range("1,3,5", 10) == [1, 3, 5]

    def test_simple_range(self):
        assert create_list_of_items_from_range("2-5", 10) == [2, 3, 4, 5]

    def test_all_keyword(self):
        assert create_list_of_items_from_range("all", 5) == [1, 2, 3, 4, 5]

    def test_all_keyword_case_insensitive(self):
        assert create_list_of_items_from_range("ALL", 3) == [1, 2, 3]

    def test_mixed_range_and_singles(self):
        result = create_list_of_items_from_range("1,3-5,7", 10)
        assert result == [1, 3, 4, 5, 7]

    def test_reversed_range_is_sorted(self):
        assert create_list_of_items_from_range("5-2", 10) == [2, 3, 4, 5]

    def test_duplicates_deduplicated(self):
        assert create_list_of_items_from_range("1,1,2", 5) == [1, 2]

    def test_result_is_sorted(self):
        result = create_list_of_items_from_range("5,3,1", 10)
        assert result == sorted(result)

    def test_item_out_of_range_raises(self):
        with pytest.raises(IndexError):
            create_list_of_items_from_range("11", 10)

    def test_zero_raises(self):
        with pytest.raises(IndexError):
            create_list_of_items_from_range("0", 10)

    def test_range_exceeds_limit_raises(self):
        with pytest.raises(IndexError):
            create_list_of_items_from_range("8-12", 10)

    def test_malformed_range_raises(self):
        with pytest.raises((IndexError, ValueError)):
            create_list_of_items_from_range("1-2-3", 10)

    def test_at_upper_limit(self):
        assert create_list_of_items_from_range("10", 10) == [10]


# ===========================================================================
# pretty_print_values
# ===========================================================================


class TestPrettyPrintValues:
    def test_basic_output(self, capsys):
        pretty_print_values({"Key": "Value"})
        out, _ = capsys.readouterr()
        assert "Key" in out
        assert "Value" in out

    def test_empty_dict_produces_no_output(self, capsys):
        pretty_print_values({})
        out, _ = capsys.readouterr()
        assert out == ""

    def test_alignment(self, capsys):
        pretty_print_values({"Short": "MARKER_A", "LongerKey": "MARKER_B"})
        out, _ = capsys.readouterr()
        # Don't use .strip() before splitlines — it would eat the indent on the first line
        lines = [l for l in out.splitlines() if l]
        assert len(lines) == 2
        # Values should start at the same column regardless of key length
        assert lines[0].index("MARKER_A") == lines[1].index("MARKER_B")

    def test_custom_separator(self, capsys):
        pretty_print_values({"K": "V"}, separator="=")
        out, _ = capsys.readouterr()
        assert "=" in out

    def test_sort_by_key(self, capsys):
        pretty_print_values({"Zebra": "z", "Apple": "a"}, sort_by_key=True)
        out, _ = capsys.readouterr()
        lines = out.strip().splitlines()
        assert "Apple" in lines[0]
        assert "Zebra" in lines[1]


# ===========================================================================
# RewindableList
# ===========================================================================


class TestRewindableList:
    def test_basic_iteration(self):
        rl = RewindableList([1, 2, 3])
        assert list(rl) == [1, 2, 3]

    def test_rewind_restarts_iteration(self):
        rl = RewindableList([10, 20, 30])
        first = list(rl)
        second = list(rl)
        assert first == second == [10, 20, 30]

    def test_rewind_mid_iteration(self):
        rl = RewindableList([1, 2, 3])
        it = iter(rl)
        assert next(it) == 1
        rl.rewind()
        assert next(it) == 1  # Restarted from beginning

    def test_rewind_to_valid_index(self):
        rl = RewindableList([10, 20, 30])
        iter(rl)  # initialise
        next(rl)
        next(rl)
        rl.rewind_to(1)
        assert next(rl) == 20

    def test_rewind_to_zero_on_empty(self):
        rl = RewindableList([])
        rl.rewind_to(0)  # Should not raise
        assert rl.index() == 0

    def test_rewind_to_out_of_bounds_raises(self):
        rl = RewindableList([1, 2, 3])
        with pytest.raises(IndexError):
            rl.rewind_to(5)

    def test_rewind_to_negative_raises(self):
        rl = RewindableList([1, 2, 3])
        with pytest.raises(IndexError):
            rl.rewind_to(-1)

    def test_len(self):
        assert len(RewindableList([1, 2, 3])) == 3
        assert len(RewindableList([])) == 0

    def test_getitem(self):
        rl = RewindableList(["a", "b", "c"])
        assert rl[0] == "a"
        assert rl[2] == "c"

    def test_index_tracks_position(self):
        rl = RewindableList([1, 2, 3])
        it = iter(rl)
        assert rl.index() == 0
        next(it)
        assert rl.index() == 1
        next(it)
        assert rl.index() == 2

    def test_str(self):
        rl = RewindableList([1, 2])
        assert "1" in str(rl) and "2" in str(rl)

    def test_stop_iteration(self):
        rl = RewindableList([1])
        it = iter(rl)
        next(it)
        with pytest.raises(StopIteration):
            next(it)

    def test_insert_before_current_index_adjusts_index(self):
        rl = RewindableList([1, 2, 3])
        it = iter(rl)
        next(it)  # index is now 1
        rl.insert(0, 99)  # Insert before current position
        assert rl.index() == 2  # Index should have incremented
        assert rl[0] == 99

    def test_insert_after_current_index_does_not_adjust(self):
        rl = RewindableList([1, 2, 3])
        it = iter(rl)
        next(it)  # index is now 1
        rl.insert(2, 99)  # Insert after current position
        assert rl.index() == 1  # Index unchanged

    def test_pop_next_removes_first_item(self):
        rl = RewindableList([10, 20, 30])
        item = rl.pop_next()
        assert item == 10
        assert len(rl) == 2
        assert rl[0] == 20

    def test_pop_next_adjusts_index(self):
        rl = RewindableList([1, 2, 3])
        it = iter(rl)
        next(it)  # index becomes 1
        rl.pop_next()
        assert rl.index() == 0  # Decremented because index was > 0


# ===========================================================================
# CLIParser
# ===========================================================================


class TestCLIParser:
    def test_single_sequence_no_separator(self):
        p = CLIParser()
        p.parse(["speaker", "volume", "25"])
        assert p.get_sequences() == [["speaker", "volume", "25"]]

    def test_two_sequences(self):
        p = CLIParser()
        p.parse(["s1", "play", ":", "s2", "pause"])
        assert p.get_sequences() == [["s1", "play"], ["s2", "pause"]]

    def test_three_sequences(self):
        p = CLIParser()
        p.parse(["a", ":", "b", ":", "c"])
        assert p.get_sequences() == [["a"], ["b"], ["c"]]

    def test_empty_args(self):
        p = CLIParser()
        p.parse([])
        assert p.get_sequences() == []

    def test_trailing_separator_creates_empty_sequence_excluded(self):
        # A trailing ':' with nothing after it — the empty sequence is not appended
        p = CLIParser()
        p.parse(["a", "b", ":"])
        seqs = p.get_sequences()
        assert seqs == [["a", "b"]]

    def test_single_separator_only(self):
        p = CLIParser()
        p.parse([":"])
        # Produces one empty sequence before the colon; the trailing nothing is dropped
        assert p.get_sequences() == [[]]

    def test_colon_in_value_not_treated_as_separator(self):
        # Only a standalone ':' token acts as a separator
        p = CLIParser()
        p.parse(["speaker", "seek", "01:30:00"])
        assert p.get_sequences() == [["speaker", "seek", "01:30:00"]]


# ===========================================================================
# speaker_name_matches
# ===========================================================================


class TestSpeakerNameMatches:
    def test_exact_match(self):
        found, exact = speaker_name_matches("Bedroom", "Bedroom")
        assert found is True
        assert exact is True

    def test_case_insensitive_is_exact(self):
        found, exact = speaker_name_matches("bedroom", "Bedroom")
        assert found is True
        assert exact is True

    def test_apostrophe_normalisation_is_exact(self):
        # curly apostrophe in stored name, straight in supplied
        found, exact = speaker_name_matches("Kids\u2019 Room", "Kids\u2019 Room")
        assert found is True
        assert exact is True

    def test_partial_start_of_name(self):
        found, exact = speaker_name_matches("bed", "bedroom")
        assert found is True
        assert exact is False

    def test_partial_any_part_of_name(self):
        found, exact = speaker_name_matches("room", "Bedroom")
        assert found is True
        assert exact is False

    def test_no_match(self):
        found, exact = speaker_name_matches("Kitchen", "Bedroom")
        assert found is False
        assert exact is False

    def test_empty_string_matches_any_start(self):
        # Empty string is a prefix of every string
        found, exact = speaker_name_matches("", "Bedroom")
        assert found is True

    def test_longer_name_not_partial_match(self):
        found, _ = speaker_name_matches("BedroomExtra", "Bedroom")
        assert found is False


# ===========================================================================
# AliasManager
# ===========================================================================


class TestAliasManager:
    def test_create_new_alias(self):
        am = AliasManager()
        result, is_new = am.create_alias("sk", "Kitchen stop")
        assert result is True
        assert is_new is True

    def test_create_updates_existing_alias(self):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        result, is_new = am.create_alias("sk", "Kitchen play")
        assert result is True
        assert is_new is False

    def test_action_returns_correct_string(self):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        assert am.action("sk") == "Kitchen stop"

    def test_action_returns_none_for_missing(self):
        am = AliasManager()
        assert am.action("nonexistent") is None

    def test_create_with_none_actions_removes_alias(self):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        result = am.create_alias("sk", None)
        assert result is True
        assert am.action("sk") is None

    def test_create_with_empty_string_removes_alias(self):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        result = am.create_alias("sk", "")
        assert result is True
        assert am.action("sk") is None

    def test_remove_existing_alias(self):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        assert am.remove_alias("sk") is True
        assert am.action("sk") is None

    def test_remove_nonexistent_alias(self):
        am = AliasManager()
        assert am.remove_alias("ghost") is False

    def test_alias_names_empty(self):
        am = AliasManager()
        assert am.alias_names() == []

    def test_alias_names_lists_all(self):
        am = AliasManager()
        am.create_alias("a", "action a")
        am.create_alias("b", "action b")
        assert set(am.alias_names()) == {"a", "b"}

    def test_alias_names_after_remove(self):
        am = AliasManager()
        am.create_alias("a", "action a")
        am.create_alias("b", "action b")
        am.remove_alias("a")
        assert am.alias_names() == ["b"]

    def test_alias_name_stripped(self):
        am = AliasManager()
        am.create_alias("  sk  ", "Kitchen stop")
        assert am.action("sk") == "Kitchen stop"

    def test_print_aliases_empty(self, capsys):
        am = AliasManager()
        am.print_aliases()
        out, _ = capsys.readouterr()
        assert "No current aliases" in out

    def test_print_aliases_shows_names(self, capsys):
        am = AliasManager()
        am.create_alias("myalias", "Kitchen play")
        am.print_aliases()
        out, _ = capsys.readouterr()
        assert "myalias" in out
        assert "Kitchen play" in out

    def test_save_and_load_aliases_to_file(self, tmp_path):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        am.create_alias("sp", "Kitchen play")
        filepath = str(tmp_path / "aliases.txt")
        assert am.save_aliases_to_file(filepath) is True

        am2 = AliasManager()
        with patch.object(am2, "save_aliases"):  # Don't write pickle during test
            assert am2.load_aliases_from_file(filepath) is True
        assert am2.action("sk") == "Kitchen stop"
        assert am2.action("sp") == "Kitchen play"

    def test_load_aliases_from_file_ignores_comments(self, tmp_path):
        filepath = tmp_path / "aliases.txt"
        filepath.write_text("# This is a comment\nsk = Kitchen stop\n")
        am = AliasManager()
        with patch.object(am, "save_aliases"):
            am.load_aliases_from_file(str(filepath))
        # create_alias strips the value, so leading/trailing whitespace is removed
        assert am.action("sk") == "Kitchen stop"

    def test_load_aliases_from_nonexistent_file(self):
        am = AliasManager()
        assert am.load_aliases_from_file("/nonexistent/path/aliases.txt") is False

    def test_aliases_to_text_raw(self):
        am = AliasManager()
        am.create_alias("sk", "Kitchen stop")
        text = am._aliases_to_text(raw=True)
        assert "sk = Kitchen stop" in text

    def test_aliases_to_text_formatted(self):
        am = AliasManager()
        am.create_alias("sk", "STOP_ACTION")
        am.create_alias("longeralias", "PLAY_ACTION")
        text = am._aliases_to_text(raw=False)
        # Find each line by its unique value — don't use .strip() which eats indent
        sk_line = next(l for l in text.splitlines() if "STOP_ACTION" in l)
        long_line = next(l for l in text.splitlines() if "PLAY_ACTION" in l)
        # Shorter alias should be padded so '=' aligns with the longer alias line
        assert sk_line.index("=") == long_line.index("=")


# ===========================================================================
# Parameter-count decorators
# ===========================================================================


class TestParameterDecorators:
    """The decorators inspect args[2] (the parameter list) and args[1] (action name)."""

    def _make_call(self, decorated_func, params):
        """Invoke a decorated action-style function with the given param list."""
        return decorated_func(None, "test_action", params, None, False)

    def test_zero_parameters_allows_empty(self):
        from soco_cli.utils import zero_parameters

        @zero_parameters
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, []) == "ok"

    def test_zero_parameters_rejects_one(self, capsys):
        from soco_cli.utils import zero_parameters

        @zero_parameters
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, ["x"]) is False
        _, err = capsys.readouterr()
        assert "Error" in err

    def test_one_parameter_allows_one(self):
        from soco_cli.utils import one_parameter

        @one_parameter
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, ["x"]) == "ok"

    def test_one_parameter_rejects_zero(self, capsys):
        from soco_cli.utils import one_parameter

        @one_parameter
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, []) is False

    def test_one_parameter_rejects_two(self, capsys):
        from soco_cli.utils import one_parameter

        @one_parameter
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, ["x", "y"]) is False

    def test_zero_or_one_parameter(self):
        from soco_cli.utils import zero_or_one_parameter

        @zero_or_one_parameter
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, []) == "ok"
        assert self._make_call(fn, ["x"]) == "ok"
        assert self._make_call(fn, ["x", "y"]) is False

    def test_one_or_two_parameters(self):
        from soco_cli.utils import one_or_two_parameters

        @one_or_two_parameters
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, ["x"]) == "ok"
        assert self._make_call(fn, ["x", "y"]) == "ok"
        assert self._make_call(fn, []) is False
        assert self._make_call(fn, ["x", "y", "z"]) is False

    def test_two_parameters(self):
        from soco_cli.utils import two_parameters

        @two_parameters
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, ["x", "y"]) == "ok"
        assert self._make_call(fn, ["x"]) is False
        assert self._make_call(fn, []) is False
        assert self._make_call(fn, ["x", "y", "z"]) is False

    def test_zero_one_or_two_parameters(self):
        from soco_cli.utils import zero_one_or_two_parameters

        @zero_one_or_two_parameters
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, []) == "ok"
        assert self._make_call(fn, ["x"]) == "ok"
        assert self._make_call(fn, ["x", "y"]) == "ok"
        assert self._make_call(fn, ["x", "y", "z"]) is False

    def test_one_or_more_parameters(self):
        from soco_cli.utils import one_or_more_parameters

        @one_or_more_parameters
        def fn(speaker, action, params, soco_fn, use_local):
            return "ok"

        assert self._make_call(fn, ["x"]) == "ok"
        assert self._make_call(fn, ["x", "y", "z"]) == "ok"
        assert self._make_call(fn, []) is False


# ===========================================================================
# ctrl-c interrupt flag
# ===========================================================================


class TestCtrlCInterruptFlag:
    def setup_method(self):
        # Reset to known state before each test
        set_ctrl_c_interrupted(False)
        set_suspend_sighandling(False)

    def teardown_method(self):
        set_ctrl_c_interrupted(False)
        set_suspend_sighandling(False)

    def test_default_is_false(self):
        assert get_ctrl_c_interrupted() is False

    def test_set_true(self):
        set_ctrl_c_interrupted(True)
        assert get_ctrl_c_interrupted() is True

    def test_set_false(self):
        set_ctrl_c_interrupted(True)
        set_ctrl_c_interrupted(False)
        assert get_ctrl_c_interrupted() is False

    def test_sig_handler_sets_flag_when_suspended(self):
        import signal as signal_mod

        set_suspend_sighandling(True)
        set_ctrl_c_interrupted(False)
        utils.sig_handler(signal_mod.SIGINT, None)
        assert get_ctrl_c_interrupted() is True

    def test_sig_handler_does_not_set_flag_for_sigterm_when_suspended(self):
        import signal as signal_mod

        set_suspend_sighandling(True)
        set_ctrl_c_interrupted(False)
        utils.sig_handler(signal_mod.SIGTERM, None)
        assert get_ctrl_c_interrupted() is False


# ===========================================================================
# SonosFunction
# ===========================================================================


class TestSonosFunction:
    def test_properties(self):
        fn = lambda: None
        sf = SonosFunction(fn, "play", True)
        assert sf.processing_function is fn
        assert sf.soco_function == "play"
        assert sf.switch_to_coordinator is True

    def test_defaults(self):
        fn = lambda: None
        sf = SonosFunction(fn)
        assert sf.soco_function is None
        assert sf.switch_to_coordinator is False

    def test_switch_to_coordinator_false(self):
        sf = SonosFunction(lambda: None, "volume", False)
        assert sf.switch_to_coordinator is False


# ===========================================================================
# get_actions
# ===========================================================================


class TestGetActions:
    def test_returns_list(self):
        actions = get_actions()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_is_sorted(self):
        actions = get_actions()
        assert actions == sorted(actions)

    def test_known_actions_present(self):
        actions = get_actions()
        for expected in ("volume", "mute", "play", "pause", "pair", "unpair"):
            assert expected in actions

    def test_satellite_actions_present(self):
        actions = get_actions()
        assert "add_satellite_speakers" in actions
        assert "add_satellites" in actions
        assert "separate_satellite_speakers" in actions
        assert "separate_satellites" in actions

    def test_loop_actions_included_by_default(self):
        actions = get_actions(include_loop_actions=True)
        for a in ("loop", "loop_until", "loop_for", "loop_to_start"):
            assert a in actions

    def test_loop_actions_excluded(self):
        actions = get_actions(include_loop_actions=False)
        for a in ("loop", "loop_until", "loop_for"):
            assert a not in actions

    def test_wait_actions_always_present(self):
        # wait/wait_for/wait_until live in the main ACTIONS dict, so they are
        # always returned regardless of the include_wait_actions flag
        for flag in (True, False):
            actions = get_actions(include_wait_actions=flag)
            assert "wait" in actions

    def test_track_follow_actions_excluded(self):
        actions = get_actions(include_track_follow_actions=False)
        for a in ("track_follow", "tf", "track_follow_compact", "tfc"):
            assert a not in actions

    def test_track_follow_actions_included_by_default(self):
        actions = get_actions(include_track_follow_actions=True)
        assert "track_follow" in actions


# ===========================================================================
# check_args
# ===========================================================================


class TestCheckArgs:
    def _args(self, min_netmask=24, timeout=1.0, threads=256):
        return types.SimpleNamespace(
            min_netmask=min_netmask,
            network_discovery_timeout=timeout,
            network_discovery_threads=threads,
        )

    def test_valid_args_returns_none(self):
        assert check_args(self._args()) is None

    def test_boundary_values_valid(self):
        assert check_args(self._args(min_netmask=0, timeout=0.0, threads=1)) is None
        assert (
            check_args(self._args(min_netmask=32, timeout=60.0, threads=32000)) is None
        )

    def test_invalid_min_netmask_low(self):
        msg = check_args(self._args(min_netmask=-1))
        assert msg is not None
        assert "min_netmask" in msg

    def test_invalid_min_netmask_high(self):
        msg = check_args(self._args(min_netmask=33))
        assert msg is not None
        assert "min_netmask" in msg

    def test_invalid_timeout_low(self):
        msg = check_args(self._args(timeout=-0.1))
        assert msg is not None
        assert "network_timeout" in msg

    def test_invalid_timeout_high(self):
        msg = check_args(self._args(timeout=60.1))
        assert msg is not None
        assert "network_timeout" in msg

    def test_invalid_threads_low(self):
        msg = check_args(self._args(threads=0))
        assert msg is not None
        assert "threads" in msg

    def test_invalid_threads_high(self):
        msg = check_args(self._args(threads=32001))
        assert msg is not None
        assert "threads" in msg

    def test_multiple_invalid_args_all_reported(self):
        msg = check_args(self._args(min_netmask=99, timeout=99.0, threads=0))
        assert "min_netmask" in msg
        assert "network_timeout" in msg
        assert "threads" in msg


# ===========================================================================
# process_wait (wait_actions)
# ===========================================================================


class TestProcessWait:
    def test_wait_sleeps_for_correct_duration(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "10s"])
            mock_sleep.assert_called_once_with(10.0)

    def test_wait_for_sleeps_for_correct_duration(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait_for", "2m"])
            mock_sleep.assert_called_once_with(120.0)

    def test_wait_hh_mm_ss_format(self):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "00:01:30"])
            mock_sleep.assert_called_once_with(90)

    def test_wait_missing_param_reports_error(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait"])
            mock_sleep.assert_not_called()
            _, err = capsys.readouterr()
            assert "Error" in err

    def test_wait_until_calls_sleep(self):
        # Mock seconds_until to return a fixed duration
        with patch("soco_cli.wait_actions.seconds_until", return_value=300):
            with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
                process_wait(["wait_until", "12:00"])
                mock_sleep.assert_called_once_with(300)

    def test_wait_until_missing_param_reports_error(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait_until"])
            mock_sleep.assert_not_called()
            _, err = capsys.readouterr()
            assert "Error" in err

    def test_wait_invalid_time_format_reports_error(self, capsys):
        with patch("soco_cli.wait_actions.time.sleep") as mock_sleep:
            process_wait(["wait", "notatime"])
            # Error is reported; sleep is still called with the fallback duration of 0
            mock_sleep.assert_called_once_with(0)
            _, err = capsys.readouterr()
            assert "Error" in err


# ===========================================================================
# add_sharelink_to_queue / play_sharelink
# ===========================================================================

SPOTIFY_URI_1 = "https://open.spotify.com/track/AAA"
SPOTIFY_URI_2 = "https://open.spotify.com/album/BBB"
INVALID_URI = "not_a_sharelink"


def _make_speaker(queue_size=5):
    speaker = MagicMock()
    speaker.queue_size = queue_size
    return speaker


def _make_share_link_plugin(valid_uris, add_return_values=None):
    """
    Return a mock ShareLinkPlugin instance.
    valid_uris: set of URIs that is_share_link() should accept.
    add_return_values: list of return values for sequential add_share_link_to_queue calls.
    """
    plugin = MagicMock()
    plugin.is_share_link.side_effect = lambda uri: uri in valid_uris
    if add_return_values is not None:
        plugin.add_share_link_to_queue.side_effect = add_return_values
    return plugin


class TestAddSharelinkToQueue:
    def _call(self, speaker, args):
        return add_sharelink_to_queue(
            speaker, "add_sharelink_to_queue", args, None, False
        )

    def test_single_uri_appends_and_prints_position(self, capsys):
        speaker = _make_speaker(queue_size=4)
        plugin = _make_share_link_plugin({SPOTIFY_URI_1}, add_return_values=[5])
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch(
                "soco_cli.action_processor.save_queue_insertion_position"
            ) as mock_save:
                result = self._call(speaker, [SPOTIFY_URI_1])
        assert result is True
        plugin.add_share_link_to_queue.assert_called_once_with(SPOTIFY_URI_1, 5)
        mock_save.assert_called_once_with(5)
        assert capsys.readouterr().out.strip() == "5"

    def test_single_uri_with_position(self):
        speaker = _make_speaker(queue_size=10)
        plugin = _make_share_link_plugin({SPOTIFY_URI_1}, add_return_values=[3])
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch(
                "soco_cli.action_processor.get_queue_insertion_position", return_value=3
            ) as mock_pos:
                with patch("soco_cli.action_processor.save_queue_insertion_position"):
                    result = self._call(speaker, [SPOTIFY_URI_1, "3"])
        assert result is True
        mock_pos.assert_called_once()
        plugin.add_share_link_to_queue.assert_called_once_with(SPOTIFY_URI_1, 3)

    def test_multiple_uris_appended_in_order(self, capsys):
        speaker = _make_speaker(queue_size=4)
        plugin = _make_share_link_plugin(
            {SPOTIFY_URI_1, SPOTIFY_URI_2}, add_return_values=[5, 8]
        )
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch("soco_cli.action_processor.save_queue_insertion_position"):
                result = self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2])
        assert result is True
        assert plugin.add_share_link_to_queue.call_count == 2
        # First call uses queue_size + 1; second also uses queue_size + 1 (appended)
        first_call_pos = plugin.add_share_link_to_queue.call_args_list[0][0][1]
        assert first_call_pos == 5
        assert capsys.readouterr().out.strip() == "5"

    def test_multiple_uris_with_position_first_uses_position(self):
        speaker = _make_speaker(queue_size=10)
        plugin = _make_share_link_plugin(
            {SPOTIFY_URI_1, SPOTIFY_URI_2}, add_return_values=[3, 7]
        )
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch(
                "soco_cli.action_processor.get_queue_insertion_position", return_value=3
            ):
                with patch("soco_cli.action_processor.save_queue_insertion_position"):
                    result = self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2, "3"])
        assert result is True
        first_call_pos = plugin.add_share_link_to_queue.call_args_list[0][0][1]
        second_call_pos = plugin.add_share_link_to_queue.call_args_list[1][0][1]
        assert first_call_pos == 3
        # Second uses queue_size + 1, not the position
        assert second_call_pos == speaker.queue_size + 1

    def test_only_first_position_is_saved(self):
        speaker = _make_speaker(queue_size=4)
        plugin = _make_share_link_plugin(
            {SPOTIFY_URI_1, SPOTIFY_URI_2}, add_return_values=[5, 9]
        )
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch(
                "soco_cli.action_processor.save_queue_insertion_position"
            ) as mock_save:
                self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2])
        mock_save.assert_called_once_with(5)

    def test_invalid_single_uri_returns_false(self, capsys):
        speaker = _make_speaker()
        plugin = _make_share_link_plugin(set())
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            result = self._call(speaker, [INVALID_URI])
        assert result is False
        plugin.add_share_link_to_queue.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_invalid_uri_in_list_prevents_all_adds(self):
        """Validation happens before any URI is added."""
        speaker = _make_speaker()
        plugin = _make_share_link_plugin({SPOTIFY_URI_1})  # SPOTIFY_URI_2 invalid
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            result = self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2])
        assert result is False
        plugin.add_share_link_to_queue.assert_not_called()

    def test_invalid_last_arg_treated_as_uri_not_position(self, capsys):
        """An unrecognised final arg is validated as a URI, not passed to
        get_queue_insertion_position."""
        speaker = _make_speaker()
        plugin = _make_share_link_plugin({SPOTIFY_URI_1})  # INVALID_URI not valid
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            result = self._call(speaker, [SPOTIFY_URI_1, INVALID_URI])
        assert result is False
        plugin.add_share_link_to_queue.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_upnp_exception_returns_false(self, capsys):
        speaker = _make_speaker()
        plugin = _make_share_link_plugin({SPOTIFY_URI_1})
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch("soco_cli.action_processor.SoCoUPnPException", Exception):
                plugin.add_share_link_to_queue.side_effect = Exception("fail")
                result = self._call(speaker, [SPOTIFY_URI_1])
        assert result is False
        assert "Error" in capsys.readouterr().err

    def test_zero_args_rejected_by_decorator(self, capsys):
        speaker = _make_speaker()
        result = add_sharelink_to_queue(
            speaker, "add_sharelink_to_queue", [], None, False
        )
        assert result is False


class TestPlaySharelink:
    def _call(self, speaker, args):
        return play_sharelink(speaker, "play_sharelink", args, None, False)

    def test_single_uri_adds_and_plays(self):
        speaker = _make_speaker(queue_size=4)
        plugin = _make_share_link_plugin({SPOTIFY_URI_1}, add_return_values=[5])
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch("soco_cli.action_processor.save_queue_insertion_position"):
                result = self._call(speaker, [SPOTIFY_URI_1])
        assert result is True
        plugin.add_share_link_to_queue.assert_called_once_with(SPOTIFY_URI_1, 5)
        # play_from_queue uses 0-based index
        speaker.play_from_queue.assert_called_once_with(4)

    def test_single_uri_with_position(self):
        speaker = _make_speaker(queue_size=10)
        plugin = _make_share_link_plugin({SPOTIFY_URI_1}, add_return_values=[3])
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch(
                "soco_cli.action_processor.get_queue_insertion_position", return_value=3
            ):
                with patch("soco_cli.action_processor.save_queue_insertion_position"):
                    result = self._call(speaker, [SPOTIFY_URI_1, "3"])
        assert result is True
        plugin.add_share_link_to_queue.assert_called_once_with(SPOTIFY_URI_1, 3)
        speaker.play_from_queue.assert_called_once_with(2)

    def test_multiple_uris_plays_from_first_position(self):
        speaker = _make_speaker(queue_size=4)
        plugin = _make_share_link_plugin(
            {SPOTIFY_URI_1, SPOTIFY_URI_2}, add_return_values=[5, 8]
        )
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch("soco_cli.action_processor.save_queue_insertion_position"):
                result = self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2])
        assert result is True
        assert plugin.add_share_link_to_queue.call_count == 2
        # Playback starts at the first added position (0-based)
        speaker.play_from_queue.assert_called_once_with(4)

    def test_multiple_uris_with_position_first_uses_position(self):
        speaker = _make_speaker(queue_size=10)
        plugin = _make_share_link_plugin(
            {SPOTIFY_URI_1, SPOTIFY_URI_2}, add_return_values=[3, 9]
        )
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch(
                "soco_cli.action_processor.get_queue_insertion_position", return_value=3
            ):
                with patch("soco_cli.action_processor.save_queue_insertion_position"):
                    result = self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2, "3"])
        assert result is True
        first_call_pos = plugin.add_share_link_to_queue.call_args_list[0][0][1]
        assert first_call_pos == 3
        speaker.play_from_queue.assert_called_once_with(2)

    def test_invalid_uri_prevents_any_add_or_play(self, capsys):
        speaker = _make_speaker()
        plugin = _make_share_link_plugin(set())
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            result = self._call(speaker, [INVALID_URI])
        assert result is False
        plugin.add_share_link_to_queue.assert_not_called()
        speaker.play_from_queue.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_invalid_uri_in_list_prevents_all_adds_and_play(self):
        """Validation happens before any URI is added."""
        speaker = _make_speaker()
        plugin = _make_share_link_plugin({SPOTIFY_URI_1})  # SPOTIFY_URI_2 invalid
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            result = self._call(speaker, [SPOTIFY_URI_1, SPOTIFY_URI_2])
        assert result is False
        plugin.add_share_link_to_queue.assert_not_called()
        speaker.play_from_queue.assert_not_called()

    def test_invalid_last_arg_treated_as_uri_not_position(self, capsys):
        """An unrecognised final arg is validated as a URI, not passed to
        get_queue_insertion_position."""
        speaker = _make_speaker()
        plugin = _make_share_link_plugin({SPOTIFY_URI_1})  # INVALID_URI not valid
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            result = self._call(speaker, [SPOTIFY_URI_1, INVALID_URI])
        assert result is False
        plugin.add_share_link_to_queue.assert_not_called()
        speaker.play_from_queue.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_upnp_exception_does_not_play(self, capsys):
        speaker = _make_speaker()
        plugin = _make_share_link_plugin({SPOTIFY_URI_1})
        with patch("soco_cli.action_processor.ShareLinkPlugin", return_value=plugin):
            with patch("soco_cli.action_processor.SoCoUPnPException", Exception):
                plugin.add_share_link_to_queue.side_effect = Exception("fail")
                result = self._call(speaker, [SPOTIFY_URI_1])
        assert result is False
        speaker.play_from_queue.assert_not_called()
        assert "Error" in capsys.readouterr().err

    def test_zero_args_rejected_by_decorator(self):
        speaker = _make_speaker()
        result = play_sharelink(speaker, "play_sharelink", [], None, False)
        assert result is False
