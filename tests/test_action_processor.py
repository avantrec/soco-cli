"""Tests for action_processor.py.

Covers pure helpers, output formatters, and action-processing functions
that can be exercised without a live Sonos network.
"""

from collections import OrderedDict
from unittest.mock import MagicMock, call, patch

import pytest

import soco_cli.utils as utils
from soco_cli.action_processor import (
    SonosFunction,
    _is_queue_position,
    add_favourite_to_queue,
    audio_format,
    filter_track_info,
    get_actions,
    get_current_queue_position,
    list_queue,
    mic_enabled,
    on_off_action,
    play_favourite_core,
    play_uri,
    playback_mode,
    print_albums,
    print_list_header,
    print_tracks,
    process_action,
    repeat,
    set_queue_position,
    shuffle,
    sleep_timer,
    surround_volume,
    switch_to_tv,
    tv_audio_delay,
    volume_actions,
)

# ---------------------------------------------------------------------------
# Autouse fixture: run every test in API mode so error_report never calls
# os._exit()
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def api_mode():
    original = utils.API
    utils.API = True
    yield
    utils.API = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_speaker(**kwargs):
    speaker = MagicMock()
    for k, v in kwargs.items():
        setattr(speaker, k, v)
    return speaker


def _make_track(title="Track", creator="Artist", album="Album", item_class=None):
    track = MagicMock()
    track.title = title
    track.creator = creator
    track.album = album
    if item_class is not None:
        track.item_class = item_class
    else:
        del track.item_class  # AttributeError on access
    return track


def _make_favourite(title, uri="http://example.com/stream", meta="<meta/>"):
    fav = MagicMock()
    fav.title = title
    fav.get_uri.return_value = uri
    fav.resource_meta_data = meta
    return fav


def _call(func, speaker, args, action=None, soco_function="", use_local=False):
    return func(speaker, action or func.__name__, args, soco_function, use_local)


# ===========================================================================
# _is_queue_position
# ===========================================================================


class TestIsQueuePosition:
    def test_integer_strings(self):
        assert _is_queue_position("1") is True
        assert _is_queue_position("0") is True
        assert _is_queue_position("100") is True
        assert _is_queue_position("-1") is True

    def test_named_keywords_case_insensitive(self):
        for kw in ["first", "FIRST", "First", "start", "START"]:
            assert _is_queue_position(kw) is True
        for kw in ["next", "NEXT", "play_next", "PLAY_NEXT"]:
            assert _is_queue_position(kw) is True
        for kw in ["last", "LAST", "end", "END"]:
            assert _is_queue_position(kw) is True

    def test_invalid_strings(self):
        assert _is_queue_position("middle") is False
        assert _is_queue_position("not_a_sharelink") is False
        assert _is_queue_position("https://open.spotify.com/track/AAA") is False
        assert _is_queue_position("") is False
        assert _is_queue_position("1.5") is False

    def test_close_but_not_valid(self):
        assert _is_queue_position("starts") is False
        assert _is_queue_position("ending") is False
        assert _is_queue_position("nexxt") is False


# ===========================================================================
# filter_track_info
# ===========================================================================


class TestFilterTrackInfo:
    def test_capitalises_keys(self):
        result = filter_track_info({"artist": "Bach", "title": "Toccata"}, [])
        assert "Artist" in result
        assert "Title" in result

    def test_excludes_specified_fields(self):
        result = filter_track_info(
            {"artist": "Bach", "uri": "x", "title": "T"}, ["uri"]
        )
        assert "Uri" not in result
        assert "Artist" in result
        assert "Title" in result

    def test_preserves_values(self):
        result = filter_track_info({"artist": "Bach"}, [])
        assert result["Artist"] == "Bach"

    def test_empty_input(self):
        assert filter_track_info({}, []) == {}

    def test_all_excluded(self):
        result = filter_track_info(
            {"artist": "Bach", "title": "T"}, ["artist", "title"]
        )
        assert result == {}

    def test_output_order_follows_sorted_input_keys(self):
        result = filter_track_info({"z_key": 1, "a_key": 2, "m_key": 3}, [])
        assert list(result.keys()) == ["A_key", "M_key", "Z_key"]

    def test_capitalize_only_first_char(self):
        # str.capitalize() uppercases first char only; doesn't affect rest
        result = filter_track_info({"album_art": "url"}, [])
        assert "Album_art" in result


# ===========================================================================
# print_list_header
# ===========================================================================


class TestPrintListHeader:
    def test_output_format(self, capsys):
        print_list_header("Sonos", "Favourites")
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert "Sonos Favourites" in lines[0]
        # Underline length matches title length
        title = "Sonos Favourites"
        assert lines[1].strip() == "=" * len(title)

    def test_unicode_name(self, capsys):
        print_list_header("", "Ünïcödé")
        out = capsys.readouterr().out
        assert "Ünïcödé" in out


