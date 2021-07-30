"""The main entry point into the 'sonos' command."""

import argparse
import logging
import pprint
import sys
import time
from os import environ as env
from signal import SIGINT, signal

import soco

from soco_cli.action_processor import list_actions
from soco_cli.aliases import AliasManager
from soco_cli.api import get_all_speakers, run_command
from soco_cli.check_for_update import print_update_status
from soco_cli.cmd_parser import CLIParser
from soco_cli.interactive import interactive_loop
from soco_cli.speakers import Speakers
from soco_cli.track_follow import track_follow
from soco_cli.utils import (
    RewindableList,
    check_args,
    configure_common_args,
    configure_logging,
    convert_to_seconds,
    create_speaker_cache,
    docs,
    error_report,
    get_speaker,
    logo,
    seconds_until,
    set_interactive,
    set_speaker_list,
    sig_handler,
    version,
)

from .wait_actions import process_wait

# Globals
pp = pprint.PrettyPrinter(width=100)


# Speaker name environment variable
ENV_SPKR = "SPKR"

# Local speaker cache environment variable
ENV_LOCAL = "USE_LOCAL_SPKR_CACHE"


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
    parser.add_argument(
        "--sk",
        action="store_true",
        default=False,
        help="Enter single keystroke mode in the interactive shell",
    )
    parser.add_argument(
        "--save_aliases",
        type=str,
        help="Save the current shell aliases to the supplied filename and exit",
    )
    parser.add_argument(
        "--load_aliases",
        type=str,
        help="Load shell aliases from the supplied filename and exit (aliases are merged)",
    )
    parser.add_argument(
        "--overwrite_aliases",
        type=str,
        help="Overwrite current shell aliases with those from the supplied filename and exit",
    )
    # The rest of the optional args are common
    configure_common_args(parser)

    # Parse the command line
    args = parser.parse_args()

    configure_logging(args.log)

    if args.version:
        version()
        exit(0)

    if args.docs:
        docs()
        exit(0)

    if args.logo:
        logo()
        exit(0)

    if args.check_for_update:
        print_update_status()
        exit(0)

    if args.actions or args.commands:
        list_actions()
        exit(0)

    if args.save_aliases:
        am = AliasManager()
        am.load_aliases()
        if am.save_aliases_to_file(args.save_aliases):
            print("Saved shell aliases to '{}'".format(args.save_aliases), flush=True)
        else:
            print(
                "Failed to save shell aliases to '{}'".format(args.save_aliases),
                flush=True,
            )
        exit(0)

    if args.load_aliases:
        am = AliasManager()
        am.load_aliases()
        if am.load_aliases_from_file(args.load_aliases):
            print(
                "Loaded and merged shell aliases from '{}'".format(args.load_aliases),
                flush=True,
            )
        else:
            print(
                "Failed to load shell aliases from '{}'".format(args.load_aliases),
                flush=True,
            )
        exit(0)

    if args.overwrite_aliases:
        am = AliasManager()
        if am.load_aliases_from_file(args.overwrite_aliases):
            print(
                "Loaded and saved shell aliases from '{}'".format(
                    args.overwrite_aliases
                ),
                flush=True,
            )
        else:
            print(
                "Failed to load shell aliases from '{}'".format(args.overwrite_aliases),
                flush=True,
            )
        exit(0)

    if len(args.parameters) == 0 and not args.interactive:
        print("No parameters. Use 'sonos --help' for usage information", flush=True)
        exit(0)

    message = check_args(args)
    if message:
        error_report(message)

    use_local_speaker_list = args.use_local_speaker_list
    if env.get(ENV_LOCAL) == "TRUE" and not args.no_env:
        logging.info(
            "Env. var. '{}' set to 'TRUE ... using local speaker list".format(ENV_LOCAL)
        )
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
    else:
        # Create the local speaker cache in the utils module
        create_speaker_cache(
            max_threads=args.network_discovery_threads,
            scan_timeout=args.network_discovery_timeout,
            min_netmask=args.min_netmask,
        )

    # Is $SPKR set in the environment?
    env_speaker = None
    if not args.no_env:
        env_speaker = env.get(ENV_SPKR)
        if env_speaker:
            logging.info("Found 'SPKR' environment variable: '{}'".format(env_speaker))
        else:
            logging.info("No 'SPKR' environment variable set")

    if args.interactive:
        sk = bool(args.sk)
        speaker_name = None
        if len(args.parameters):
            speaker_name = args.parameters[0]
        interactive_loop(
            speaker_name,
            use_local_speaker_list=use_local_speaker_list,
            no_env=args.no_env,
            single_keystroke=sk,
        )
        exit(0)

    cli_parser = CLIParser()
    cli_parser.parse(args.parameters)
    sequences = cli_parser.get_sequences()

    cumulative_exit_code = 0

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
                    error_report("Action 'loop_to_start' takes no parameters")
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
                            error_report(
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
                    error_report(
                        "Action 'loop_for' requires one parameter (check spaces around the ':' separator)"
                    )
                loop_duration = 0
                if loop_start_time is None:
                    loop_start_time = time.time()
                    try:
                        loop_duration = convert_to_seconds(sequence[1])
                    except ValueError:
                        error_report(
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
                    error_report(
                        "Action 'loop_until' requires one parameter (check spaces around the ':' separator)"
                    )
                if loop_start_time is None:
                    loop_start_time = time.time()
                    try:
                        loop_duration = seconds_until(sequence[1])
                    except:
                        error_report(
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

            # Special case: the 'wait' actions
            if speaker_name in ["wait", "wait_for", "wait_until"]:
                process_wait(sequence)
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
                error_report(
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
                    speakers = get_all_speakers(use_scan=True)
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
                        print(speaker.player_name + ": ", end="", flush=True)
                        exit_code, output_msg, error_msg = run_command(
                            speaker,
                            action,
                            *args,
                            use_local_speaker_list=use_local_speaker_list,
                        )
                        if exit_code == 0:
                            if len(output_msg) != 0:
                                print(output_msg, flush=True)
                            else:
                                print("OK", flush=True)
                        elif len(error_msg) != 0:
                            print(error_msg, file=sys.stderr, flush=True)
                        cumulative_exit_code += exit_code
            else:
                speaker = get_speaker(speaker_name, use_local_speaker_list)
                if not speaker:
                    print(
                        "Error: Speaker '{}' not found".format(speaker_name),
                        file=sys.stderr,
                        flush=True,
                    )
                    cumulative_exit_code += 1
                else:
                    # Special case of 'track_follow' action
                    if action in ["track_follow", "tf", "track_follow_compact", "tfc"]:
                        # Does not return
                        compact = action in ["track_follow_compact", "tfc"]
                        track_follow(
                            speaker,
                            use_local_speaker_list=use_local_speaker_list,
                            break_on_pause=False,
                            compact=compact,
                        )
                    # Standard action processing
                    exit_code, output_msg, error_msg = run_command(
                        speaker,
                        action,
                        *args,
                        use_local_speaker_list=use_local_speaker_list,
                    )
                    if exit_code == 0 and len(output_msg) != 0:
                        print(output_msg, flush=True)
                    elif len(error_msg) != 0:
                        print(error_msg, file=sys.stderr, flush=True)
                    cumulative_exit_code += exit_code

        except Exception as e:
            print("Error: ", str(e), flush=True)
            cumulative_exit_code += 1

        sequence_pointer += 1

    exit(cumulative_exit_code)


if __name__ == "__main__":
    # Catch all untrapped exceptions
    try:
        main()
        exit(0)
    except Exception as error:
        error_report(str(error))
        exit(1)
