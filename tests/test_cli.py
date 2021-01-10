import soco
import unittest

from soco_cli import action_processor as ap


def test_volume(capsys):
    speaker = soco.SoCo("192.168.0.42")
    action = "volume"
    use_local_speaker_list = True
    args = ["25"]
    ap.process_action(speaker, action, args, use_local_speaker_list)
    assert capsys.readouterr().out == ""
    args = []
    ap.process_action(speaker, action, args, use_local_speaker_list)
    assert capsys.readouterr().out == "25\n"


# class TestVolEQ(unittest.TestCase):
#     def test_volume(self, capsys):
#         sys.argv = ["-l", "stu", "track"]
#         sonos.main()
#         captured = capsys


if __name__ == '__main__':
    unittest.main()