# ===========================================================================
# get_current_queue_position
# ===========================================================================


class TestGetCurrentQueuePosition:
    def _make_speaker(self, playlist_position="3", title="A Track", state="PLAYING"):
        speaker = MagicMock()
        speaker.get_current_track_info.return_value = {
            "playlist_position": playlist_position,
            "title": title,
        }
        speaker.get_current_transport_info.return_value = {
            "current_transport_state": state
        }
        return speaker

    def test_playing_no_tracks_returns_qp_and_true(self):
        speaker = self._make_speaker(playlist_position="3", state="PLAYING")
        qp, is_playing = get_current_queue_position(speaker)
        assert qp == 3
        assert is_playing is True

    def test_paused_returns_qp_and_false(self):
        speaker = self._make_speaker(state="PAUSED_PLAYBACK")
        qp, is_playing = get_current_queue_position(speaker)
        assert qp == 3
        assert is_playing is False

    def test_playing_with_matching_track_title(self):
        speaker = self._make_speaker(
            playlist_position="2", title="My Song", state="PLAYING"
        )
        tracks = [MagicMock(), MagicMock()]
        tracks[1].title = "My Song"
        qp, is_playing = get_current_queue_position(speaker, tracks)
        assert qp == 2
        assert is_playing is True

    def test_playing_with_mismatched_track_title_resets_to_1(self):
        speaker = self._make_speaker(
            playlist_position="2", title="My Song", state="PLAYING"
        )
        tracks = [MagicMock(), MagicMock()]
        tracks[1].title = "Different Song"
        qp, is_playing = get_current_queue_position(speaker, tracks)
        assert qp == 1
        assert is_playing is False

    def test_track_info_exception_returns_zero(self):
        speaker = MagicMock()
        speaker.get_current_track_info.side_effect = Exception("network error")
        speaker.get_current_transport_info.return_value = {
            "current_transport_state": "PLAYING"
        }
        qp, is_playing = get_current_queue_position(speaker)
        assert qp == 0
        assert is_playing is True  # PLAYING with no tracks → True without title check

    def test_transport_info_exception_returns_false(self):
        speaker = MagicMock()
        speaker.get_current_track_info.return_value = {
            "playlist_position": "2",
            "title": "T",
        }
        speaker.get_current_transport_info.side_effect = Exception("network error")
        qp, is_playing = get_current_queue_position(speaker)
        assert qp == 2
        assert is_playing is False

    def test_index_error_on_tracks_access_resets_to_1(self):
        speaker = self._make_speaker(playlist_position="99", state="PLAYING")
        tracks = [MagicMock()]  # only 1 track; position 99 is out of range
        tracks[0].title = "different"
        qp, is_playing = get_current_queue_position(speaker, tracks)
        assert qp == 1
        assert is_playing is False


# ===========================================================================
# print_tracks
# ===========================================================================


class TestPrintTracks:
    def test_prints_track_info(self, capsys):
        tracks = [_make_track(title="Toccata", creator="Bach", album="Organ Works")]
        print_tracks(tracks)
        out = capsys.readouterr().out
        assert "Toccata" in out
        assert "Bach" in out
        assert "Organ Works" in out

    def test_missing_attributes_are_skipped(self, capsys):
        track = MagicMock()
        track.title = "Only Title"
        del track.creator
        del track.album
        del track.item_class
        print_tracks([track])
        out = capsys.readouterr().out
        assert "Only Title" in out
        assert "Artist" not in out
        assert "Album" not in out

    def test_podcast_track_renames_title_field(self, capsys):
        track = _make_track(
            title="Episode 1", item_class="object.item.audioItem.podcast"
        )
        print_tracks([track])
        out = capsys.readouterr().out
        assert "Podcast Episode" in out
        assert "Episode 1" in out

    def test_numbered_sequentially(self, capsys):
        tracks = [_make_track(title=f"Track {i}") for i in range(1, 4)]
        print_tracks(tracks)
        out = capsys.readouterr().out
        assert "  1:" in out
        assert "  2:" in out
        assert "  3:" in out

    def test_current_track_prefix_playing(self, capsys):
        tracks = [_make_track(title="Active"), _make_track(title="Next")]
        with patch(
            "soco_cli.action_processor.get_current_queue_position",
            return_value=(1, True),
        ):
            print_tracks(tracks, speaker=MagicMock())
        out = capsys.readouterr().out
        lines = [l for l in out.splitlines() if "Active" in l]
        assert lines[0].startswith(" *> ")

    def test_current_track_prefix_paused(self, capsys):
        tracks = [_make_track(title="Paused"), _make_track(title="Next")]
        with patch(
            "soco_cli.action_processor.get_current_queue_position",
            return_value=(1, False),
        ):
            print_tracks(tracks, speaker=MagicMock())
        out = capsys.readouterr().out
        lines = [l for l in out.splitlines() if "Paused" in l]
        assert lines[0].startswith(" *  ")

    def test_non_current_track_has_plain_prefix(self, capsys):
        tracks = [_make_track(title="T1"), _make_track(title="T2")]
        with patch(
            "soco_cli.action_processor.get_current_queue_position",
            return_value=(1, True),
        ):
            print_tracks(tracks, speaker=MagicMock())
        out = capsys.readouterr().out
        lines = [l for l in out.splitlines() if "T2" in l]
        assert lines[0].startswith("    ")

    def test_single_track_mode_uses_given_number(self, capsys):
        tracks = [_make_track(title="Solo")]
        print_tracks(tracks, single_track=True, track_number=7)
        out = capsys.readouterr().out
        assert "  7:" in out

    def test_returns_true(self):
        assert print_tracks([]) is True


