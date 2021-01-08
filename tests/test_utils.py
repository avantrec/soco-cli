import unittest

from soco_cli.utils import convert_to_seconds


class MyTestCase(unittest.TestCase):
    def test_convert_to_seconds(self):
        assert convert_to_seconds("00:01:01") == 61
        assert convert_to_seconds("01:30") == 90 * 60
        assert convert_to_seconds("12s") == 12
        assert convert_to_seconds("3m") == 180
        assert convert_to_seconds("2h") == 2 * 60 * 60
        with self.assertRaises(ValueError):
            seconds = convert_to_seconds("")
        assert convert_to_seconds("00:61:65") == (61 * 60) + 65


if __name__ == "__main__":
    unittest.main()
