"""Tests for m3u_parser.py."""

import os
import tempfile

import pytest

import soco_cli.utils as utils
from soco_cli.m3u_parser import Track, parse_m3u


@pytest.fixture(autouse=True)
def api_mode():
    original = utils.API
    utils.API = True
    yield
    utils.API = original


def _write_tempfile(content, suffix=".m3u"):
    """Write content to a named temporary file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------


class TestTrack:
    def test_attributes_set(self):
        t = Track("300", "My Song", "/path/to/song.mp3")
        assert t.length == "300"
        assert t.title == "My Song"
        assert t.path == "/path/to/song.mp3"

    def test_none_values_allowed(self):
        t = Track(None, None, None)
        assert t.length is None
        assert t.title is None
        assert t.path is None


# ---------------------------------------------------------------------------
# parse_m3u — .m3u files (require #EXTM3U header)
# ---------------------------------------------------------------------------


class TestParseMp3u:
    def test_valid_m3u_with_extinf(self):
        content = "#EXTM3U\n" "#EXTINF:300,Artist - Title\n" "/music/track.mp3\n"
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert len(tracks) == 1
        assert tracks[0].length == "300"
        assert tracks[0].title == "Artist - Title"
        assert tracks[0].path == "/music/track.mp3"

    def test_multiple_tracks(self):
        content = (
            "#EXTM3U\n"
            "#EXTINF:120,Track One\n"
            "/music/one.mp3\n"
            "#EXTINF:240,Track Two\n"
            "/music/two.flac\n"
        )
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert len(tracks) == 2
        assert tracks[0].title == "Track One"
        assert tracks[1].title == "Track Two"

    def test_missing_extinf_header_still_adds_track(self):
        # A path line without a preceding #EXTINF creates a Track with None metadata
        content = "#EXTM3U\n/music/track.mp3\n"
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert len(tracks) == 1
        assert tracks[0].path == "/music/track.mp3"
        assert tracks[0].length is None
        assert tracks[0].title is None

    def test_comment_lines_skipped(self):
        content = (
            "#EXTM3U\n"
            "# This is a comment\n"
            "#EXTINF:60,My Track\n"
            "/music/track.mp3\n"
        )
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert len(tracks) == 1

    def test_blank_lines_skipped(self):
        content = "#EXTM3U\n" "\n" "#EXTINF:60,My Track\n" "\n" "/music/track.mp3\n"
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert len(tracks) == 1

    def test_missing_extm3u_header_returns_empty(self, capsys):
        content = "#EXTINF:60,My Track\n/music/track.mp3\n"
        path = _write_tempfile(content, suffix=".m3u")
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert tracks == []
        assert "lacks '#EXTM3U'" in capsys.readouterr().err

    def test_empty_playlist(self):
        content = "#EXTM3U\n"
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert tracks == []

    def test_title_with_comma_preserved(self):
        # split(",", 1) means only the first comma is the EXTINF delimiter
        content = "#EXTM3U\n#EXTINF:180,Artist, Title With Comma\n/music/t.mp3\n"
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert tracks[0].title == "Artist, Title With Comma"

    def test_path_whitespace_stripped(self):
        content = "#EXTM3U\n#EXTINF:60,T\n  /music/track.mp3  \n"
        path = _write_tempfile(content)
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert tracks[0].path == "/music/track.mp3"

    # --- non-.m3u extension: header not required ---

    def test_non_m3u_extension_skips_header_check(self):
        content = "#EXTINF:60,My Track\n/music/track.mp3\n"
        path = _write_tempfile(content, suffix=".txt")
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert len(tracks) == 1

    def test_m3u8_extension_requires_header(self, capsys):
        content = "#EXTINF:60,My Track\n/music/track.mp3\n"
        path = _write_tempfile(content, suffix=".m3u8")
        try:
            tracks = parse_m3u(path)
        finally:
            os.unlink(path)
        assert tracks == []
        capsys.readouterr()  # suppress output