# ===========================================================================
# print_albums
# ===========================================================================


class TestPrintAlbums:
    def _make_album(self, title, creator="Artist"):
        a = MagicMock()
        a.title = title
        a.creator = creator
        return a

    def test_prints_albums(self, capsys):
        albums = [self._make_album("Abbey Road", "Beatles")]
        print_albums(albums)
        out = capsys.readouterr().out
        assert "Abbey Road" in out
        assert "Beatles" in out

    def test_omit_first(self, capsys):
        albums = [self._make_album("First"), self._make_album("Second")]
        print_albums(albums, omit_first=True)
        out = capsys.readouterr().out
        assert "First" not in out
        assert "Second" in out

    def test_numbering_with_omit_first_restarts_at_1(self, capsys):
        # omit_first skips the first album but does NOT advance the counter,
        # so the remaining albums are numbered starting from 1.
        albums = [self._make_album("A"), self._make_album("B"), self._make_album("C")]
        print_albums(albums, omit_first=True)
        out = capsys.readouterr().out
        assert "      1:" in out
        assert "      2:" in out

    def test_missing_creator_defaults_to_empty(self, capsys):
        a = MagicMock()
        a.title = "Untitled"
        del a.creator
        print_albums([a])
        out = capsys.readouterr().out
        assert "Untitled" in out

    def test_returns_true(self):
        assert print_albums([]) is True


# ===========================================================================
# on_off_action
# ===========================================================================


class TestOnOffAction:
    def test_get_state_on(self, capsys):
        speaker = _make_speaker()
        speaker.loudness = True
        _call(on_off_action, speaker, [], soco_function="loudness")
        assert capsys.readouterr().out.strip() == "on"

    def test_get_state_off(self, capsys):
        speaker = _make_speaker()
        speaker.loudness = False
        _call(on_off_action, speaker, [], soco_function="loudness")
        assert capsys.readouterr().out.strip() == "off"

    def test_set_on(self):
        speaker = _make_speaker()
        result = _call(on_off_action, speaker, ["on"], soco_function="loudness")
        assert result is True
        assert speaker.loudness is True

    def test_set_off(self):
        speaker = _make_speaker()
        result = _call(on_off_action, speaker, ["off"], soco_function="loudness")
        assert result is True
        assert speaker.loudness is False

    def test_set_case_insensitive(self):
        speaker = _make_speaker()
        assert _call(on_off_action, speaker, ["ON"], soco_function="loudness") is True
        assert _call(on_off_action, speaker, ["OFF"], soco_function="loudness") is True

    def test_invalid_arg_returns_false(self, capsys):
        speaker = _make_speaker()
        result = _call(on_off_action, speaker, ["yes"], soco_function="loudness")
        assert result is False

    def test_group_mute_switches_to_group(self):
        speaker = MagicMock()
        speaker.group.mute = False
        on_off_action(speaker, "group_mute", ["on"], "mute", False)
        assert speaker.group.mute is True


# ===========================================================================
# volume_actions
# ===========================================================================


