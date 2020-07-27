#!/usr/bin/env python3
import soco
import argparse
import os
import sys
import platform
from signal import signal, SIGINT

if not "Windows" in platform.platform():
    from signal import SIGKILL
import pprint
import time
import datetime
import logging

from . import speakers
from . import __version__
from . import action_processor as ap
from . import utils

# Globals
speaker_list = None
pp = pprint.PrettyPrinter(width=100)


def error_and_exit(msg):
    # Print to stderror
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    os._exit(1)


def handler(signal_received, frame):
    # Exit silently without stack dump
    logging.info("Caught signal, exiting.")
    print(" CTRL-C ... exiting.")
    # ToDo: Temporary for now; hard kill required to get out of 'wait_for_stopped'
    #       Need to understand this.
    #       Not tested on Windows
    if not "Windows" in platform.platform() and ap.use_sigkill:
        os.kill(os.getpid(), SIGKILL)
    else:
        exit(0)


def convert_to_seconds(time_str):
    """Convert a time string to seconds.
    time_str can be one of Nh, Nm or Ns, or of the form HH:MM:SS
    """
    logging.info("Converting '{}' to a number of seconds".format(time_str))
    time_str = time_str.lower()
    try:
        if ":" in time_str:  # Assume form is HH:MM:SS or HH:MM
            parts = time_str.split(":")
            if len(parts) == 3:  # HH:MM:SS
                if 0 <= int(parts[1]) <= 59 and 0 <= int(parts[2]) <= 59:
                    duration = float(
                        int(parts[0]) * 60 * 60 + int(parts[1]) * 60 + int(parts[2])
                    )
                else:
                    duration = None
            else:  # HH:MM
                if 0 <= int(parts[1]) <= 59:
                    duration = float(int(parts[0]) * 60 * 60 + int(parts[1]) * 60)
                else:
                    duration = None
        elif time_str.endswith("s"):  # Seconds (explicit)
            duration = float(time_str[:-1])
        elif time_str.endswith("m"):  # Minutes
            duration = float(time_str[:-1]) * 60
        elif time_str.endswith("h"):  # Hours
            duration = float(time_str[:-1]) * 60 * 60
        else:  # Seconds (default)
            duration = float(time_str)
        return duration
    except ValueError:
        # Catch cast failures
        return None


def get_speaker(name, local=False):
    # Allow the use of an IP address even if 'local' is specified
    if speakers.Speakers.is_ipv4_address(name):
        logging.info("Using IP address instead of speaker name")
        return soco.SoCo(name)
    if local:
        logging.info("Using local speaker list")
        return speaker_list.find(name)
    else:
        logging.info("Using SoCo speaker discovery")
        return soco.discovery.by_name(name)


def version():
    print("soco-cli version: {}".format(__version__))
    print("soco version:     {}".format(soco.__version__))


