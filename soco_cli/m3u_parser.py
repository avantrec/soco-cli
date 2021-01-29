# Derived from https://github.com/dvndrsn/M3uParser ... thanks!
#
# more info on the M3U file format available here:
# http://n4k3d.com/the-m3u-file-format/

import sys

from soco_cli.utils import error_and_exit


class Track:
    def __init__(self, length, title, path):
        self.length = length
        self.title = title
        self.path = path


"""
    song info lines are formatted like:
    EXTINF:419,Alice In Chains - Rotten Apple
    length (seconds)
    Song title
    file name - relative or absolute path of file
    ..\Minus The Bear - Planet of Ice\Minus The Bear_Planet of Ice_01_Burying Luck.mp3
"""


def parse_m3u(m3u_file):
    with open(m3u_file, "r") as infile:
        """
        Parse file contents. Files with an M3U/M3U8 extension must follow conventions.
        """

        if m3u_file.lower().endswith(".m3u") or m3u_file.lower().endswith(".m3u8"):
            line = infile.readline()
            if not line.startswith("#EXTM3U"):
                error_and_exit(
                    "File '{}' lacks '#EXTM3U' as first line".format(m3u_file)
                )
                return None

        playlist = []
        song = Track(None, None, None)
        for line in infile:
            line = line.strip()
            if line.startswith("#EXTINF:"):
                # pull length and title from #EXTINF line
                length, title = line.split("#EXTINF:")[1].split(",", 1)
                song = Track(length, title, None)
            elif line.startswith("#"):
                # Comment line
                pass
            elif len(line) != 0:
                # pull song path from all other, non-blank lines
                song.path = line
                playlist.append(song)
                # reset the song variable so it doesn't use the same EXTINF more than once
                song = Track(None, None, None)

        return playlist