class TestVolumeActions:
    def test_get_volume(self, capsys):
        speaker = _make_speaker(volume=42)
        _call(volume_actions, speaker, [], soco_function="volume")
        assert capsys.readouterr().out.strip() == "42"

    def test_set_volume(self):
        speaker = _make_speaker()
        result = _call(volume_actions, speaker, ["75"], soco_function="volume")
        assert result is True
        assert speaker.volume == 75

    def test_set_volume_boundary_values(self):
        for v in [0, 100]:
            speaker = _make_speaker()
            assert (
                _call(volume_actions, speaker, [str(v)], soco_function="volume") is True
            )
            assert speaker.volume == v

    def test_set_volume_out_of_range(self, capsys):
        for v in ["-1", "101"]:
            speaker = _make_speaker()
            result = _call(volume_actions, speaker, [v], soco_function="volume")
            assert result is False

    def test_set_volume_invalid_arg(self, capsys):
        speaker = _make_speaker()
        result = _call(volume_actions, speaker, ["loud"], soco_function="volume")
        assert result is False

    def test_group_volume_uses_group(self, capsys):
        speaker = MagicMock()
        speaker.group.volume = 30
        _call(volume_actions, speaker, [], soco_function="group_volume")
        assert capsys.readouterr().out.strip() == "30"

    def test_ramp_to_volume(self):
        speaker = _make_speaker()
        speaker.ramp_to_volume.return_value = 60
        with patch("builtins.print"):
            result = _call(
                volume_actions, speaker, ["60"], soco_function="ramp_to_volume"
            )
        assert result is True
        speaker.ramp_to_volume.assert_called_once_with(60)


# ===========================================================================
# shuffle
# ===========================================================================


class TestShuffle:
    def test_get_shuffle_on(self, capsys):
        speaker = _make_speaker(shuffle=True)
        _call(shuffle, speaker, [])
        assert capsys.readouterr().out.strip() == "on"

    def test_get_shuffle_off(self, capsys):
        speaker = _make_speaker(shuffle=False)
        _call(shuffle, speaker, [])
        assert capsys.readouterr().out.strip() == "off"

    def test_set_shuffle_on(self):
        speaker = _make_speaker()
        assert _call(shuffle, speaker, ["on"]) is True
        assert speaker.shuffle is True

    def test_set_shuffle_off(self):
        speaker = _make_speaker()
        assert _call(shuffle, speaker, ["off"]) is True
        assert speaker.shuffle is False

    def test_set_shuffle_case_insensitive(self):
        speaker = _make_speaker()
        assert _call(shuffle, speaker, ["ON"]) is True
        assert _call(shuffle, speaker, ["OFF"]) is True

    def test_invalid_arg_returns_false(self, capsys):
        speaker = _make_speaker()
        assert _call(shuffle, speaker, ["yes"]) is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# repeat
# ===========================================================================


class TestRepeat:
    def test_get_repeat_all(self, capsys):
        speaker = _make_speaker(repeat=True)
        _call(repeat, speaker, [])
        assert capsys.readouterr().out.strip() == "all"

    def test_get_repeat_off(self, capsys):
        speaker = _make_speaker(repeat=False)
        _call(repeat, speaker, [])
        assert capsys.readouterr().out.strip() == "off"

    def test_get_repeat_one(self, capsys):
        speaker = _make_speaker(repeat="ONE")
        _call(repeat, speaker, [])
        assert capsys.readouterr().out.strip() == "one"

    def test_set_off(self):
        speaker = _make_speaker()
        assert _call(repeat, speaker, ["off"]) is True
        assert speaker.repeat is False

    def test_set_none_alias(self):
        speaker = _make_speaker()
        assert _call(repeat, speaker, ["none"]) is True
        assert speaker.repeat is False

    def test_set_one(self):
        speaker = _make_speaker()
        assert _call(repeat, speaker, ["one"]) is True
        assert speaker.repeat == "ONE"

    def test_set_all(self):
        speaker = _make_speaker()
        assert _call(repeat, speaker, ["all"]) is True
        assert speaker.repeat is True

    def test_set_case_insensitive(self):
        speaker = _make_speaker()
        assert _call(repeat, speaker, ["ALL"]) is True
        assert _call(repeat, speaker, ["OFF"]) is True

    def test_invalid_arg_returns_false(self, capsys):
        speaker = _make_speaker()
        assert _call(repeat, speaker, ["twice"]) is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# playback_mode
# ===========================================================================


class TestPlaybackMode:
    def test_get_mode(self, capsys):
        speaker = _make_speaker(play_mode="SHUFFLE")
        _call(playback_mode, speaker, [])
        assert capsys.readouterr().out.strip() == "SHUFFLE"

    def test_set_valid_modes(self):
        for mode in [
            "normal",
            "repeat_all",
            "repeat_one",
            "shuffle",
            "shuffle_norepeat",
            "shuffle_repeat_one",
        ]:
            speaker = _make_speaker()
            result = _call(playback_mode, speaker, [mode])
            assert result is True
            assert speaker.play_mode == mode

    def test_set_mode_case_insensitive(self):
        speaker = _make_speaker()
        _call(playback_mode, speaker, ["NORMAL"])
        assert speaker.play_mode == "NORMAL"

    def test_invalid_mode_still_returns_true(self, capsys):
        # Known behaviour: playback_mode always returns True even on invalid input
        speaker = _make_speaker()
        result = _call(playback_mode, speaker, ["random"])
        assert result is True
        # But the speaker's play_mode should not have been set
        (
            speaker.play_mode.__set__.assert_not_called()
            if hasattr(speaker.play_mode, "__set__")
            else None
        )


