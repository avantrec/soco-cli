"""Plays a list of files from the local filesystem, with interactive options."""

import logging
import os
import sys
from multiprocessing import Process
from os import chdir, name, path, scandir
from pathlib import Path
from random import choice, sample
from typing import List

from soco import SoCo  # type: ignore

from soco_cli.m3u_parser import parse_m3u
from soco_cli.play_local_file import is_supported_type, play_local_file
from soco_cli.utils import error_report


def interaction_manager(speaker_ip: str) -> None:
    sys.stdin = open(0)
    speaker = SoCo(speaker_ip)
    while True:
        try:
            # keypress = wait_for_keypress()
            keypress = input("")[0]
        except:
            keypress = ""
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


def play_file_list(speaker: SoCo, tracks: List[str], options: str = "") -> bool:
    """Play a list of files (tracks) with absolute pathnames."""
    options = options.lower()

    # Check for invalid options
    invalid = set(options) - set("psri")
    if invalid:
        error_report("Invalid option(s) '{}' supplied".format(invalid))
        return False

    if options != "":
        # Grab back stdout from api.run_command()
        sys.stdout = sys.__stdout__

    if "r" in options:
        # Choose a single random track
        track = choice(tracks)
        tracks = [track]
        logging.info("Choosing random track: {}".format(track))

    elif "s" in options:
        logging.info("Shuffling playlist")
        # For some reason, 'shuffle(tracks)' does not work
        tracks = sample(tracks, len(tracks))

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

    zero_pad = len(str(len(tracks)))
    for index, track in enumerate(tracks):
        if not path.exists(track):
            print("Error: file not found:", track)
            continue

        if not is_supported_type(track):
            print("Error: unsupported file type:", track)
            continue

        if "p" in options:
            print(
                "Playing {} of {}:".format(str(index + 1).zfill(zero_pad), len(tracks)),
                track,
            )

        play_local_file(speaker, track)

    if keypress_process:
        keypress_process.terminate()

    return True


def play_m3u_file(speaker: SoCo, m3u_file: str, options: str = "") -> bool:
    if not path.exists(m3u_file):
        error_report("File '{}' not found".format(m3u_file))
        return False

    logging.info("Parsing file contents'{}'".format(m3u_file))
    track_list = parse_m3u(m3u_file)
    if len(track_list) == 0:
        error_report("No tracks found in '{}'".format(m3u_file))
        return False

    directory, _ = path.split(m3u_file)
    if directory != "":
        chdir(directory)
    tracks = [str(Path(track.path).absolute()) for track in track_list]  # type:ignore
    logging.info("Files to to play: {}".format(tracks))

    play_file_list(speaker, tracks, options)
    return True


def play_directory_files(speaker: SoCo, directory: str, options: str = "") -> bool:
    """Play all the valid audio files in a directory. Ignores subdirectories"""
    tracks = []
    try:
        with scandir(directory) as files:
            for file in files:
                if is_supported_type(file.name):
                    tracks.append(path.abspath(path.join(directory, file.name)))
    except FileNotFoundError:
        error_report("Directory '{}' not found".format(directory))
        return False

    tracks.sort()
    logging.info("Files to to play: {}".format(tracks))
    play_file_list(speaker, tracks, options)
    return True