def main():
    # Handle SIGINT
    signal(SIGINT, handler)

    # Create the argument parser
    parser = argparse.ArgumentParser(
        prog="sonos",
        usage="%(prog)s SPEAKER_NAME_OR_IP ACTION <parameters> <: ...>",
        description="Command line utility for controlling Sonos speakers",
    )
    # A variable number of arguments depending on the action
    parser.add_argument(
        "parameters", nargs="*", help="Sequences of SPEAKER ACTION <parameters> : ..."
    )
    # Optional arguments
    parser.add_argument(
        "--use-local-speaker-list",
        "-l",
        action="store_true",
        default=False,
        help="Use the local speaker list instead of SoCo discovery",
    )
    parser.add_argument(
        "--refresh-local-speaker-list",
        "-r",
        action="store_true",
        default=False,
        help="Refresh the local speaker list",
    )
    parser.add_argument(
        "--network-discovery-threads",
        "-t",
        type=int,
        default=128,
        help="Maximum number of threads used for Sonos network discovery",
    )
    parser.add_argument(
        "--network-discovery-timeout",
        "-n",
        type=float,
        default=2.0,
        help="Network timeout for Sonos device scan (seconds)",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        default=False,
        help="Print the soco-cli and SoCo versions and exit",
    )
    parser.add_argument(
        "--log",
        type=str,
        default="NONE",
        help="Set the logging level: 'NONE' (default) |'CRITICAL' | 'ERROR' | 'WARN'| 'INFO' | 'DEBUG'",
    )
    # Parse the command line
    args = parser.parse_args()

    if args.version:
        version()
        exit(0)

    # Set up logging
    log_level = args.log.lower()
    if log_level == "none":
        # Disables all logging (i.e., CRITICAL and below)
        logging.disable(logging.CRITICAL)
    else:
        log_format = (
            "%(asctime)s %(filename)s:%(lineno)s - %(funcName)s() - %(message)s"
        )
        if log_level == "debug":
            logging.basicConfig(format=log_format, level=logging.DEBUG)
        elif log_level == "info":
            logging.basicConfig(format=log_format, level=logging.INFO)
        elif log_level == "warning":
            logging.basicConfig(format=log_format, level=logging.WARNING)
        elif log_level == "error":
            logging.basicConfig(format=log_format, level=logging.ERROR)
        elif log_level == "critical":
            logging.basicConfig(format=log_format, level=logging.CRITICAL)
        else:
            error_and_exit(
                "--log takes one of: NONE, DEBUG, INFO, WARN, ERROR, CRITICAL"
            )

    use_local_speaker_list = args.use_local_speaker_list
    if use_local_speaker_list:
        global speaker_list
        speaker_list = speakers.Speakers(
            network_threads=args.network_discovery_threads,
            network_timeout=args.network_discovery_timeout,
        )
        if args.refresh_local_speaker_list or not speaker_list.load():
            logging.info("Start speaker discovery")
            speaker_list.discover()
            speaker_list.save()

    # Break up the command line into command sequences, observing the separator.
    command_line_separator = ":"
    sequence = []  # A single command sequence
    sequences = []  # A list of command sequences
    for arg in args.parameters:
        if len(arg) > 1 and command_line_separator in arg:
            # Catch special cases of colon use: HH:MM(:SS) time formats,
            # and URLs
            if not (
                sequence
                and sequence[-1]
                in [
                    "wait",
                    "wait_until",
                    "seek",
                    "sleep",
                    "sleep_timer",
                    "sleep_at",
                    "wait_stopped_for",
                    "loop_for",
                    "loop_until",
                ]
                or ":/" in arg
            ):
                error_and_exit(
                    "Spaces are required each side of the ':' command separator"
                )
        if arg != command_line_separator:
            sequence.append(arg)
        else:
            sequences.append(sequence)
            sequence = []
    if sequence:
        sequences.append(sequence)

    # Loop through processing command sequences
    logging.info("Found {} action sequence(s): {}".format(len(sequences), sequences))
    rewindable_sequences = utils.RewindableList(sequences)
    loop_iterator = None
    sequence_pointer = 0
    loop_pointer = (
        -1
    )  # There is a notional 'loop' action before the first command sequence
    loop_start_time = None
    for sequence in rewindable_sequences:
        try:
            speaker_name = sequence[0]

            # Special case: the 'loop' action
            if speaker_name.lower() == "loop":
                if len(sequence) == 2:
                    if loop_iterator is None:
                        try:
                            loop_iterator = int(sequence[1])
                            if loop_iterator <= 0:
                                raise ValueError
                            logging.info(
                                "Looping for {} iteration(s)".format(loop_iterator)
                            )
                        except ValueError:
                            error_and_exit(
                                "Action 'loop' takes no parameters, or a number of iterations (> 0)"
                            )
                    loop_iterator -= 1
                    if loop_iterator <= 0:
                        loop_iterator = None
                        loop_pointer = sequence_pointer + 1
                        sequence_pointer += 1
                        continue
                logging.info("Rewinding to command number {}".format(loop_pointer + 2))
                rewindable_sequences.rewind_to(loop_pointer + 1)
                sequence_pointer = loop_pointer
                continue

            # Special case: the 'loop_for' action
            if speaker_name.lower() == "loop_for":
                if len(sequence) != 2:
                    error_and_exit("Action 'loop_for' requires one parameter (duration)")
                if loop_start_time is None:
                    loop_start_time = time.time()
                    loop_duration = convert_to_seconds(sequence[1])
                    if not loop_duration:
                        error_and_exit("Action 'loop_for' requires one parameter (duration)")
                    logging.info("Starting action 'loop_for' for duration {}s".format(loop_duration))
                else:
                    if time.time() - loop_start_time >= loop_duration:
                        logging.info("Ending action 'loop_for' after duration {}s".format(loop_duration))
                        loop_start_time = None
                        continue
                logging.info("Rewinding to command number {}".format(loop_pointer + 2))
                rewindable_sequences.rewind_to(loop_pointer + 1)
                sequence_pointer = loop_pointer
                continue

            # Special case: the 'loop_until' action
            if speaker_name.lower() == "loop_until":
                if len(sequence) != 2:
                    error_and_exit("Action 'loop_until' requires one parameter (stop time)")
                if loop_start_time is None:
                    loop_start_time = time.time()
                    try:
                        loop_duration = ap.seconds_until(sequence[1])
                    except Exception as e:
                        error_and_exit("Action 'loop_until' requires one parameter (stop time)")
                    logging.info("Starting action 'loop_until' for duration {}s".format(loop_duration))
                else:
                    if time.time() - loop_start_time >= loop_duration:
                        logging.info("Ending action 'loop_until' after duration {}s".format(loop_duration))
                        loop_start_time = None
                        continue
                logging.info("Rewinding to command number {}".format(loop_pointer + 2))
                rewindable_sequences.rewind_to(loop_pointer + 1)
                sequence_pointer = loop_pointer
                continue

            # Special case: the 'wait' action
            if speaker_name in ["wait"]:
                if len(sequence) != 2:
                    error_and_exit("Action 'wait' requires 1 parameter")
                action = sequence[1].lower()
                duration = convert_to_seconds(action)
                if duration is not None:
                    logging.info("Waiting for {}s".format(duration))
                    time.sleep(duration)
                else:
                    error_and_exit(
                        "'wait' requires number hours, seconds or minutes + 'h/m/s', or HH:MM(:SS)"
                    )
                continue

            # Special case: the 'wait_until' action
            elif speaker_name in ["wait_until"]:
                if len(sequence) != 2:
                    error_and_exit("'wait_until' requires 1 parameter")
                try:
                    action = sequence[1].lower()
                    duration = ap.seconds_until(action)
                    logging.info("Waiting for {}s".format(duration))
                    time.sleep(duration)
                except ValueError:
                    error_and_exit(
                        "'wait_until' requires parameter: time in 24hr HH:MM(:SS) format"
                    )
                continue

            action = sequence[1].lower()
            args = sequence[2:]
            speaker = get_speaker(speaker_name, use_local_speaker_list)
            if not speaker:
                error_and_exit("Speaker '{}' not found".format(speaker_name))
            if not ap.process_action(speaker, action, args, use_local_speaker_list):
                error_and_exit(
                    "Action '{}' not found. \n\nAvailable actions are: {} and 'wait', 'wait_until'.\n".format(
                        action, list(ap.actions.keys())
                    )
                )

        except Exception as e:
            error_and_exit(str(e))
        sequence_pointer += 1

    exit(0)


if __name__ == "__main__":
    main()
