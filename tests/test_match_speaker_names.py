"""Tests for match_speaker_names.py."""

from soco_cli.match_speaker_names import speaker_name_matches


class TestSpeakerNameMatches:
    # --- exact match ---

    def test_exact_match(self):
        match, exact = speaker_name_matches("Kitchen", "Kitchen")
        assert match is True
        assert exact is True

    def test_exact_match_with_spaces(self):
        match, exact = speaker_name_matches("Living Room", "Living Room")
        assert match is True
        assert exact is True

    # --- case-insensitive exact match ---

    def test_case_insensitive_match(self):
        match, exact = speaker_name_matches("kitchen", "Kitchen")
        assert match is True
        assert exact is True

    def test_uppercase_supplied(self):
        match, exact = speaker_name_matches("KITCHEN", "Kitchen")
        assert match is True
        assert exact is True

    def test_mixed_case(self):
        match, exact = speaker_name_matches("kItChEn", "Kitchen")
        assert match is True
        assert exact is True

    # --- apostrophe normalisation exact match ---

    def test_straight_apostrophe_matches_curly(self):
        # Supplied uses straight apostrophe; stored uses curly/Unicode
        match, exact = speaker_name_matches("Bob's Room", "Bob\u2019s Room")
        assert match is True
        assert exact is True

    def test_curly_apostrophe_matches_straight(self):
        match, exact = speaker_name_matches("Bob\u2019s Room", "Bob's Room")
        assert match is True
        assert exact is True

    # --- partial start-of-name match ---

    def test_partial_start_of_name(self):
        match, exact = speaker_name_matches("Kit", "Kitchen")
        assert match is True
        assert exact is False

    def test_partial_first_word_of_multi_word_name(self):
        match, exact = speaker_name_matches("living", "Living Room")
        assert match is True
        assert exact is False

    # --- partial anywhere-in-name match ---

    def test_partial_middle_of_name(self):
        match, exact = speaker_name_matches("itchen", "Kitchen")
        assert match is True
        assert exact is False

    def test_partial_end_of_name(self):
        match, exact = speaker_name_matches("room", "Living Room")
        assert match is True
        assert exact is False

    def test_partial_substring_match(self):
        match, exact = speaker_name_matches("ing Ro", "Living Room")
        assert match is True
        assert exact is False

    # --- no match ---

    def test_no_match(self):
        match, exact = speaker_name_matches("Bedroom", "Kitchen")
        assert match is False
        assert exact is False

    def test_no_match_superset_not_counted(self):
        # Supplied is longer than stored — not a partial match
        match, exact = speaker_name_matches("Kitchen Cabinet", "Kitchen")
        assert match is False
        assert exact is False

    # --- edge cases ---

    def test_empty_supplied_matches_anything_partial(self):
        # Empty string is always a start-of-name match
        match, exact = speaker_name_matches("", "Kitchen")
        assert match is True
        assert exact is False

    def test_single_character_match(self):
        match, exact = speaker_name_matches("K", "Kitchen")
        assert match is True
        assert exact is False

    def test_identical_single_character(self):
        match, exact = speaker_name_matches("K", "K")
        assert match is True
        assert exact is True
