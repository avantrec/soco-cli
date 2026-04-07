"""Tests for speakers.py — Speakers class."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from soco_cli.speakers import SonosDevice, Speakers


def _make_device(name, ip="192.168.1.1", visible=True, household="HH1"):
    return SonosDevice(
        household_id=household,
        ip_address=ip,
        speaker_name=name,
        is_visible=visible,
        model_name="Sonos One",
        display_version="15.0",
    )


# ---------------------------------------------------------------------------
# is_ipv4_address
# ---------------------------------------------------------------------------


class TestIsIpv4Address:
    def test_valid_ip(self):
        assert Speakers.is_ipv4_address("192.168.1.1") is True

    def test_valid_ip_class_a(self):
        assert Speakers.is_ipv4_address("10.0.0.1") is True

    def test_valid_loopback(self):
        assert Speakers.is_ipv4_address("127.0.0.1") is True

    def test_cidr_notation(self):
        # IPv4Network also accepts CIDR notation
        assert Speakers.is_ipv4_address("192.168.1.0/24") is True

    def test_hostname_returns_false(self):
        assert Speakers.is_ipv4_address("sonos-kitchen") is False

    def test_ipv6_returns_false(self):
        assert Speakers.is_ipv4_address("::1") is False

    def test_empty_string_returns_false(self):
        assert Speakers.is_ipv4_address("") is False

    def test_out_of_range_octet_returns_false(self):
        assert Speakers.is_ipv4_address("999.0.0.1") is False

    def test_partial_ip_returns_false(self):
        assert Speakers.is_ipv4_address("192.168.1") is False


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_save_returns_false_when_no_speakers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            assert s.save() is False

    def test_save_and_load_round_trip(self):
        device = _make_device("Kitchen", "192.168.1.10")
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            s._speakers = [device]
            assert s.save() is True

            s2 = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            assert s2.load() is True
            assert len(s2.speakers) == 1
            assert s2.speakers[0].speaker_name == "Kitchen"

    def test_load_returns_false_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="missing.pickle")
            assert s.load() is False

    def test_speaker_cache_file_exists_property(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            assert s.speaker_cache_file_exists is False
            s._speakers = [_make_device("Kitchen")]
            s.save()
            assert s.speaker_cache_file_exists is True

    def test_speaker_cache_loaded_property(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            assert s.speaker_cache_loaded is False
            s._speakers = [_make_device("Kitchen")]
            assert s.speaker_cache_loaded is True


# ---------------------------------------------------------------------------
# clear / remove_save_file
# ---------------------------------------------------------------------------


class TestClearAndRemove:
    def test_clear_empties_speakers_list(self):
        s = Speakers()
        s._speakers = [_make_device("Kitchen")]
        s.clear()
        assert s.speakers == []

    def test_remove_save_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            s._speakers = [_make_device("Kitchen")]
            s.save()
            assert os.path.exists(s.save_pathname)
            s.remove_save_file()
            assert not os.path.exists(s.save_pathname)


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------


class TestRename:
    def test_rename_existing_speaker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            s._speakers = [_make_device("Kitchen")]
            result = s.rename("Kitchen", "Dining Room")
            assert result is True
            names = [sp.speaker_name for sp in s.speakers]
            assert "Dining Room" in names
            assert "Kitchen" not in names

    def test_rename_nonexistent_returns_false(self):
        s = Speakers()
        s._speakers = [_make_device("Kitchen")]
        result = s.rename("Bedroom", "Office")
        assert result is False

    def test_rename_with_apostrophe_normalisation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Speakers(save_directory=tmpdir + "/", save_file="test.pickle")
            # Stored name uses curly apostrophe
            s._speakers = [_make_device("Bob\u2019s Room")]
            # Look up with straight apostrophe
            result = s.rename("Bob's Room", "Guest Room")
            assert result is True


# ---------------------------------------------------------------------------
# subnets setter
# ---------------------------------------------------------------------------


class TestSubnetsSetter:
    def test_none_subnets_sets_none(self):
        s = Speakers(subnets=None)
        assert s.subnets is None

    def test_valid_subnets_kept(self):
        s = Speakers(subnets=["192.168.1.0/24", "10.0.0.0/8"])
        assert "192.168.1.0/24" in s.subnets
        assert "10.0.0.0/8" in s.subnets

    def test_invalid_subnets_removed(self):
        s = Speakers(subnets=["192.168.1.0/24", "not_a_network"])
        assert "192.168.1.0/24" in s.subnets
        assert "not_a_network" not in s.subnets

    def test_all_invalid_subnets_leaves_empty_list(self):
        s = Speakers(subnets=["bad1", "bad2"])
        assert s.subnets == []


# ---------------------------------------------------------------------------
# get_all_speaker_names
# ---------------------------------------------------------------------------


class TestGetAllSpeakerNames:
    def test_returns_sorted_visible_names(self):
        s = Speakers()
        s._speakers = [
            _make_device("Zebra", visible=True),
            _make_device("Apple", visible=True),
            _make_device("Mango", visible=True),
        ]
        names = s.get_all_speaker_names()
        assert names == ["Apple", "Mango", "Zebra"]

    def test_invisible_speakers_excluded(self):
        s = Speakers()
        s._speakers = [
            _make_device("Visible", visible=True),
            _make_device("Hidden", visible=False),
        ]
        names = s.get_all_speaker_names()
        assert "Visible" in names
        assert "Hidden" not in names

    def test_empty_list_returns_empty(self):
        s = Speakers()
        assert s.get_all_speaker_names() == []


# ---------------------------------------------------------------------------
# find (uses soco.SoCo — patched)
# ---------------------------------------------------------------------------


class TestFind:
    def test_exact_match_returns_soco_object(self):
        s = Speakers()
        s._speakers = [_make_device("Kitchen", ip="192.168.1.10")]
        mock_soco = MagicMock()
        with patch("soco_cli.speakers.soco.SoCo", return_value=mock_soco):
            result = s.find("Kitchen")
        assert result is mock_soco

    def test_partial_match_returns_soco_object(self):
        s = Speakers()
        s._speakers = [_make_device("Kitchen", ip="192.168.1.10")]
        mock_soco = MagicMock()
        with patch("soco_cli.speakers.soco.SoCo", return_value=mock_soco):
            result = s.find("Kit")
        assert result is mock_soco

    def test_no_match_returns_none(self):
        s = Speakers()
        s._speakers = [_make_device("Kitchen")]
        result = s.find("Bedroom")
        assert result is None

    def test_invisible_speaker_excluded_by_default(self):
        s = Speakers()
        s._speakers = [_make_device("Hidden", visible=False)]
        result = s.find("Hidden")
        assert result is None

    def test_invisible_speaker_found_when_not_requiring_visible(self):
        s = Speakers()
        s._speakers = [_make_device("Hidden", ip="192.168.1.20", visible=False)]
        mock_soco = MagicMock()
        with patch("soco_cli.speakers.soco.SoCo", return_value=mock_soco):
            result = s.find("Hidden", require_visible=False)
        assert result is mock_soco

    def test_ambiguous_partial_match_returns_none(self, capsys):
        s = Speakers()
        s._speakers = [
            _make_device("Kitchen Front", ip="192.168.1.10"),
            _make_device("Kitchen Back", ip="192.168.1.11"),
        ]
        with patch("soco_cli.speakers.soco.SoCo", return_value=MagicMock()):
            result = s.find("Kitchen")
        assert result is None
        assert "ambiguous" in capsys.readouterr().out
