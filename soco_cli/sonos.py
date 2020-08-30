#!/usr/bin/env python3
import argparse
from signal import signal, SIGINT
import pprint
import time
import logging

from .speakers import Speakers
from .action_processor import process_action
from .utils import (
    error_and_exit,
    convert_to_seconds,
    version,
    sig_handler,
    configure_logging,
    RewindableList,
    seconds_until,
    get_speaker,
    set_speaker_list,
    configure_common_args,
)

# Globals
pp = pprint.PrettyPrinter(width=100)


def main():
    # Handle SIGINT
    signal(SIGINT, sig_handler)

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
    # The rest of the optional args are common
    configure_common_args(parser)

    # Parse the command line
    args = parser.parse_args()

    if args.version:
        version()
        exit(0)

    configure_logging(args.log)

    use_local_speaker_list = args.use_local_speaker_list
    if use_local_speaker_list:
        speaker_list = Speakers(
            network_threads=args.network_discovery_threads,
            network_timeout=args.network_discovery_timeout,
        )
        if args.refresh_local_speaker_list or not speaker_list.load():
            logging.info("Start speaker discovery")
            speaker_list.discover()
            speaker_list.save()
        set_speaker_list(speaker_list)

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
                    "wait_for",
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
    rewindable_sequences = RewindableList(sequences)
    loop_iterator = None
    sequence_pointer = 0
    loop_pointer = (
        -1
    )  # There is a notional 'loop' action before the first command sequence
    loop_start_time = None
    for sequence in rewindable_sequences:
        try:
            speaker_name = sequence[0]

            # Special case: the 'loop_to_start' action
            if speaker_name.lower() == "loop_to_start":
                if len(sequence) != 1:
                    error_and_exit("Action 'loop_to_start' takes no parameters")
                # Reset pointers, rewind and continue
                loop_pointer = -1
                sequence_pointer = 0
                logging.info("Rewind to start of command sequences")
                rewindable_sequences.rewind()
                continue

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
                    logging.info("Loop iterator countdown = {}".format(loop_iterator))
                    if loop_iterator <= 0:
                        # Reset variables, stop iteration and continue
                        loop_iterator = None
                        loop_pointer = sequence_pointer
                        sequence_pointer += 1
                        continue
                logging.info("Rewinding to command number {}".format(loop_pointer + 2))
                rewindable_sequences.rewind_to(loop_pointer + 1)
                sequence_pointer = loop_pointer + 1
                continue

            # Special case: the 'loop_for' action
            if speaker_name.lower() == "loop_for":
                if len(sequence) != 2:
                    error_and_exit(
                        "Action 'loop_for' requires one parameter (check spaces around the ':' separator)"
                    )
                if loop_start_time is None:
                    loop_start_time = time.time()
                    try:
                        loop_duration = convert_to_seconds(sequence[1])
                    except ValueError:
                        error_and_exit(
                            "Action 'loop_for' requires one parameter (duration >= 0)"
                        )
                    logging.info(
                        "Starting action 'loop_for' for duration {}s".format(
                            loop_duration
                        )
                    )
                else:
                    if time.time() - loop_start_time >= loop_duration:
                        logging.info(
                            "Ending action 'loop_for' after duration {}s".format(
                                loop_duration
                            )
                        )
                        loop_start_time = None
                        continue
                logging.info("Rewinding to command number {}".format(loop_pointer + 2))
                rewindable_sequences.rewind_to(loop_pointer + 1)
                sequence_pointer = loop_pointer
                continue

            # Special case: the 'loop_until' action
            if speaker_name.lower() == "loop_until":
                if len(sequence) != 2:
                    error_and_exit(
                        "Action 'loop_until' requires one parameter (check spaces around the ':' separator)"
                    )
                if loop_start_time is None:
                    loop_start_time = time.time()
                    try:
                        loop_duration = seconds_until(sequence[1])
                    except:
                        error_and_exit(
                            "Action 'loop_until' requires one parameter (stop time)"
                        )
                    logging.info(
                        "Starting action 'loop_until' for duration {}s".format(
                            loop_duration
                        )
                    )
                else:
                    if time.time() - loop_start_time >= loop_duration:
                        logging.info(
                            "Ending action 'loop_until' after duration {}s".format(
                                loop_duration
                            )
                        )
                        loop_start_time = None
                        continue
                logging.info("Rewinding to command number {}".format(loop_pointer + 2))
                rewindable_sequences.rewind_to(loop_pointer + 1)
                sequence_pointer = loop_pointer
                continue

            # Special case: the 'wait' action
            if speaker_name in ["wait", "wait_for"]:
                if len(sequence) != 2:
                    error_and_exit(
                        "Action 'wait' requires 1 parameter (check spaces around the ':' separator)"
                    )
                action = sequence[1].lower()
                try:
                    duration = convert_to_seconds(action)
                except ValueError:
                    error_and_exit(
                        "Action 'wait' requires positive number of hours, seconds or minutes + 'h/m/s', or HH:MM(:SS)"
                    )
                logging.info("Waiting for {}s".format(duration))
                time.sleep(duration)
                continue

            # Special case: the 'wait_until' action
            elif speaker_name in ["wait_until"]:
                if len(sequence) != 2:
                    error_and_exit(
                        "'wait_until' requires 1 parameter (check spaces around the ':' separator)"
                    )
                try:
                    action = sequence[1].lower()
                    duration = seconds_until(action)
                    logging.info("Waiting for {}s".format(duration))
                    time.sleep(duration)
                except ValueError:
                    error_and_exit(
                        "'wait_until' requires parameter: time in 24hr HH:MM(:SS) format"
                    )
                continue

            # General action processing
            if len(sequence) < 2:
                error_and_exit(
                    "At least 2 parameters required in action sequence '{}'".format(
                        sequence
                    )
                )
            action = sequence[1].lower()
            args = sequence[2:]
            speaker = get_speaker(speaker_name, use_local_speaker_list)
            if not speaker:
                error_and_exit("Speaker '{}' not found".format(speaker_name))
            if not process_action(speaker, action, args, use_local_speaker_list):
                error_and_exit("Action '{}' not found".format(action))

        except Exception as e:
            error_and_exit(str(e))
        sequence_pointer += 1

    exit(0)


if __name__ == "__main__":
    main()
