"""Extended tests for utils.py — covering functions not tested in test_utils.py."""

import argparse
import datetime as real_datetime
from unittest.mock import MagicMock, patch

import pytest

import soco_cli.utils as utils
from soco_cli.utils import (
    RewindableList,
    SpeakerCache,
    check_args,
    convert_true_false,
    create_list_of_items_from_range,
    create_time_from_str,
    find_by_name,
    forget_event_sub,
    one_or_more_parameters,
    one_or_two_parameters,
    one_parameter,
    playback_state,
    pretty_print_values,
    remember_event_sub,
    seconds_until,
    two_parameters,
    unsub_all_remembered_event_subs,
    zero_one_or_two_parameters,
    zero_or_one_parameter,
    zero_parameters,
)


@pytest.fixture(autouse=True)
def api_mode():
    original = utils.API
    utils.API = True
    yield
    utils.API = original


@pytest.fixture(autouse=True)
def reset_subs():
    """Ensure the global SUBS_LIST is empty between tests."""
    utils.SUBS_LIST = set()
    yield
    utils.SUBS_LIST = set()


# ---------------------------------------------------------------------------
# create_time_from_str
# ---------------------------------------------------------------------------


class TestCreateTimeFromStr:
    def test_hh_mm(self):
        t = create_time_from_str("13:30")
        assert t == real_datetime.time(13, 30, 0)

    def test_hh_mm_ss(self):
        t = create_time_from_str("08:15:45")
        assert t == real_datetime.time(8, 15, 45)

    def test_midnight(self):
        t = create_time_from_str("00:00:00")
        assert t == real_datetime.time(0, 0, 0)

    def test_end_of_day(self):
        t = create_time_from_str("23:59:59")
        assert t == real_datetime.time(23, 59, 59)

    def test_no_colon_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("1330")

    def test_too_many_parts_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("13:30:00:00")

    def test_out_of_range_hour_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("25:00:00")

    def test_out_of_range_minute_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("12:60:00")

    def test_out_of_range_second_raises(self):
        with pytest.raises(ValueError):
            create_time_from_str("12:30:60")

    def test_non_numeric_raises(self):
        with pytest.raises((ValueError, TypeError)):
            create_time_from_str("HH:MM")


# ---------------------------------------------------------------------------
# seconds_until
# ---------------------------------------------------------------------------


class TestSecondsUntil:
    def _mock_now(self, h, m, s=0):
        """Patch datetime.datetime.now() to return a fixed time."""
        mock_dt = MagicMock()
        mock_dt.time.return_value = real_datetime.time(h, m, s)
        return mock_dt

    def test_future_time_returns_positive_seconds(self):
        with patch("soco_cli.utils.datetime") as mock_dt_mod:
            mock_dt_mod.time = real_datetime.time
            mock_dt_mod.timedelta = real_datetime.timedelta
            mock_dt_mod.datetime.now.return_value = self._mock_now(12, 0, 0)
            result = seconds_until("13:00:00")
        assert result == 3600

    def test_past_time_wraps_to_next_day(self):
        with patch("soco_cli.utils.datetime") as mock_dt_mod:
            mock_dt_mod.time = real_datetime.time
            mock_dt_mod.timedelta = real_datetime.timedelta
            mock_dt_mod.datetime.now.return_value = self._mock_now(14, 0, 0)
            result = seconds_until("13:00:00")
        # 13:00 has passed; next occurrence is 23 hours away
        assert result == 23 * 3600

    def test_hh_mm_format(self):
        with patch("soco_cli.utils.datetime") as mock_dt_mod:
            mock_dt_mod.time = real_datetime.time
            mock_dt_mod.timedelta = real_datetime.timedelta
            mock_dt_mod.datetime.now.return_value = self._mock_now(10, 0, 0)
            result = seconds_until("10:30")
        assert result == 1800

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            seconds_until("not_a_time")


