import unittest

import soco  # type: ignore

from soco_cli import action_processor as ap
from soco_cli.api import run_command

speaker_1 = soco.SoCo("192.168.0.42")
speaker_2 = soco.SoCo("192.168.0.39")

tests = [
    [speaker_1, "volume", ["25"], ""],
    [speaker_1, "volume", [], "25\n"],
    [speaker_1, "mute", ["on"], ""],
    [speaker_1, "mute", [], "on\n"],
    [speaker_1, "mute", ["off"], ""],
    [speaker_1, "mute", [], "off\n"],
    [speaker_1, "bass", ["0"], ""],
    [speaker_1, "bass", [], "0\n"],
    [speaker_1, "loudness", ["off"], ""],
    [speaker_1, "loudness", [], "off\n"],
    [speaker_1, "loudness", ["on"], ""],
    [speaker_1, "loudness", [], "on\n"],
]


def test_cli(capsys):
    for test in tests:
        ap.process_action(test[0], test[1], test[2], use_local_speaker_list=True)
        out, err = capsys.readouterr()
        assert out == test[3]


def test_api():
    for test in tests:
        exit_code, output, error_msg = run_command(
            test[0], test[1], *test[2], use_local_speaker_list=True
        )
        assert output == test[3].rstrip()


# class TestVolEQ(unittest.TestCase):
#     def test_volume(self, capsys):
#         sys.argv = ["-l", "stu", "track"]
#         sonos.main()
#         captured = capsys


if __name__ == "__main__":
    unittest.main()
