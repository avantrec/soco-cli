"""Prints a table of information about the Sonos system."""

import datetime

import tabulate  # type: ignore

# Collect speaker information from each speaker in turn
headers = [
    "Zone Name",
    "IP Address",
    "Visible",
    "CoOrd",
    "CoOrd IP",
    "Vol.",
    "Mute",
    "State",
    "Model Name",
    "Model No.",
    "HW Version",
    "SW Version",
]


def print_speaker_table(device):
    speakers = []
    models = set()
    errors = []
    exceptions = []

    def add_err_and_exc(err_player_name, err_ip_address, exc):
        exceptions.append(exc)
        errors.append(
            ("Could not get speaker_info for {}: {}").format(
                err_player_name, err_ip_address
            )
        )

    for sco in device.all_zones:
        # Load the speaker info
        try:
            sco.get_speaker_info()
        except BaseException as e:
            add_err_and_exc(sco.player_name, sco.ip_address, e)
            continue

        # Boost and Bridge don't support some attributes
        if sco.is_bridge:
            not_applicable = "n/a"
            volume = not_applicable
            mute = not_applicable
            state = not_applicable
        else:
            volume = sco.volume
            mute = "On" if sco.mute else "Off"
            # Bonded speakers return errors for transport and track info.
            # Wrap in an exception, and ignore.
            try:
                state = sco.get_current_transport_info()["current_transport_state"]
            except BaseException as e:
                # If we're here, assume the speakers are bonded
                # in a Home Theatre configuration
                state = "Bonded"

        # Find the coordinator IP
        coord = sco.group.coordinator
        if sco is coord:
            coord_ip = ""
        else:
            coord_ip = coord.ip_address
            # Overwrite the 'state'
            if state != "Bonded":
                state = sco.group.coordinator.get_current_transport_info()[
                    "current_transport_state"
                ]

        # Set up the information for the speaker
        speaker = [
            sco.player_name,
            sco.ip_address,
            "Yes" if sco.is_visible else "No",
            "Yes" if sco.is_coordinator else "No",
            coord_ip,
            volume,
            mute,
            state,
            sco.speaker_info["model_name"].replace("Sonos ", ""),
            sco.speaker_info["model_number"],
            sco.speaker_info["hardware_version"],
            sco.speaker_info["software_version"]
            + " ("
            + sco.speaker_info["display_version"]
            + ")",
        ]
        speakers.append(speaker)
        models.add(sco.speaker_info["model_number"])

    # Print the date and time
    print()
    print(
        "Report generated on:",
        datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC%z (%A)"),
    )

    # Print the speaker information table in a nice format
    print()
    print(tabulate.tabulate(sorted(speakers), headers, numalign="center"))

    # Print the list of unique model numbers
    print("\nSonos model numbers present:", end="")
    for index, model in enumerate(sorted(models)):
        print(" " + model, end="")
        if index != len(models) - 1:
            print(",", end="")
        else:
            print(".", end="")
    print(
        "\nDevice counts: {} total Sonos device(s), {} unique model(s).".format(
            len(speakers), len(models)
        )
    )
    print()

    # List any speakers that couldn't be inspected, along with the
    # relevant exception
    if len(errors) != 0:
        for err, exc in zip(errors, exceptions):
            print(err)
            print("Exception: {}".format(exc))
        print()
        return False
    return True
