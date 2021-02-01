"""Plays a list of files from the local filesystem, with interactive options."""

import logging
import os
import sys
from multiprocessing import Process
from os import chdir, name, path
from pathlib import Path
from random import choice, sample

from soco import SoCo

from soco_cli.m3u_parser import parse_m3u
from soco_cli.play_local_file import is_supported_type, play_local_file
from soco_cli.utils import error_and_exit

# def wait_for_keypress():
#     # Wait for a key press on the console and return it
#     result = None
#
#     if name == "nt":  # Windows
#         import msvcrt
#
#         result = msvcrt.getch().decode()
#     else:  # Linux & macOS
#         import termios
#
#         fd = sys.stdin.fileno()
#         oldterm = termios.tcgetattr(fd)
#         newattr = termios.tcgetattr(fd)
#         newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
#         termios.tcsetattr(fd, termios.TCSANOW, newattr)
#         try:
#             result = sys.stdin.read(1)
#         except IOError:
#             pass
#         finally:
#             termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
#     return result


def interaction_manager(speaker_ip):
    sys.stdin = open(0)
    speaker = SoCo(speaker_ip)
    while True:
        try:
            # keypress = wait_for_keypress()
            keypress = input("")[0]
        except:
            keypress = None
            pass
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
            logging.info(
                "Windows CTRL-C: Stopping speaker '{}' and exiting".format(
                    speaker.player_name
                )
            )
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

    if not path.exists(m3u_file):
        error_and_exit("File '{}' not found".format(m3u_file))
        return False

    # if not (m3u_file.lower().endswith(".m3u") or m3u_file.lower().endswith(".m3u8")):
    #     error_and_exit(
    #         "Filename '{}' does not end in '.m3u' or '.m3u8'".format(m3u_file)
    #     )
    #     return False

    logging.info("Parsing file contents'{}'".format(m3u_file))
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

    # Interactive mode
    keypress_process = None
    if "i" in options:
        print("Interactive mode actions: (N)ext, (P)ause, (R)esume + RETURN")
        try:
            logging.info("Interactive mode ... starting keypress process")
            keypress_process = Process(
                target=interaction_manager, args=(speaker.ip_address,), daemon=True
            )
            keypress_process.start()
            logging.info("Process PID {} created".format(keypress_process.pid))
        except Exception as e:
            logging.info("Exception ignored: {}".format(e))
            keypress_process = None
            pass

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

        if "p" in options:
            print(
                "Playing {} of {}:".format(str(index + 1).zfill(zero_pad), len(tracks)),
                abs_filename,
            )

        play_local_file(speaker, abs_filename)

    if keypress_process:
        keypress_process.terminate()

    if "p" in options:
        print("End of playlist")

    return True
