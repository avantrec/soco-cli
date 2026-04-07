"""Tests for cmd_parser.py."""

from soco_cli.cmd_parser import CLIParser


class TestCLIParser:
    # --- basic parsing ---

    def test_empty_args_produces_no_sequences(self):
        p = CLIParser()
        p.parse([])
        assert p.get_sequences() == []

    def test_single_token(self):
        p = CLIParser()
        p.parse(["play"])
        assert p.get_sequences() == [["play"]]

    def test_single_sequence_multiple_tokens(self):
        p = CLIParser()
        p.parse(["volume", "50"])
        assert p.get_sequences() == [["volume", "50"]]

    # --- colon separation ---

    def test_two_sequences_separated_by_colon(self):
        p = CLIParser()
        p.parse(["play", ":", "volume", "50"])
        assert p.get_sequences() == [["play"], ["volume", "50"]]

    def test_three_sequences(self):
        p = CLIParser()
        p.parse(["play", ":", "volume", "50", ":", "mute", "off"])
        assert p.get_sequences() == [["play"], ["volume", "50"], ["mute", "off"]]

    def test_ordering_preserved(self):
        p = CLIParser()
        p.parse(["a", "b", "c", ":", "d", "e"])
        assert p.get_sequences() == [["a", "b", "c"], ["d", "e"]]

    # --- edge cases ---

    def test_colon_at_start_produces_empty_first_sequence(self):
        p = CLIParser()
        p.parse([":", "play"])
        assert p.get_sequences() == [[], ["play"]]

    def test_colon_at_end_has_no_trailing_sequence(self):
        # Trailing colon: the empty final sequence is not appended
        # because the code only appends when 'if sequence' is True.
        p = CLIParser()
        p.parse(["play", ":"])
        assert p.get_sequences() == [["play"]]

    def test_consecutive_colons_produce_empty_middle_sequence(self):
        p = CLIParser()
        p.parse(["play", ":", ":", "pause"])
        assert p.get_sequences() == [["play"], [], ["pause"]]

    def test_colon_only_produces_one_empty_sequence(self):
        p = CLIParser()
        p.parse([":"])
        assert p.get_sequences() == [[]]

    def test_parse_can_be_called_multiple_times(self):
        p = CLIParser()
        p.parse(["play"])
        p.parse(["volume", "50"])
        assert p.get_sequences() == [["volume", "50"]]
