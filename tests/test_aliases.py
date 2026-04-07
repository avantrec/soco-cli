"""Tests for aliases.py — AliasManager."""

import os
import tempfile
from unittest.mock import patch

import pytest

from soco_cli.aliases import AliasManager

# ---------------------------------------------------------------------------
# create_alias / action / remove_alias / alias_names
# ---------------------------------------------------------------------------


class TestCreateAndRetrieve:
    def test_create_new_alias(self):
        am = AliasManager()
        result, new = am.create_alias("vol50", "volume 50")
        assert result is True
        assert new is True
        assert am.action("vol50") == "volume 50"

    def test_update_existing_alias(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        result, new = am.create_alias("vol", "volume 75")
        assert result is True
        assert new is False
        assert am.action("vol") == "volume 75"

    def test_none_action_removes_alias(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        result = am.create_alias("vol", None)
        assert result is True  # remove_alias returns True
        assert am.action("vol") is None

    def test_empty_string_action_removes_alias(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        am.create_alias("vol", "")
        assert am.action("vol") is None

    def test_alias_name_whitespace_stripped(self):
        am = AliasManager()
        am.create_alias("  vol  ", "volume 50")
        assert am.action("vol") == "volume 50"

    def test_action_returns_none_for_unknown_alias(self):
        am = AliasManager()
        assert am.action("nonexistent") is None

    def test_action_value_whitespace_stripped(self):
        am = AliasManager()
        am.create_alias("vol", "  volume 50  ")
        assert am.action("vol") == "volume 50"


class TestRemoveAlias:
    def test_remove_existing_alias(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        result = am.remove_alias("vol")
        assert result is True
        assert am.action("vol") is None

    def test_remove_nonexistent_alias_returns_false(self):
        am = AliasManager()
        result = am.remove_alias("nonexistent")
        assert result is False

    def test_remove_name_whitespace_stripped(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        result = am.remove_alias("  vol  ")
        assert result is True


class TestAliasNames:
    def test_empty_manager_returns_empty_list(self):
        am = AliasManager()
        assert am.alias_names() == []

    def test_returns_all_alias_names(self):
        am = AliasManager()
        am.create_alias("a", "action_a")
        am.create_alias("b", "action_b")
        names = am.alias_names()
        assert set(names) == {"a", "b"}

    def test_removed_alias_not_in_names(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        am.remove_alias("vol")
        assert "vol" not in am.alias_names()


# ---------------------------------------------------------------------------
# _aliases_to_text
# ---------------------------------------------------------------------------


class TestAliasesToText:
    def test_raw_format(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        text = am._aliases_to_text(raw=True)
        assert "vol" in text
        assert "volume 50" in text
        assert "=" in text

    def test_pretty_format_indented(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        text = am._aliases_to_text(raw=False)
        # Pretty format has leading spaces and padding
        assert text.startswith("  ")

    def test_multiple_aliases_sorted(self):
        am = AliasManager()
        am.create_alias("z_alias", "z action")
        am.create_alias("a_alias", "a action")
        text = am._aliases_to_text(raw=True)
        assert text.index("a_alias") < text.index("z_alias")


# ---------------------------------------------------------------------------
# save_aliases_to_file / load_aliases_from_file
# ---------------------------------------------------------------------------


class TestFileRoundTrip:
    def test_save_and_load_round_trip(self):
        am = AliasManager()
        am.create_alias("vol50", "volume 50")
        am.create_alias("playjazz", "play_favourite Jazz")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            tmpfile = f.name
        try:
            am.save_aliases_to_file(tmpfile)

            am2 = AliasManager()
            with patch.object(am2, "save_aliases"):  # don't touch ~/.soco-cli
                result = am2.load_aliases_from_file(tmpfile)

            assert result is True
            assert am2.action("vol50") == "volume 50"
            assert am2.action("playjazz") == "play_favourite Jazz"
        finally:
            os.unlink(tmpfile)

    def test_saved_file_has_header_comment(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            tmpfile = f.name
        try:
            am.save_aliases_to_file(tmpfile)
            with open(tmpfile) as f:
                first_line = f.readline()
            assert first_line.startswith("#")
        finally:
            os.unlink(tmpfile)

    def test_save_to_nonexistent_path_returns_false(self):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        result = am.save_aliases_to_file("/nonexistent_dir/aliases.txt")
        assert result is False

    def test_load_comment_lines_ignored(self):
        content = "# This is a comment\nvol = volume 50\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, delete_on_close=False
        ) as f:
            f.write(content)
            tmpfile = f.name
        try:
            am = AliasManager()
            with patch.object(am, "save_aliases"):
                am.load_aliases_from_file(tmpfile)
            assert am.action("vol") == "volume 50"
        finally:
            os.unlink(tmpfile)

    def test_load_malformed_line_skipped(self, capsys):
        # Line without exactly one '=' is malformed and skipped
        content = "malformed_no_equals\nvol = volume 50\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            tmpfile = f.name
        try:
            am = AliasManager()
            with patch.object(am, "save_aliases"):
                am.load_aliases_from_file(tmpfile)
            assert am.action("vol") == "volume 50"
            assert "Malformed" in capsys.readouterr().out
        finally:
            os.unlink(tmpfile)

    def test_load_from_nonexistent_file_returns_false(self):
        am = AliasManager()
        result = am.load_aliases_from_file("/nonexistent_path/aliases.txt")
        assert result is False

    def test_load_blank_lines_skipped(self):
        content = "\nvol = volume 50\n\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            tmpfile = f.name
        try:
            am = AliasManager()
            with patch.object(am, "save_aliases"):
                am.load_aliases_from_file(tmpfile)
            assert am.action("vol") == "volume 50"
        finally:
            os.unlink(tmpfile)


# ---------------------------------------------------------------------------
# print_aliases
# ---------------------------------------------------------------------------


class TestPrintAliases:
    def test_empty_manager_prints_message(self, capsys):
        am = AliasManager()
        am.print_aliases()
        assert "No current aliases" in capsys.readouterr().out

    def test_aliases_printed(self, capsys):
        am = AliasManager()
        am.create_alias("vol", "volume 50")
        am.print_aliases()
        out = capsys.readouterr().out
        assert "vol" in out
        assert "volume 50" in out