# ---------------------------------------------------------------------------
# convert_true_false
# ---------------------------------------------------------------------------


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
        assert convert_true_false(True, "unknown") is None


# ---------------------------------------------------------------------------
# playback_state
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# find_by_name
# ---------------------------------------------------------------------------


class TestFindByName:
    def _item(self, title):
        m = MagicMock()
        m.title = title
        return m

    def test_strict_match_found(self):
        items = [self._item("Jazz"), self._item("Classical")]
        result = find_by_name(items, "Jazz")
        assert result.title == "Jazz"

    def test_fuzzy_match_case_insensitive(self):
        items = [self._item("Classic FM"), self._item("Jazz Radio")]
        result = find_by_name(items, "classic")
        assert result.title == "Classic FM"

    def test_strict_match_takes_priority_over_fuzzy(self):
        items = [self._item("My Jazz"), self._item("Jazz")]
        # "Jazz" is an exact match for items[1]; items[0] is fuzzy
        result = find_by_name(items, "Jazz")
        assert result.title == "Jazz"

    def test_not_found_returns_none(self):
        items = [self._item("Jazz"), self._item("Classical")]
        assert find_by_name(items, "Rock") is None

    def test_empty_list_returns_none(self):
        assert find_by_name([], "Jazz") is None

    def test_fuzzy_substring_match(self):
        items = [self._item("BBC Radio 6 Music")]
        result = find_by_name(items, "Radio 6")
        assert result is not None


# ---------------------------------------------------------------------------
# create_list_of_items_from_range
# ---------------------------------------------------------------------------


class TestCreateListOfItemsFromRange:
    def test_single_item(self):
        assert create_list_of_items_from_range("3", 5) == [3]

    def test_range(self):
        assert create_list_of_items_from_range("2-4", 5) == [2, 3, 4]

    def test_reversed_range_normalised(self):
        assert create_list_of_items_from_range("4-2", 5) == [2, 3, 4]

    def test_multiple_items_comma_separated(self):
        assert create_list_of_items_from_range("1,3,5", 5) == [1, 3, 5]

    def test_mix_of_single_and_range(self):
        result = create_list_of_items_from_range("1,3-5", 5)
        assert result == [1, 3, 4, 5]

    def test_all_keyword(self):
        assert create_list_of_items_from_range("all", 4) == [1, 2, 3, 4]

    def test_all_keyword_case_insensitive(self):
        assert create_list_of_items_from_range("ALL", 3) == [1, 2, 3]

    def test_duplicates_removed(self):
        result = create_list_of_items_from_range("1,1,2", 5)
        assert result == [1, 2]

    def test_item_out_of_range_raises(self):
        with pytest.raises(IndexError):
            create_list_of_items_from_range("6", 5)

    def test_zero_out_of_range_raises(self):
        with pytest.raises(IndexError):
            create_list_of_items_from_range("0", 5)

    def test_range_exceeds_limit_raises(self):
        with pytest.raises(IndexError):
            create_list_of_items_from_range("3-7", 5)

    def test_result_is_sorted(self):
        result = create_list_of_items_from_range("5,1,3", 5)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# pretty_print_values
# ---------------------------------------------------------------------------


class TestPrettyPrintValues:
    def test_basic_output(self, capsys):
        pretty_print_values({"Name": "Kitchen", "IP": "192.168.1.1"})
        out = capsys.readouterr().out
        assert "Name" in out
        assert "Kitchen" in out
        assert "IP" in out
        assert "192.168.1.1" in out

    def test_empty_dict_prints_nothing(self, capsys):
        pretty_print_values({})
        assert capsys.readouterr().out == ""

    def test_values_aligned(self, capsys):
        # The spacer pads after the separator so that values start at the same column,
        # not the colons (which immediately follow the key).
        pretty_print_values({"Short": "a_val", "LongerKey": "b_val"})
        out = capsys.readouterr().out
        lines = [l for l in out.splitlines() if l.strip()]
        value_positions = [l.index("_val") - 1 for l in lines]
        assert len(set(value_positions)) == 1

    def test_sort_by_key(self, capsys):
        pretty_print_values({"Z": "last", "A": "first"}, sort_by_key=True)
        out = capsys.readouterr().out
        assert out.index("A") < out.index("Z")