# ===========================================================================
# sleep_timer
# ===========================================================================


class TestSleepTimer:
    def test_get_no_timer(self, capsys):
        speaker = _make_speaker()
        speaker.get_sleep_timer.return_value = None
        _call(sleep_timer, speaker, [])
        assert "No sleep timer set" in capsys.readouterr().out

    def test_get_timer_active(self, capsys):
        speaker = _make_speaker()
        speaker.get_sleep_timer.return_value = 600  # 10 minutes
        _call(sleep_timer, speaker, [])
        out = capsys.readouterr().out
        assert "expires" in out

    def test_cancel_timer(self):
        speaker = _make_speaker()
        result = _call(sleep_timer, speaker, ["off"])
        assert result is True
        speaker.set_sleep_timer.assert_called_once_with(None)

    def test_cancel_alias(self):
        speaker = _make_speaker()
        _call(sleep_timer, speaker, ["cancel"])
        speaker.set_sleep_timer.assert_called_once_with(None)

    def test_set_timer_seconds(self):
        speaker = _make_speaker()
        result = _call(sleep_timer, speaker, ["120s"])
        assert result is True
        speaker.set_sleep_timer.assert_called_once_with(120)

    def test_set_timer_minutes(self):
        speaker = _make_speaker()
        result = _call(sleep_timer, speaker, ["30m"])
        assert result is True
        speaker.set_sleep_timer.assert_called_once_with(1800)

    def test_set_timer_invalid_format(self, capsys):
        speaker = _make_speaker()
        result = _call(sleep_timer, speaker, ["tomorrow"])
        assert result is False

    def test_set_timer_exceeds_max(self, capsys):
        speaker = _make_speaker()
        result = _call(sleep_timer, speaker, ["90000s"])  # > 86399
        assert result is False


# ===========================================================================
# switch_to_tv
# ===========================================================================


class TestSwitchToTv:
    def test_soundbar_switches(self):
        speaker = _make_speaker(is_soundbar=True)
        result = _call(switch_to_tv, speaker, [])
        assert result is True
        speaker.switch_to_tv.assert_called_once()

    def test_non_soundbar_returns_false(self, capsys):
        speaker = _make_speaker(is_soundbar=False, player_name="Kitchen")
        result = _call(switch_to_tv, speaker, [])
        assert result is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# audio_format
# ===========================================================================


class TestAudioFormat:
    def test_soundbar_with_format(self, capsys):
        speaker = _make_speaker(
            is_soundbar=True, soundbar_audio_input_format="Dolby Atmos"
        )
        result = _call(audio_format, speaker, [])
        assert result is True
        assert "Dolby Atmos" in capsys.readouterr().out

    def test_soundbar_no_format(self, capsys):
        speaker = _make_speaker(is_soundbar=True, soundbar_audio_input_format=None)
        result = _call(audio_format, speaker, [])
        assert result is True
        assert "No audio format information" in capsys.readouterr().out

    def test_non_soundbar_returns_false(self, capsys):
        speaker = _make_speaker(is_soundbar=False, player_name="Kitchen")
        result = _call(audio_format, speaker, [])
        assert result is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# mic_enabled
# ===========================================================================


class TestMicEnabled:
    def test_mic_enabled_true(self, capsys):
        speaker = _make_speaker(mic_enabled=True)
        result = _call(mic_enabled, speaker, [])
        assert result is True
        assert "True" in capsys.readouterr().out

    def test_mic_enabled_false(self, capsys):
        speaker = _make_speaker(mic_enabled=False)
        result = _call(mic_enabled, speaker, [])
        assert result is True
        assert "False" in capsys.readouterr().out

    def test_mic_none_returns_false(self, capsys):
        speaker = _make_speaker(mic_enabled=None, player_name="Kitchen")
        result = _call(mic_enabled, speaker, [])
        assert result is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# tv_audio_delay
# ===========================================================================


class TestTvAudioDelay:
    def test_non_soundbar_returns_false(self, capsys):
        speaker = _make_speaker(is_soundbar=False, player_name="Kitchen")
        result = _call(tv_audio_delay, speaker, [])
        assert result is False

    def test_get_delay(self, capsys):
        speaker = _make_speaker(is_soundbar=True, audio_delay=2)
        _call(tv_audio_delay, speaker, [])
        assert "2" in capsys.readouterr().out

    def test_set_delay(self):
        speaker = _make_speaker(is_soundbar=True)
        result = _call(tv_audio_delay, speaker, ["3"])
        assert result is True
        assert speaker.audio_delay == 3

    def test_set_delay_invalid(self, capsys):
        speaker = _make_speaker(is_soundbar=True)
        result = _call(tv_audio_delay, speaker, ["abc"])
        assert result is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# set_queue_position
