import os
import argparse
import pprint
from . import speakers


def error_and_exit(msg):
    # Print to stderror
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    os._exit(1)


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
        help="Print the discovery results",
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
        default=3.0,
        help="Network timeout for Sonos device scan (seconds)",
    )
    parser.add_argument(
        "--delete-local-speaker-cache",
        "-d",
        action="store_true",
        default=False,
        help="Delete the local speaker cache, if it exists",
    )

    # Parse the command line
    args = parser.parse_args()

    # Parameter validation
    if not 1 <= args.network_discovery_threads <= 1024:
        print(
            "Error: value of 'threads' parameter should be an integer between 1 and 1024"
        )
        exit(1)
    if not 0 <= args.network_discovery_timeout <= 60:
        print(
            "Error: value of 'network_timeout' parameter should be a float between 0 and 60"
        )
        exit(1)

    speaker_list = speakers.Speakers(
        network_threads=args.network_discovery_threads,
        network_timeout=args.network_discovery_timeout,
    )

    try:
        if args.delete_local_speaker_cache:
            speaker_list.remove_save_file()
            exit(0)
        speaker_list.discover()
        speaker_list.save()
    except Exception as e:
        error_and_exit(str(e))

    if args.print:
        households = {}
        for device in speaker_list.speakers:
            if device.household_id not in households:
                households[device.household_id] = []
            households[device.household_id].append(
                (
                    device.speaker_name,
                    device.ip_address,
                    # device.is_coordinator,
                    # device.is_visible,
                )
            )

        print("{} Sonos Household(s) found: ".format(len(households)))
        for household in households:
            print("  {}".format(household))
        print()

        pp = pprint.PrettyPrinter(width=100)
        pp.pprint(households)


if __name__ == "__main__":
    main()