# ---------------------------------------------------------------------------
# RewindableList
# ---------------------------------------------------------------------------


class TestRewindableList:
    def test_len(self):
        rl = RewindableList([1, 2, 3])
        assert len(rl) == 3

    def test_getitem(self):
        rl = RewindableList(["a", "b", "c"])
        assert rl[0] == "a"
        assert rl[2] == "c"

    def test_iteration(self):
        rl = RewindableList([10, 20, 30])
        assert list(rl) == [10, 20, 30]

    def test_iteration_rewinds_on_each_iter_call(self):
        rl = RewindableList([1, 2])
        list(rl)  # consume
        assert list(rl) == [1, 2]  # rewinds automatically

    def test_rewind_resets_index(self):
        rl = RewindableList([1, 2, 3])
        next(rl)
        next(rl)
        rl.rewind()
        assert rl.index() == 0

    def test_rewind_to_valid_index(self):
        rl = RewindableList([1, 2, 3])
        rl.rewind_to(1)
        assert rl.index() == 1

    def test_rewind_to_zero_on_empty_list(self):
        rl = RewindableList([])
        rl.rewind_to(0)
        assert rl.index() == 0

    def test_rewind_to_invalid_raises(self):
        rl = RewindableList([1, 2])
        with pytest.raises(IndexError):
            rl.rewind_to(5)

    def test_index_increments_on_next(self):
        rl = RewindableList([1, 2, 3])
        assert rl.index() == 0
        next(rl)
        assert rl.index() == 1

    def test_pop_next_removes_first_element(self):
        rl = RewindableList([10, 20, 30])
        item = rl.pop_next()
        assert item == 10
        assert list(rl) == [20, 30]

    def test_pop_next_on_empty_raises(self):
        rl = RewindableList([])
        with pytest.raises(IndexError):
            rl.pop_next()

    def test_insert_at_zero_increments_index(self):
        rl = RewindableList([2, 3])
        next(rl)  # index -> 1
        rl.insert(0, 1)
        assert rl.index() == 2
        assert rl[0] == 1

    def test_insert_at_index_equal_to_current_increments_index(self):
        # insert(index, e) increments _index when index <= _index (uses <=, not <)
        rl = RewindableList([1, 3])
        next(rl)  # _index -> 1
        rl.insert(1, 2)
        assert rl.index() == 2  # incremented because 1 <= 1
        assert rl[1] == 2

    def test_str_representation(self):
        rl = RewindableList([1, 2])
        assert "[1, 2]" in str(rl)

    def test_stop_iteration_at_end(self):
        rl = RewindableList([1])
        next(rl)
        with pytest.raises(StopIteration):
            next(rl)


# ---------------------------------------------------------------------------
# Parameter decorators
# ---------------------------------------------------------------------------


def _make_action(decorator):
    """Wrap a trivial function with the given decorator."""

    @decorator
    def action(speaker, action_name, args, soco_fn, use_local):
        return "ok"

    return action


