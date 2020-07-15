#!/usr/bin/env python3
import soco
import argparse
import os
import sys
from signal import signal, SIGINT
import pprint
import time

from . import speakers
from . import __version__
from . import action_processor as ap

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
    exit(0)


def get_speaker(name, local=False):
    # Allow the use of an IP address even if 'local' is specified
    if speakers.Speakers.is_ipv4_address(name):
        return soco.SoCo(name)
    if local:
        return speaker_list.find(name)
    else:
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
        default=10.0,
        help="Network timeout for Sonos device scan (seconds)",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        default=False,
        help="Print the soco-cli and SoCo versions and exit",
    )

    # Parse the command line
    args = parser.parse_args()

    if args.version:
        version()
        exit(0)

    use_local_speaker_list = args.use_local_speaker_list
    if use_local_speaker_list:
        global speaker_list
        speaker_list = speakers.Speakers(
            network_threads=args.network_discovery_threads,
            network_timeout=args.network_discovery_timeout,
        )
        if args.refresh_local_speaker_list or not speaker_list.load():
            speaker_list.discover()
            speaker_list.save()

    # Break up the command line into command sequences, observing the separator.
    command_line_separator = ":"
    sequence = []  # A single command sequence
    sequences = []  # A list of command sequences
    for arg in args.parameters:
        if len(arg) > 1 and command_line_separator in arg:
            # Catch special cases of colon use: 'seek' action and URLs
            if not (sequence and sequence[-1] == "seek" or ":/" in arg):
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
    for sequence in sequences:
        try:
            if len(sequence) < 2:
                error_and_exit("{}: At least two arguments required".format(sequence))
            speaker = None
            speaker_name = sequence[0]
            action = sequence[1].lower()
            # Special case of a "wait" command
            # Assume there aren't any speakers called 'wait':
            if speaker_name in ["wait"]:
                duration = 0
                try:
                    if action.endswith("s"):  # Seconds (explicit)
                        duration = float(action[:-1])
                    elif action.endswith("m"):  # Minutes
                        duration = float(action[:-1]) * 60
                    elif action.endswith("h"):  # Hours
                        duration = float(action[:-1]) * 60 * 60
                    else:  # Seconds (default)
                        duration = float(action)
                except:
                    error_and_exit(
                        "'wait' requires integer number of seconds, or float number of minutes + 'm'"
                    )
                time.sleep(duration)
                continue
            args = sequence[2:]
            speaker = get_speaker(speaker_name, use_local_speaker_list)
            if not speaker:
                error_and_exit("Speaker '{}' not found".format(speaker_name))
            if not ap.process_action(speaker, action, args, use_local_speaker_list):
                error_and_exit(
                    "Action '{}' not found. \n\nAvailable actions are: {} and 'wait'.\n".format(
                        action, list(ap.actions.keys())
                    )
                )
        except Exception as e:
            error_and_exit(str(e))
    exit(0)


if __name__ == "__main__":
    main()
