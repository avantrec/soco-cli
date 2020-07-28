import argparse

from .utils import error_and_exit, configure_logging, version, configure_common_args
from .speakers import Speakers


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

    configure_logging(args.log)

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

    # Parameter validation
    if not 1 <= args.network_discovery_threads <= 1024:
        error_and_exit(
            "Value of 'threads' parameter should be an integer between 1 and 1024"
        )
    speaker_list.network_threads = args.network_discovery_threads

    if not 0 <= args.network_discovery_timeout <= 60:
        error_and_exit(
            "Value of 'network_timeout' parameter should be a float between 0 and 60"
        )
    speaker_list.network_timeout = args.network_discovery_timeout

    try:
        speaker_list.discover()
        speaker_list.save()
        speaker_list.print()
    except Exception as e:
        error_and_exit(str(e))


if __name__ == "__main__":
    main()