class TestParameterDecorators:
    def test_zero_parameters_passes_on_empty(self):
        f = _make_action(zero_parameters)
        assert f(None, "play", [], None, False) == "ok"

    def test_zero_parameters_fails_on_one(self):
        f = _make_action(zero_parameters)
        assert f(None, "play", ["extra"], None, False) is False

    def test_one_parameter_passes_on_one(self):
        f = _make_action(one_parameter)
        assert f(None, "vol", ["50"], None, False) == "ok"

    def test_one_parameter_fails_on_zero(self):
        f = _make_action(one_parameter)
        assert f(None, "vol", [], None, False) is False

    def test_one_parameter_fails_on_two(self):
        f = _make_action(one_parameter)
        assert f(None, "vol", ["50", "extra"], None, False) is False

    def test_zero_or_one_passes_on_zero(self):
        f = _make_action(zero_or_one_parameter)
        assert f(None, "play", [], None, False) == "ok"

    def test_zero_or_one_passes_on_one(self):
        f = _make_action(zero_or_one_parameter)
        assert f(None, "play", ["arg"], None, False) == "ok"

    def test_zero_or_one_fails_on_two(self):
        f = _make_action(zero_or_one_parameter)
        assert f(None, "play", ["a", "b"], None, False) is False

    def test_one_or_two_passes_on_one(self):
        f = _make_action(one_or_two_parameters)
        assert f(None, "fav", ["Jazz"], None, False) == "ok"

    def test_one_or_two_passes_on_two(self):
        f = _make_action(one_or_two_parameters)
        assert f(None, "fav", ["Jazz", "next"], None, False) == "ok"

    def test_one_or_two_fails_on_zero(self):
        f = _make_action(one_or_two_parameters)
        assert f(None, "fav", [], None, False) is False

    def test_two_parameters_passes_on_two(self):
        f = _make_action(two_parameters)
        assert f(None, "eq", ["bass", "5"], None, False) == "ok"

    def test_two_parameters_fails_on_one(self):
        f = _make_action(two_parameters)
        assert f(None, "eq", ["bass"], None, False) is False

    def test_zero_one_or_two_passes_on_zero(self):
        f = _make_action(zero_one_or_two_parameters)
        assert f(None, "x", [], None, False) == "ok"

    def test_zero_one_or_two_passes_on_two(self):
        f = _make_action(zero_one_or_two_parameters)
        assert f(None, "x", ["a", "b"], None, False) == "ok"

    def test_zero_one_or_two_fails_on_three(self):
        f = _make_action(zero_one_or_two_parameters)
        assert f(None, "x", ["a", "b", "c"], None, False) is False

    def test_one_or_more_passes_on_one(self):
        f = _make_action(one_or_more_parameters)
        assert f(None, "x", ["a"], None, False) == "ok"

    def test_one_or_more_passes_on_many(self):
        f = _make_action(one_or_more_parameters)
        assert f(None, "x", ["a", "b", "c", "d"], None, False) == "ok"

    def test_one_or_more_fails_on_zero(self):
        f = _make_action(one_or_more_parameters)
        assert f(None, "x", [], None, False) is False


# ---------------------------------------------------------------------------
# check_args
# ---------------------------------------------------------------------------


class TestCheckArgs:
    def _make_args(self, min_netmask=24, timeout=1.0, threads=256):
        args = MagicMock()
        args.min_netmask = min_netmask
        args.network_discovery_timeout = timeout
        args.network_discovery_threads = threads
        return args

    def test_valid_args_returns_none(self):
        assert check_args(self._make_args()) is None

    def test_invalid_netmask_low(self):
        result = check_args(self._make_args(min_netmask=-1))
        assert result is not None
        assert "min_netmask" in result

    def test_invalid_netmask_high(self):
        result = check_args(self._make_args(min_netmask=33))
        assert result is not None

    def test_boundary_netmask_0(self):
        assert check_args(self._make_args(min_netmask=0)) is None

    def test_boundary_netmask_32(self):
        assert check_args(self._make_args(min_netmask=32)) is None

    def test_invalid_timeout_negative(self):
        result = check_args(self._make_args(timeout=-1.0))
        assert result is not None

    def test_invalid_timeout_too_large(self):
        result = check_args(self._make_args(timeout=61.0))
        assert result is not None

    def test_invalid_threads_zero(self):
        result = check_args(self._make_args(threads=0))
        assert result is not None

    def test_multiple_errors_reported(self):
        result = check_args(self._make_args(min_netmask=-1, timeout=-1.0))
        assert result is not None
        assert len(result) > 10  # contains two error messages


