import logging
import os
from os import chdir, name, path
from pathlib import Path
from random import choice, sample
import signal
import sys
from threading import Thread
from .m3u_parser import parse_m3u
from .play_local_file import play_local_file, is_supported_type
from .utils import error_and_exit, set_sigterm


def wait_for_keypress():
    # Wait for a key press on the console and return it
    result = None

    if name == "nt":  # Windows
        import msvcrt

        result = msvcrt.getch().decode()
    else:  # Linux & macOS
        import termios

        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        try:
            result = sys.stdin.read(1)
        except IOError:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
    return result


def interactive_thread(speaker):
    set_sigterm(True)
    keypress = wait_for_keypress()
    if keypress in ["N", "n"]:
        action = "NEXT"
        print("Next track ...")
        speaker.stop()
        logging.info(
            "Interactive mode: key = '{}', action = '{}'".format(keypress, action)
        )
    if keypress in ["P", "p"]:
        action = "PAUSE"
        print("Pause playback ...")
        try:
            speaker.pause()
        except Exception as e:
            logging.info("Exception ignored: {}".format(e))
            pass
        logging.info(
            "Interactive mode: key = '{}', action = '{}'".format(keypress, action)
        )
    if keypress in ["R", "r"]:
        action = "RESUME"
        print("Resume playback ...")
        try:
            speaker.play()
        except Exception as e:
            logging.info("Exception ignored: {}".format(e))
            pass
        logging.info(
            "Interactive mode: key = '{}', action = '{}'".format(keypress, action)
        )
    # Windows captures CTRL-C key-presses, so we handle them directly here
    if name == "nt" and keypress == "\x03":
        logging.info("Windows CTRL-C: Stopping speaker '{}' and exiting".format(speaker.player_name))
        speaker.stop()
        os._exit(0)


def play_m3u_file(speaker, m3u_file, options=""):
    """Play a M3U or M3U8 file"""
    options = options.lower()

    # Check for invalid options
    invalid = set(options) - set("psri")
    if invalid:
        error_and_exit("Invalid option(s) '{}' supplied".format(invalid))
        return False

    if not (m3u_file.lower().endswith(".m3u") or m3u_file.lower().endswith(".m3u8")):
        error_and_exit(
            "Filename '{}' does not end in '.m3u' or '.m3u8'".format(m3u_file)
        )
        return False

    if not path.exists(m3u_file):
        error_and_exit("File '{}' not found".format(m3u_file))
        return False

    logging.info("Parsing M3U file '{}'".format(m3u_file))
    tracks = parse_m3u(m3u_file)
    if not tracks:
        error_and_exit("No tracks found in '{}'".format(m3u_file))

    logging.info("Found {} tracks".format(len(tracks)))

    if "r" in options:
        # Choose a single random track
        track = choice(tracks)
        tracks = [track]
        logging.info("Choosing random track: {}".format(track.path))

    elif "s" in options:
        logging.info("Shuffling playlist")
        # For some reason, 'shuffle(tracks)' does not work
        tracks = sample(tracks, len(tracks))

    directory, _ = path.split(m3u_file)
    if directory != "":
        chdir(directory)

    if "i" in options:
        print("Interactive mode actions: (N)ext, (P)ause, (R)esume, CTRL-C")

    zero_pad = len(str(len(tracks)))
    for index, track in enumerate(tracks):
        abs_filename = str(Path(track.path).absolute())
        logging.info("Convert '{}' to '{}'".format(track.path, abs_filename))

        if not path.exists(abs_filename):
            print("Error: file not found:", abs_filename)
            continue

        if not is_supported_type(abs_filename):
            print("Error: unsupported file type:", abs_filename)
            continue

        # Interactive mode
        keypress_thread = None
        if "i" in options:
            try:
                logging.info("Interactive mode ... starting keypress thread")
                keypress_thread = Thread(
                    target=interactive_thread, args=(speaker,), daemon=True
                )
                keypress_thread.start()
            except Exception as e:
                logging.info("Exception ignored: {}".format(e))
                pass

        if "p" in options:
            print(
                "Playing {} of {}:".format(str(index + 1).zfill(zero_pad), len(tracks)),
                abs_filename,
            )

        play_local_file(speaker, abs_filename)

        if keypress_thread:
            keypress_thread.join(timeout=0.1)

    return True
