#!/usr/bin/env python3
import soco
import argparse
import os  # Use os._exit() to avoid the catch-all 'except'
import ipaddress


# Include only the group coordinator for paired systems
# Use lower case
speakers = {
    "kitchen": "192.168.0.30",
    "rear reception": "192.168.0.32",
    "front reception": "192.168.0.35",
    "bedroom": "192.168.0.36",
    "bedroom 2": "192.168.0.38",
    "move": "192.168.0.41",
    "study": "192.168.0.39",
    "test": "192.168.0.42",
}


# Directory for locally-defined streams
# Use lower case
streams = {
    "bbc world service": "http://a.files.bbci.co.uk/media/live/manifesto/audio/simulcast/hls/nonuk/sbr_low/llnw/bbc_world_service.m3u8",
#   "radio paradise": "https://stream.radioparadise.com/flac)",
}


def error_and_exit(msg):
    print("Error:", msg)
    os._exit(1)


def is_ip_address(speaker_name):
    try:
        ipaddress.IPv4Network(speaker_name)
        return True
    except ValueError:
        return False


def get_speaker(speaker_name):
    if is_ip_address(speaker_name):
        speaker_ip = speaker_name
    else:
        speaker_ip = speakers.get(speaker_name.lower())
        if not speaker_ip:
            error_and_exit("Speaker '{}' not recognised.".format(speaker_name))
    return soco.SoCo(speaker_ip)


def print_speaker_info(speaker):
    info = speaker.get_speaker_info()
    info["volume"] = speaker.volume
    info["mute"] = speaker.mute
    info["state"] = speaker.get_current_transport_info()["current_transport_state"]
    info["title"] = speaker.get_current_track_info()["title"]
    info["player_name"] = speaker.player_name
    info["ip_address"] = speaker.ip_address
    if len(speaker.group.members) == 1:
        grouped = "No"
    else:
        grouped = "Yes"
    info["grouped_or_paired"] = grouped
    for item in sorted(info):
        print("  {} = {}".format(item, info[item]))


def play_sonos_favourite(speaker, favourite):
    fs = speaker.music_library.get_sonos_favorites()
    for f in fs:
        if favourite in f.title:
            reference = f.reference
            resource = reference.resources[0]
            uri = resource.uri
            speaker.play_uri(uri)
    exit(0)


if __name__ == "__main__":
    # Create the argument parser
    parser = argparse.ArgumentParser(
        prog="sonos-cli",
        usage="%(prog)s speaker action",
        description="Control Sonos speakers",
    )
    # Set up arguments
    parser.add_argument("speaker", help="The name or IP address of the speaker (Zone/Room)")
    parser.add_argument("action", help="The action to perform")
    parser.add_argument(
        "parameters", nargs="*", help="Parameter(s), if required by the action"
    )

    # parser.add_argument("Parameters", action="store", nargs=*)
    # parser.add_argument("--mute", "-m", action="store_true", help="Mute the speaker")
    # parser.add_argument("--volume", "-V", type=int, action="store", help="Set the volume of the speaker")
    # parser.add_argument("--favourite", "-F", type=str, action="store", help="Play a Sonos favourite")

    # Parse the command line
    args = parser.parse_args()

    # Process the actions
    # Wrap everything in a try/except to catch all SoCo (etc.) errors
    try:
        speaker = get_speaker(args.speaker)
        np = len(args.parameters)
        action = args.action.lower()
        # Mute, Unmute ##############################################
        if action == "mute":
            speaker.mute = True
        elif action == "unmute":
            speaker.mute = False
        # Play, Pause, Stop #########################################
        elif action == "stop":
            speaker.stop()
        elif action == "pause":
            speaker.pause()
        elif action == "play":
            speaker.play()
        # Volume ####################################################
        elif action == "volume":
            if np == 0:
                print("Volume:", speaker.volume)
            elif np == 1:
                volume = int(args.parameters[0])
                if 0 <= volume <= 100:
                    speaker.volume = volume
                else:
                    error_and_exit("Volume parameter must be from 0 to 100")
            else:
                error_and_exit("Volume takes 0 or 1 parameter")
        # Play Favourite ############################################
        elif action == "favourite" or action == "favorite":
            if np != 1:
                error_and_exit("Playing a favourite requires one parameter")
            else:
                play_sonos_favourite(speaker, args.parameters[0])
        # Play URI ##################################################
        elif action == "uri" or action == "play_uri":
            if np != 1:
                error_and_exit("Playing URI requires one parameter")
            else:
                speaker.play_uri(args.parameters[0])
        # Play locally defined stream ###############################
        elif action == "stream" or action == "play_stream":
            if np != 1:
                error_and_exit("Playing URI requires one parameter")
            else:
                stream = streams.get(args.parameters[0].lower())
                if stream:
                    speaker.play_uri(stream)
                else:
                    error_and_exit("Stream not found")
        # Sleep Timer ###############################################
        elif action == "sleep" or action == "sleep_timer":
            if np == 0:
                st = speaker.get_sleep_timer()
                if st:
                    print("Sleep timer:", st, "seconds remaining")
                else:
                    print("No sleep timer set")
            elif np == 1:
                speaker.set_sleep_timer(int(args.parameters[0]))
            else:
                error_and_exit("Too many parameters")
        # Info ######################################################
        elif action == "info":
            print_speaker_info(speaker)
        # Reindex ###################################################
        elif action == "reindex":
            if np == 0:
                speaker.music_library.start_library_update()
            else:
                error_and_exit("No parameters required for the 'reindex' action")
        # Grouping and pairing ######################################
        elif action == "group" or action == "group_with":
            if np == 1:
                speaker2 = get_speaker(args.parameters[0])
                speaker.join(speaker2)
            else:
                error_and_exit("One parameter (the speaker to group with) required")
        elif action == "ungroup":
            if np == 0:
                speaker.unjoin()
            else:
                error_and_exit("No parameters required for 'ungroup' action")
        # Stereo pairing is pending release of SoCo 0.20
        # elif action == "pair":
        #     if np == 1:
        #         right_speaker = get_speaker(args.parameters[0])
        #         speaker.create_stereo_pair(right_speaker)
        #     else:
        #         error_and_exit("One parameter (the right hand speaker) required")
        # elif action == "unpair":
        #     if np == 0:
        #         speaker.separate_stereo_pair()
        #     else:
        #         error_and_exit("No parameters required for 'unpair' action")
        # Invalid Action ############################################
        else:
            error_and_exit("Action '{}' is not defined.".format(action))
    except BaseException as e:
        error_and_exit("Exception: {}".format(str(e)))
    exit(0)
