"""Tests for play_local_file.py — testable portions only."""

from soco_cli.play_local_file import (
    MIME_TYPES,
    SUPPORTED_TYPES,
    get_mime_type,
    get_uri_title_and_mime_type,
    is_supported_type,
)


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


class TestGetMimeType:
    def test_every_supported_type_has_mime_type(self):
        for ext in SUPPORTED_TYPES:
            assert get_mime_type("track." + ext.lower()) == MIME_TYPES[ext], ext

    def test_unsupported(self):
        assert get_mime_type("file.txt") is None
        assert get_mime_type("noextension") is None


class TestGetUriTitleAndMimeType:
    def test_http_flac(self):
        assert get_uri_title_and_mime_type("http://host:8000/music/Song.flac") == (
            "Song",
            "audio/flac",
        )

    def test_https_mp3(self):
        assert get_uri_title_and_mime_type("https://host/a/b/track.MP3") == (
            "track",
            "audio/mpeg",
        )

    def test_url_encoded_filename(self):
        assert get_uri_title_and_mime_type("http://host/My%20Song.m4a") == (
            "My Song",
            "audio/mp4",
        )

    def test_query_string_ignored(self):
        assert get_uri_title_and_mime_type("http://host/song.ogg?token=abc") == (
            "song",
            "audio/ogg",
        )

    def test_unknown_extension(self):
        assert get_uri_title_and_mime_type("http://host/stream") == ("", None)
        assert get_uri_title_and_mime_type("http://host/playlist.m3u") == ("", None)

    def test_non_http_scheme(self):
        assert get_uri_title_and_mime_type("x-file-cifs://server/share/song.mp3") == (
            "",
            None,
        )
        assert get_uri_title_and_mime_type("x-sonos-spotify:spotify%3atrack%3a123") == (
            "",
            None,
        )