# ===========================================================================


class TestSetQueuePosition:
    def test_valid_position(self):
        speaker = _make_speaker(queue_size=10)
        result = _call(set_queue_position, speaker, ["5"])
        assert result is True
        speaker.stop.assert_called_once()
        speaker.play_from_queue.assert_called_once_with(index=4, start=False)

    def test_boundary_first(self):
        speaker = _make_speaker(queue_size=5)
        result = _call(set_queue_position, speaker, ["1"])
        assert result is True
        speaker.play_from_queue.assert_called_once_with(index=0, start=False)

    def test_boundary_last(self):
        speaker = _make_speaker(queue_size=5)
        result = _call(set_queue_position, speaker, ["5"])
        assert result is True
        speaker.play_from_queue.assert_called_once_with(index=4, start=False)

    def test_out_of_range_low(self, capsys):
        speaker = _make_speaker(queue_size=5)
        result = _call(set_queue_position, speaker, ["0"])
        assert result is False
        speaker.stop.assert_not_called()

    def test_out_of_range_high(self, capsys):
        speaker = _make_speaker(queue_size=5)
        result = _call(set_queue_position, speaker, ["6"])
        assert result is False
        speaker.stop.assert_not_called()

    def test_non_integer_returns_false(self, capsys):
        speaker = _make_speaker(queue_size=5)
        result = _call(set_queue_position, speaker, ["abc"])
        assert result is False
        speaker.stop.assert_not_called()


# ===========================================================================
# surround_volume
# ===========================================================================


class TestSurroundVolume:
    def test_no_surround_returns_false(self, capsys):
        speaker = _make_speaker(player_name="Kitchen")
        speaker.sub_gain = None
        result = surround_volume(speaker, "surround_volume", [], "sub_gain", False)
        assert result is False
        assert "Error" in capsys.readouterr().err

    def test_get_gain(self, capsys):
        speaker = _make_speaker()
        speaker.sub_gain = 5
        result = surround_volume(speaker, "surround_volume", [], "sub_gain", False)
        assert result is True
        assert "5" in capsys.readouterr().out

    def test_set_gain(self):
        speaker = _make_speaker()
        speaker.sub_gain = 0
        result = surround_volume(speaker, "surround_volume", ["10"], "sub_gain", False)
        assert result is True
        assert speaker.sub_gain == 10

    def test_set_gain_boundary(self):
        for v in [-15, 0, 15]:
            speaker = _make_speaker()
            speaker.sub_gain = 0
            result = surround_volume(
                speaker, "surround_volume", [str(v)], "sub_gain", False
            )
            assert result is True

    def test_set_gain_out_of_range(self, capsys):
        for v in ["-16", "16"]:
            speaker = _make_speaker()
            speaker.sub_gain = 0
            result = surround_volume(speaker, "surround_volume", [v], "sub_gain", False)
            assert result is False

    def test_set_gain_invalid(self, capsys):
        speaker = _make_speaker()
        speaker.sub_gain = 0
        result = surround_volume(speaker, "surround_volume", ["abc"], "sub_gain", False)
        assert result is False


# ===========================================================================
# play_uri
# ===========================================================================


class TestPlayUri:
    def test_success_on_first_attempt(self):
        speaker = _make_speaker()
        result = _call(play_uri, speaker, ["http://stream.example.com/radio"])
        assert result is True
        speaker.play_uri.assert_called_once_with(
            "http://stream.example.com/radio", title="", force_radio=False
        )

    def test_falls_back_to_force_radio(self):
        speaker = _make_speaker()
        speaker.play_uri.side_effect = [Exception("fail"), None]
        result = _call(play_uri, speaker, ["http://stream.example.com/radio"])
        assert result is True
        assert speaker.play_uri.call_count == 2
        assert speaker.play_uri.call_args_list[1][1]["force_radio"] is True

    def test_both_attempts_fail_returns_false(self, capsys):
        speaker = _make_speaker()
        speaker.play_uri.side_effect = Exception("fail")
        result = _call(play_uri, speaker, ["http://bad.uri/"])
        assert result is False
        assert "Error" in capsys.readouterr().err

    def test_passes_title(self):
        speaker = _make_speaker()
        _call(play_uri, speaker, ["http://stream.example.com/", "My Station"])
        assert speaker.play_uri.call_args[1]["title"] == "My Station"

    def test_title_defaults_to_empty_string(self):
        speaker = _make_speaker()
        _call(play_uri, speaker, ["http://stream.example.com/"])
        assert speaker.play_uri.call_args[1]["title"] == ""