# ---------------------------------------------------------------------------
# Event subscription tracking
# ---------------------------------------------------------------------------


class TestEventSubscriptions:
    def test_remember_and_forget(self):
        sub = MagicMock()
        remember_event_sub(sub)
        assert sub in utils.SUBS_LIST
        forget_event_sub(sub)
        assert sub not in utils.SUBS_LIST

    def test_forget_nonexistent_does_not_raise(self):
        sub = MagicMock()
        forget_event_sub(sub)  # should not raise

    def test_unsub_all_calls_unsubscribe(self):
        sub1 = MagicMock()
        sub2 = MagicMock()
        remember_event_sub(sub1)
        remember_event_sub(sub2)
        with patch("soco_cli.utils.event_unsubscribe") as mock_unsub:
            unsub_all_remembered_event_subs()
        assert mock_unsub.call_count == 2
        assert utils.SUBS_LIST == set()

    def test_unsub_all_clears_list(self):
        sub = MagicMock()
        remember_event_sub(sub)
        with patch("soco_cli.utils.event_unsubscribe"):
            unsub_all_remembered_event_subs()
        assert utils.SUBS_LIST == set()


# ---------------------------------------------------------------------------
# SpeakerCache — in-memory operations (no network)
# ---------------------------------------------------------------------------


class TestSpeakerCache:
    def test_cache_speakers(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        mock_spk.player_name = "Kitchen"
        sc.cache_speakers([mock_spk])
        assert (mock_spk, "Kitchen") in sc._cache

    def test_add_speaker(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        mock_spk.player_name = "Bedroom"
        sc.add(mock_spk)
        assert (mock_spk, "Bedroom") in sc._cache

    def test_exists_false_when_empty(self):
        sc = SpeakerCache()
        assert sc.exists is False

    def test_exists_true_after_add(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        mock_spk.player_name = "Kitchen"
        sc.add(mock_spk)
        assert sc.exists is True

    def test_find_exact_match(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        sc._cache.add((mock_spk, "Kitchen"))
        assert sc.find("Kitchen") is mock_spk

    def test_find_partial_match(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        sc._cache.add((mock_spk, "Kitchen"))
        assert sc.find("Kit") is mock_spk

    def test_find_no_match_returns_none(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        sc._cache.add((mock_spk, "Kitchen"))
        assert sc.find("Bedroom") is None

    def test_find_ambiguous_returns_none(self, capsys):
        sc = SpeakerCache()
        sc._cache.add((MagicMock(), "Kitchen Front"))
        sc._cache.add((MagicMock(), "Kitchen Back"))
        result = sc.find("Kitchen")
        assert result is None
        capsys.readouterr()  # suppress error output

    def test_rename_speaker(self):
        sc = SpeakerCache()
        mock_spk = MagicMock()
        sc._cache.add((mock_spk, "Kitchen"))
        result = sc.rename_speaker("Kitchen", "Dining Room")
        assert result is True
        assert (mock_spk, "Dining Room") in sc._cache
        assert (mock_spk, "Kitchen") not in sc._cache

    def test_rename_nonexistent_returns_false(self):
        sc = SpeakerCache()
        assert sc.rename_speaker("Nonexistent", "New Name") is False

    def test_find_indirect_exact_match(self):
        sc = SpeakerCache()
        inner = MagicMock()
        inner.player_name = "Kitchen"
        outer = MagicMock()
        outer.visible_zones = [inner]
        sc._cache.add((outer, "GroupName"))
        assert sc.find_indirect("Kitchen") is inner

    def test_find_indirect_no_match_returns_none(self):
        sc = SpeakerCache()
        inner = MagicMock()
        inner.player_name = "Kitchen"
        outer = MagicMock()
        outer.visible_zones = [inner]
        sc._cache.add((outer, "GroupName"))
        assert sc.find_indirect("Bedroom") is None
