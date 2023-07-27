"""The main entry point into the 'sonos-discover' command."""

import argparse

from soco_cli.check_for_update import print_update_status
from soco_cli.speakers import Speakers
from soco_cli.utils import (
    check_args,
    configure_common_args,
    configure_logging,
    docs,
    error_report,
    logo,
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
    parser.add_argument(
        "--subnets",
        type=str,
        help=(
            "Specify the networks or IP addresses to search, in dotted decimal/CIDR"
            " format"
        ),
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

    # Create the Speakers object
    speaker_list = Speakers()

    if args.print:
        if speaker_list.load():
            speaker_list.print()
            exit(0)
        else:
            error_report("No current speaker data")

    if args.delete_local_speaker_cache:
        try:
            file = speaker_list.remove_save_file()
            print("Removed file: {}".format(file))
            exit(0)
        except Exception:
            error_report("No current speaker data file")

    # Parameter validation for various args
    message = check_args(args)
    if message:
        error_report(message)

    speaker_list._network_threads = args.network_discovery_threads
    speaker_list._network_timeout = args.network_discovery_timeout
    speaker_list._min_netmask = args.min_netmask
    if args.subnets is not None:
        speaker_list.subnets = args.subnets.split(",")

    try:
        speaker_list.discover()
        saved = speaker_list.save()
        speaker_list.print()
        if saved:
            print("Saved speaker data at: {}\n".format(speaker_list.save_pathname))
        else:
            print("No speakers discovered. No cache data saved or overwritten.")
    except Exception as e:
        error_report(str(e))


if __name__ == "__main__":
    # Catch all untrapped exceptions
    try:
        main()
        exit(0)
    except Exception as error:
        error_report(str(error))
        exit(1)
