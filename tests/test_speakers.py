"""Tests for speakers.py — Speakers class."""

import os
import pickle
import tempfile
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from soco_cli.speakers import (
    SonosDevice,
    Speakers,
    create_soco,
    parse_speaker_address,
    speaker_address,
)


def _make_device(name, ip="192.168.1.1", visible=True, household="HH1", port=1400):
    return SonosDevice(
        household_id=household,
        ip_address=ip,
        speaker_name=name,
        is_visible=visible,
        model_name="Sonos One",
        display_version="15.0",
        port=port,
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


# ---------------------------------------------------------------------------
# Multi-port players (e.g., Sonos Amp Multi)
# ---------------------------------------------------------------------------


class TestSpeakerAddress:
    def test_default_port_is_plain_ip(self):
        assert speaker_address(_make_device("A", ip="10.0.0.5")) == "10.0.0.5"

    def test_other_port_is_included(self):
        device = _make_device("A", ip="10.0.0.5", port=1500)
        assert speaker_address(device) == "10.0.0.5:1500"

    def test_object_without_port_attribute(self):
        speaker = MagicMock(spec=["ip_address"])
        speaker.ip_address = "10.0.0.5"
        assert speaker_address(speaker) == "10.0.0.5"


class TestParseSpeakerAddress:
    @pytest.mark.parametrize(
        "address, expected",
        [
            ("10.0.0.5", ("10.0.0.5", 1400)),
            ("10.0.0.5:1500", ("10.0.0.5", 1500)),
            ("10.0.0.5:1400", ("10.0.0.5", 1400)),
        ],
    )
    def test_valid(self, address, expected):
        assert parse_speaker_address(address) == expected

    @pytest.mark.parametrize(
        "address",
        [
            "Kitchen",
            "10.0.0.5:",
            "10.0.0.5:abc",
            "10.0.0.5:0",
            "10.0.0.5:70000",
            "Kitchen:1500",
            "",
        ],
    )
    def test_invalid(self, address):
        assert parse_speaker_address(address) is None


class TestCreateSoco:
    def test_default_port_omitted(self):
        with patch("soco_cli.speakers.soco.SoCo") as mock_soco:
            create_soco("10.0.0.5")
        mock_soco.assert_called_once_with("10.0.0.5")

    def test_other_port_passed(self):
        with patch("soco_cli.speakers.soco.SoCo") as mock_soco:
            create_soco("10.0.0.5", 1500)
        mock_soco.assert_called_once_with("10.0.0.5", 1500)


class TestMultiPortCache:
    def test_old_cache_records_load_with_default_port(self):
        # Simulate a cache saved by a version without the 'port' field
        old_sonos_device = namedtuple("SonosDevice", SonosDevice._fields[:-1])
        old_sonos_device.__module__ = SonosDevice.__module__
        old_record = old_sonos_device(
            "HH1", "10.0.0.5", "Kitchen", True, "Sonos One", "15.0"
        )
        with patch("soco_cli.speakers.SonosDevice", old_sonos_device):
            data = pickle.dumps([old_record])
        device = pickle.loads(data)[0]
        assert isinstance(device, SonosDevice)
        assert device.port == 1400
        assert device.speaker_name == "Kitchen"

    def test_save_and_load_preserves_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            spkrs = Speakers(save_directory=tmp + "/", save_file="test.pickle")
            spkrs._speakers = [_make_device("Zone 2", ip="10.0.0.5", port=1500)]
            spkrs.save()
            loaded = Speakers(save_directory=tmp + "/", save_file="test.pickle")
            loaded.load()
            assert loaded.speakers[0].port == 1500

    def test_find_uses_port(self):
        spkrs = Speakers()
        spkrs._speakers = [
            _make_device("Zone 1", ip="10.0.0.5"),
            _make_device("Zone 2", ip="10.0.0.5", port=1500),
        ]
        with patch("soco_cli.speakers.soco.SoCo") as mock_soco:
            spkrs.find("Zone 2")
        mock_soco.assert_called_once_with("10.0.0.5", 1500)

    def test_get_all_speakers_uses_ports(self):
        spkrs = Speakers()
        spkrs._speakers = [
            _make_device("Zone 1", ip="10.0.0.5"),
            _make_device("Zone 2", ip="10.0.0.5", port=1500),
        ]
        with patch("soco_cli.speakers.soco.SoCo") as mock_soco:
            spkrs.get_all_speakers()
        assert mock_soco.call_args_list == [
            (("10.0.0.5",),),
            (("10.0.0.5", 1500),),
        ]

    def test_discover_keeps_players_sharing_an_ip(self):
        zones = []
        for port in (1400, 1500):
            zone = MagicMock()
            zone.ip_address = "10.0.0.5"
            zone.port = port
            zones.append(zone)
        spkrs = Speakers()
        with patch("soco_cli.speakers.soco.discovery.scan_network", return_value=zones):
            with patch.object(
                Speakers,
                "get_sonos_device_data",
                side_effect=lambda ip, port: _make_device(str(port), ip=ip, port=port),
            ) as mock_get:
                spkrs.discover()
        assert mock_get.call_args_list == [
            (("10.0.0.5", 1400),),
            (("10.0.0.5", 1500),),
        ]
        assert [d.port for d in spkrs.speakers] == [1400, 1500]

    def test_get_sonos_device_data_records_port(self):
        mock_soco = MagicMock()
        mock_soco.get_speaker_info.return_value = {
            "zone_name": "Zone 2",
            "model_name": "Sonos Amp Multi",
            "display_version": "17.0",
        }
        with patch("soco_cli.speakers.soco.SoCo", return_value=mock_soco) as soco_cls:
            device = Speakers.get_sonos_device_data("10.0.0.5", 1500)
        soco_cls.assert_called_once_with("10.0.0.5", 1500)
        assert device.port == 1500
        assert device.speaker_name == "Zone 2"

    def test_print_shows_port(self, capsys):
        spkrs = Speakers()
        spkrs._speakers = [_make_device("Zone 2", ip="10.0.0.5", port=1500)]
        spkrs.print()
        assert "10.0.0.5:1500" in capsys.readouterr().out
