import soco
import unittest

from soco_cli import action_processor as ap

speaker_1 = soco.SoCo("192.168.0.42")
speaker_2 = soco.SoCo("192.168.0.39")

tests = [
    [speaker_1, "volume", ["25"], ""],
    [speaker_1, "volume", [], "25\n"],
    [speaker_1, "mute", ["on"], ""],
    [speaker_1, "mute", [], "on\n"],
    [speaker_1, "mute", ["off"], ""],
    [speaker_1, "mute", [], "off\n"],
]


def test_cli(capsys):
    for test in tests:
        ap.process_action(test[0], test[1], test[2], True)
        out, err = capsys.readouterr()
        assert out == test[3]


# class TestVolEQ(unittest.TestCase):
#     def test_volume(self, capsys):
#         sys.argv = ["-l", "stu", "track"]
#         sonos.main()
#         captured = capsys


if __name__ == "__main__":
    unittest.main()
