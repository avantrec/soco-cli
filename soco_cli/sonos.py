#!/usr/bin/env python3
import argparse
import logging
import pprint
import time
from os import environ as env
from shlex import split as shlex_split
from signal import SIGINT, signal

import soco

from .action_processor import list_actions, process_action
from .interactive import interactive_loop
from .speakers import Speakers
from .utils import (
    RewindableList,
    check_args,
    configure_common_args,
    configure_logging,
    convert_to_seconds,
    docs,
    error_and_exit,
    get_speaker,
    logo,
    seconds_until,
    set_interactive,
    set_speaker_list,
    sig_handler,
    version,
)

# Globals
pp = pprint.PrettyPrinter(width=100)


# Speaker name environment variable
ENV_SPKR = "SPKR"
ENV_LOCAL = "USE_LOCAL"


def main():
    # Handle SIGINT
    signal(SIGINT, sig_handler)

    # Create the argument parser
    parser = argparse.ArgumentParser(
        prog="sonos",
        usage="%(prog)s <options> SPEAKER_NAME_OR_IP ACTION <parameters> < : ...>",
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
        "--actions",
        action="store_true",
        default=False,
        help="Print the list of available actions",
    )
    parser.add_argument(
        "--commands",
        action="store_true",
        default=False,
        help="Print the list of available actions",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=False,
        help="Enter interactive mode",
    )
    parser.add_argument(
        "--no-env",
        action="store_true",
        default=False,
        help="Ignore the 'SPKR' environment variable, if set",
    )
    # The rest of the optional args are common
    configure_common_args(parser)

    # Parse the command line
    args = parser.parse_args()

    if args.version:
        version()
        exit(0)

    if args.docs:
        docs()
        exit(0)

    if args.logo:
        logo()
        exit(0)

    if args.actions or args.commands:
        list_actions()
        exit(0)

    if len(args.parameters) == 0 and not args.interactive:
        print("No parameters. Use 'sonos --help' for usage information")
        exit(0)

    message = check_args(args)
    if message:
        error_and_exit(message)

    configure_logging(args.log)

    use_local_speaker_list = args.use_local_speaker_list
    if env.get(ENV_LOCAL) == "TRUE" and not args.no_env:
        use_local_speaker_list = True
    if use_local_speaker_list:
        speaker_list = Speakers(
            network_threads=args.network_discovery_threads,
            network_timeout=args.network_discovery_timeout,
            min_netmask=args.min_netmask,
        )
        if args.refresh_local_speaker_list or not speaker_list.load():
            logging.info("Start speaker discovery")
            speaker_list.discover()
            speaker_list.save()
        set_speaker_list(speaker_list)

    # Is $SPKR set in the environment?
    env_speaker = None
    if not args.no_env:
        logging.info("Ignoring 'SPKR' environment variable")
        env_speaker = env.get(ENV_SPKR)

    if args.interactive:
        speaker_name = None
        if len(args.parameters):
            speaker_name = args.parameters[0]
        interactive_loop(
            speaker_name,
            use_local_speaker_list=use_local_speaker_list,
            no_env=args.no_env,
        )
        exit(0)

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
                    "seek_to",
                    "seek_forward",
                    "sf",
                    "seek_back",
                    "sb",
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

    # There is a notional 'loop' action before the first command sequence
    loop_pointer = -1

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
                loop_duration = 0
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
                loop_duration = 0
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
                duration = 0
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

            # Use the speaker name from the environment?
            if env_speaker:
                logging.info(
                    "Getting speaker name '{}' from the $SPKR environment variable".format(
                        env_speaker
                    )
                )
                sequence.insert(0, env_speaker)
                speaker_name = env_speaker

            # General action processing
            if len(sequence) < 2:
                error_and_exit(
                    "At least 2 parameters required in action sequence '{}'".format(
                        sequence
                    )
                )
            action = sequence[1].lower()
            args = sequence[2:]
            if speaker_name.lower() == "_all_":
                if use_local_speaker_list:
                    speakers = speaker_list.get_all_speakers()
                else:
                    speakers = soco.discovery.any_soco().all_zones
                logging.info(
                    "Performing action '{}' on all visible, coordinator speakers".format(
                        action
                    )
                )
                for speaker in speakers:
                    if speaker.is_visible and speaker.is_coordinator:
                        logging.info(
                            "Performing action '{}' on speaker '{}'".format(
                                action, speaker.player_name
                            )
                        )
                        print(speaker.player_name)
                        if not process_action(
                            speaker, action, args, use_local_speaker_list
                        ):
                            error_and_exit("Action '{}' not found".format(action))
            else:
                speaker = get_speaker(speaker_name, use_local_speaker_list)
                if not speaker:
                    error_and_exit("Speaker '{}' not found".format(speaker_name))
                if not process_action(
                    speaker, action, args, use_local_speaker_list=use_local_speaker_list
                ):
                    error_and_exit("Action '{}' not found".format(action))

        except Exception as e:
            error_and_exit(str(e))
        sequence_pointer += 1

    exit(0)


2

if __name__ == "__main__":
    main()