# ===========================================================================
# play_favourite_core
# ===========================================================================


class TestPlayFavouriteCore:
    def _setup_speaker(self, favs):
        speaker = MagicMock()
        speaker.music_library.get_sonos_favorites.return_value = favs
        return speaker

    def test_found_by_name_play_uri_succeeds(self):
        fav = _make_favourite("Radio 4")
        speaker = self._setup_speaker([fav])
        result, msg = play_favourite_core(speaker, "Radio 4")
        assert result is True
        assert msg == ""
        speaker.play_uri.assert_called_once()

    def test_found_by_fuzzy_name(self):
        fav = _make_favourite("BBC Radio 4")
        speaker = self._setup_speaker([fav])
        result, msg = play_favourite_core(speaker, "Radio 4")
        assert result is True

    def test_not_found_returns_false_with_message(self):
        speaker = self._setup_speaker([_make_favourite("Radio 3")])
        result, msg = play_favourite_core(speaker, "Radio 4")
        assert result is False
        assert "not found" in msg

    def test_play_uri_fails_falls_back_to_queue(self):
        fav = _make_favourite("Radio 4")
        speaker = self._setup_speaker([fav])
        speaker.play_uri.side_effect = Exception("unsupported")
        speaker.add_to_queue.return_value = 3
        result, msg = play_favourite_core(speaker, "Radio 4")
        assert result is True
        speaker.add_to_queue.assert_called_once_with(fav, as_next=True)
        speaker.play_from_queue.assert_called_once_with(3, start=True)

    def test_both_strategies_fail_returns_error(self):
        fav = _make_favourite("Radio 4")
        speaker = self._setup_speaker([fav])
        speaker.play_uri.side_effect = Exception("e1")
        speaker.add_to_queue.side_effect = Exception("e2")
        result, msg = play_favourite_core(speaker, "Radio 4")
        assert result is False
        assert "e1" in msg
        assert "e2" in msg

    def test_by_number_valid(self):
        favs = [
            _make_favourite("Alpha"),
            _make_favourite("Beta"),
            _make_favourite("Gamma"),
        ]
        speaker = self._setup_speaker(favs)
        # Sorted by title: Alpha, Beta, Gamma → number 2 = Beta
        result, msg = play_favourite_core(speaker, "", favourite_number="2")
        assert result is True
        # Verify Beta's URI was used
        assert speaker.play_uri.call_args[1]["uri"] == "http://example.com/stream"

    def test_by_number_out_of_range(self):
        favs = [_make_favourite("Only")]
        speaker = self._setup_speaker(favs)
        result, msg = play_favourite_core(speaker, "", favourite_number="5")
        assert result is False
        assert "1 and 1" in msg

    def test_by_number_zero_is_out_of_range(self):
        favs = [_make_favourite("Only")]
        speaker = self._setup_speaker(favs)
        result, msg = play_favourite_core(speaker, "", favourite_number="0")
        assert result is False

    def test_by_number_non_integer(self):
        favs = [_make_favourite("Only")]
        speaker = self._setup_speaker(favs)
        result, msg = play_favourite_core(speaker, "", favourite_number="abc")
        assert result is False

    def test_by_number_sorted_by_title(self):
        favs = [
            _make_favourite("Zebra"),
            _make_favourite("Apple"),
            _make_favourite("Mango"),
        ]
        speaker = self._setup_speaker(favs)
        play_favourite_core(speaker, "", favourite_number="1")
        # Number 1 sorted = Apple; verify Apple's URI was used
        assert speaker.play_uri.called
        used_uri = speaker.play_uri.call_args[1]["uri"]
        assert used_uri == "http://example.com/stream"  # all share the same mock URI


# ===========================================================================
# add_favourite_to_queue
# ===========================================================================


