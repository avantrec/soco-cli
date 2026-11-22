"""Tests for how api.run_command() formats captured output.

Single-line output is returned as-is. Multi-line output is returned with a
leading newline (unless it already starts with a blank line) and a trailing
newline. No live Sonos network is required: the speaker and the action are
mocked.
"""

from unittest.mock import MagicMock, patch

import pytest
from soco import SoCo  # type: ignore

from soco_cli.api import run_command


def _make_speaker():
    speaker = MagicMock(spec=SoCo)
    speaker.player_name = "Kitchen"
    speaker.ip_address = "192.0.2.1"
    return speaker


@pytest.mark.parametrize(
    "printed, expected",
    [
        ("", ""),
        ("24\n", "24"),
        ("24\n\n\n", "24"),
        ("a\nb\n", "\na\nb\n"),
        ("a\nb\nc\n\n", "\na\nb\nc\n"),
        ("\na\nb\n", "\na\nb\n"),
        ("\n\n\na\n", "\n\n\na\n"),
    ],
)
def test_multiline_output_formatting(printed, expected):
    def action(speaker, action, args, use_local_speaker_list=False):
        print(printed, end="")
        return True

    with patch("soco_cli.api.process_action", side_effect=action):
        assert run_command(_make_speaker(), "test") == (0, expected, "")
