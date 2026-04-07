"""Tests for play_local_file.py — testable portions only."""

import pytest

from soco_cli.play_local_file import SUPPORTED_TYPES, is_supported_type


class TestIsSupportedType:
    # --- supported types ---

    def test_all_supported_types_recognised(self):
        for ext in SUPPORTED_TYPES:
            assert is_supported_type("track." + ext.lower()), ext
            assert is_supported_type("track." + ext.upper()), ext

    def test_mp3_lowercase(self):
        assert is_supported_type("song.mp3") is True

    def test_flac_uppercase(self):
        assert is_supported_type("song.FLAC") is True

    def test_wav_mixed_case(self):
        assert is_supported_type("song.Wav") is True

    def test_path_with_directories(self):
        assert is_supported_type("/home/user/music/song.mp3") is True

    def test_path_with_spaces(self):
        assert is_supported_type("/home/user/my music/song.flac") is True

    # --- unsupported types ---

    def test_txt_not_supported(self):
        assert is_supported_type("file.txt") is False

    def test_mp4_is_supported(self):
        assert is_supported_type("video.mp4") is True

    def test_avi_not_supported(self):
        assert is_supported_type("video.avi") is False

    def test_no_extension(self):
        assert is_supported_type("noextension") is False

    def test_dot_only(self):
        assert is_supported_type("file.") is False

    def test_extension_only_dot(self):
        assert is_supported_type(".mp3") is True

    def test_multiple_dots_uses_last_extension(self):
        # The function checks the whole uppercased filename for endings
        assert is_supported_type("my.song.mp3") is True

    def test_empty_string(self):
        assert is_supported_type("") is False