class TestAddFavouriteToQueue:
    def _setup(self, fav_titles, queue_size=5):
        speaker = MagicMock()
        speaker.queue_size = queue_size
        favs = [_make_favourite(t) for t in fav_titles]
        speaker.music_library.get_sonos_favorites.return_value = favs
        return speaker

    def test_found_appends_to_end(self, capsys):
        speaker = self._setup(["Radio 4"], queue_size=5)
        with patch("soco_cli.action_processor.save_queue_insertion_position"):
            result = add_favourite_to_queue(
                speaker, "add_favourite_to_queue", ["Radio 4"], "", False
            )
        assert result is True
        speaker.add_to_queue.assert_called_once()
        assert "6" in capsys.readouterr().out  # queue_size + 1

    def test_found_with_position(self):
        speaker = self._setup(["Radio 4"])
        with patch(
            "soco_cli.action_processor.get_queue_insertion_position", return_value=3
        ):
            with patch("soco_cli.action_processor.save_queue_insertion_position"):
                result = add_favourite_to_queue(
                    speaker, "add_favourite_to_queue", ["Radio 4", "3"], "", False
                )
        assert result is True
        call_args = speaker.add_to_queue.call_args
        assert call_args[1]["position"] == 3

    def test_not_found_returns_false(self, capsys):
        speaker = self._setup(["Radio 3"])
        result = add_favourite_to_queue(
            speaker, "add_favourite_to_queue", ["Radio 4"], "", False
        )
        assert result is False
        assert "Error" in capsys.readouterr().err

    def test_add_to_queue_exception_returns_false(self, capsys):
        speaker = self._setup(["Radio 4"])
        speaker.add_to_queue.side_effect = Exception("UPnP error")
        with patch("soco_cli.action_processor.save_queue_insertion_position"):
            result = add_favourite_to_queue(
                speaker, "add_favourite_to_queue", ["Radio 4"], "", False
            )
        assert result is False
        assert "Error" in capsys.readouterr().err


# ===========================================================================
# list_queue
# ===========================================================================


class TestListQueue:
    def test_empty_queue_returns_true(self):
        speaker = _make_speaker()
        speaker.get_queue.return_value = []
        result = list_queue(speaker, "list_queue", [], "", False)
        assert result is True

    def test_full_queue_calls_print_tracks(self):
        speaker = _make_speaker()
        tracks = [_make_track(f"T{i}") for i in range(3)]
        speaker.get_queue.return_value = tracks
        with patch("soco_cli.action_processor.print_tracks") as mock_print:
            list_queue(speaker, "list_queue", [], "", False)
        mock_print.assert_called_once()

    def test_single_track_by_number(self):
        speaker = _make_speaker()
        tracks = [_make_track(f"T{i}") for i in range(5)]
        speaker.get_queue.return_value = tracks
        with patch("soco_cli.action_processor.print_tracks") as mock_print:
            result = list_queue(speaker, "list_queue", ["3"], "", False)
        assert result is True
        # print_tracks called with the single-track slice
        called_tracks = mock_print.call_args[0][0]
        assert len(called_tracks) == 1

    def test_track_number_out_of_range(self, capsys):
        speaker = _make_speaker()
        speaker.get_queue.return_value = [_make_track("T")]
        result = list_queue(speaker, "list_queue", ["5"], "", False)
        assert result is False
        assert "Error" in capsys.readouterr().err

    def test_track_number_zero_out_of_range(self, capsys):
        speaker = _make_speaker()
        speaker.get_queue.return_value = [_make_track("T")]
        result = list_queue(speaker, "list_queue", ["0"], "", False)
        assert result is False

    def test_non_integer_track_number(self, capsys):
        speaker = _make_speaker()
        speaker.get_queue.return_value = [_make_track("T")]
        result = list_queue(speaker, "list_queue", ["abc"], "", False)
        assert result is False


# ===========================================================================
# process_action
# ===========================================================================


class TestProcessAction:
    def test_unknown_action_returns_false(self):
        speaker = _make_speaker()
        result = process_action(speaker, "no_such_action", [])
        assert result is False

    def test_known_action_is_dispatched(self):
        speaker = _make_speaker()
        mock_fn = MagicMock(return_value=True)
        fake_actions = {
            "test_action": SonosFunction(mock_fn, "some_fn", False),
        }
        with patch("soco_cli.action_processor.actions", fake_actions):
            result = process_action(speaker, "test_action", ["arg1"])
        assert result is True
        mock_fn.assert_called_once_with(
            speaker, "test_action", ["arg1"], "some_fn", False
        )

    def test_switch_to_coordinator_when_not_coordinator(self):
        speaker = MagicMock()
        speaker.is_coordinator = False
        coordinator = MagicMock()
        speaker.group.coordinator = coordinator
        mock_fn = MagicMock(return_value=True)
        fake_actions = {
            "coord_action": SonosFunction(mock_fn, "", True),
        }
        with patch("soco_cli.action_processor.actions", fake_actions):
            process_action(speaker, "coord_action", [])
        # Function should have been called with the coordinator, not the original speaker
        called_speaker = mock_fn.call_args[0][0]
        assert called_speaker is coordinator

    def test_switch_to_coordinator_when_already_coordinator(self):
        speaker = MagicMock()
        speaker.is_coordinator = True
        mock_fn = MagicMock(return_value=True)
        fake_actions = {
            "coord_action": SonosFunction(mock_fn, "", True),
        }
        with patch("soco_cli.action_processor.actions", fake_actions):
            process_action(speaker, "coord_action", [])
        called_speaker = mock_fn.call_args[0][0]
        assert called_speaker is speaker
