"""The main entry point into the 'sonos-discover' command."""

import argparse

from soco_cli.speakers import Speakers
from soco_cli.utils import (
    check_args,
    configure_common_args,
    configure_logging,
    docs,
    error_and_exit,
    version,
)


def main():
    # Create the argument parser
    parser = argparse.ArgumentParser(
        prog="sonos-discover",
        usage="%(prog)s",
        description="Sonos speaker discovery utility",
    )
    parser.add_argument(
        "--print",
        "-p",
        action="store_true",
        default=False,
        help="Print the contents of the current speaker information file, and exit",
    )
    parser.add_argument(
        "--delete-local-speaker-cache",
        "-d",
        action="store_true",
        default=False,
        help="Delete the local speaker cache, if it exists",
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

    configure_logging(args.log)

    # Create the Speakers object
    speaker_list = Speakers()

    if args.print:
        if speaker_list.load():
            speaker_list.print()
            exit(0)
        else:
            error_and_exit("No current speaker data")

    if args.delete_local_speaker_cache:
        try:
            file = speaker_list.remove_save_file()
            print("Removed file: {}".format(file))
            exit(0)
        except Exception:
            error_and_exit("No current speaker data file")

    # Parameter validation for various args
    message = check_args(args)
    if message:
        error_and_exit(message)

    speaker_list._network_threads = args.network_discovery_threads
    speaker_list._network_timeout = args.network_discovery_timeout
    speaker_list._min_netmask = args.min_netmask

    try:
        speaker_list.discover()
        saved = speaker_list.save()
        speaker_list.print()
        if saved:
            print("Saved speaker data at: {}\n".format(speaker_list.save_pathname))
        else:
            print("No speaker data saved or overwritten")
    except Exception as e:
        error_and_exit(str(e))


if __name__ == "__main__":
    main()
