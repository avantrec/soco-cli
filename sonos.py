#!/usr/bin/env python3
import soco
import argparse
import os  # Use os._exit() to avoid the catch-all 'except'
import ipaddress
import sonos_discover


# Include only the group coordinator for paired/bonded systems
# Use lower case for case-insensitive mapping
speakers_cache = {
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


def is_ipv4_address(speaker_name):
    try:
        ipaddress.IPv4Network(speaker_name)
        return True
    except ValueError:
        return False


def get_speaker(speaker_name, use_local_database):
    try:
        if is_ipv4_address(speaker_name):
            return soco.SoCo(speaker_name)
        elif use_local_database:
            if speakers_cache:
                speaker_ip = speakers_cache.get(speaker_name.lower())
                if speaker_ip:
                    return soco.SoCo(speaker_ip)
            # No cache or not found in the cache; fall through
            devices = sonos_discover.list_sonos_devices()
            speaker_ip = None
            for device in devices:
                if device[2].lower() == speaker_name.lower():
                    speaker_ip = device[1]
            if not speaker_ip:
                error_and_exit("Speaker '{}' not recognised.".format(speaker_name))
            return soco.SoCo(speaker_ip)
        else:
            return soco.discovery.by_name(speaker_name)
    except BaseException as e:
        error_and_exit("Exception: {}".format(str(e)))


def print_speaker_info(speaker):
    info = speaker.get_speaker_info()
    info["volume"] = speaker.volume
    info["mute"] = speaker.mute
    info["state"] = speaker.get_current_transport_info()["current_transport_state"]
    info["title"] = speaker.get_current_track_info()["title"]
    info["player_name"] = speaker.player_name
    info["ip_address"] = speaker.ip_address
    info["household_id"] = speaker.household_id
    info["status_light"] = speaker.status_light
    info["is_coordinator"] = speaker.is_coordinator
    info["grouped_or_paired"] = False if len(speaker.group.members) == 1 else True
    info["loudness"] = speaker.loudness
    info["treble"] = speaker.treble
    info["bass"] = speaker.bass
    info["is_coordinator"] = speaker.is_coordinator
    if speaker.is_coordinator:
        info["cross_fade"] = speaker.cross_fade
    info["balance"] = speaker.balance
    info["night_mode"] = speaker.night_mode
    info["is_soundbar"] = speaker.is_soundbar
    info["is_playing_line_in"] = speaker.is_playing_line_in
    info["is_visible"] = speaker.is_visible
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
        prog="sonos",
        usage="%(prog)s speaker action",
        description="Command line utility for controlling Sonos speakers",
    )
    # Set up arguments
    parser.add_argument(
        "speaker", help="The name (Sonos Room/Zone) or IP address of the speaker"
    )
    parser.add_argument("action", help="The action to perform")
    # A variable number of arguments depending on the action
    parser.add_argument(
        "parameters", nargs="*", help="Parameter(s), if required by the action"
    )
    # Optional arguments
    parser.add_argument(
        "--use_local_speaker_database",
        "-l",
        action="store_true",
        default=False,
        help="Use the local speaker database instead of SoCo discovery",
    )

    # Parse the command line
    args = parser.parse_args()

    # Process the actions
    # Wrap everything in a try/except to catch all SoCo (etc.) errors
    # ToDo: improve so there's a single action pattern and a single function to interpret it
    try:
        speaker = get_speaker(args.speaker, args.use_local_speaker_database)
        if not speaker:
            error_and_exit("Speaker not found")
        np = len(args.parameters)
        action = args.action.lower()
        # Mute ######################################################
        if action == "mute":
            if np == 0:
                print("Mute:", speaker.mute)
            elif np == 1:
                mute = (args.parameters[0]).lower()
                if mute == "true":
                    speaker.mute = True
                elif mute == "false":
                    speaker.mute = False
                else:
                    error_and_exit("Mute setting takes parameter 'T/true' or 'F/false'")
            else:
                error_and_exit(
                    "Zero or one parameter(s) required for the 'mute' action"
                )
        # Play, Pause, Stop #########################################
        elif action == "stop":
            if np == 0:
                speaker.stop()
            else:
                error_and_exit("Action 'stop' requires no parameters")
        elif action == "pause":
            if np == 0:
                speaker.pause()
            else:
                error_and_exit("Action 'pause' requires no parameters")
        elif action == "play":
            if np == 0:
                speaker.play()
            else:
                error_and_exit("Action 'play' requires no parameters")
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
        # Bass ######################################################
        elif action == "bass":
            if np == 0:
                print("Bass:", speaker.bass)
            elif np == 1:
                bass = int(args.parameters[0])
                if -10 <= bass <= 10:
                    speaker.bass = bass
                else:
                    error_and_exit("Bass parameter must be from -10 to 10")
            else:
                error_and_exit("Bass takes 0 or 1 parameter")
        # Treble ####################################################
        elif action == "treble":
            if np == 0:
                print("Treble:", speaker.treble)
            elif np == 1:
                treble = int(args.parameters[0])
                if -10 <= treble <= 10:
                    speaker.treble = treble
                else:
                    error_and_exit("Treble parameter must be from -10 to 10")
            else:
                error_and_exit("Treble takes 0 or 1 parameter")
        # Balance ###################################################
        elif action == "balance":
            if np == 0:
                print("Balance:", speaker.balance)
            elif np == 2:
                balance = int(args.parameters[0]), int(args.parameters[1])
                if 0 <= balance[0] <= 100 and 0 <= balance[1] <= 100:
                    speaker.balance = balance
                else:
                    error_and_exit("Balance parameters 'Left Right' must be from 0 to 100")
            else:
                error_and_exit("Balance takes 0 or 2 parameters")
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
                error_and_exit(
                    "Action 'sleep' requires one parameter (sleep time in seconds)"
                )
        # Info ######################################################
        elif action == "info":
            print_speaker_info(speaker)
        # Reindex ###################################################
        elif action == "reindex":
            if np == 0:
                speaker.music_library.start_library_update()
            else:
                error_and_exit("No parameters required for the 'reindex' action")
        # Loudness ##################################################
        elif action == "loudness":
            if np == 0:
                print("Loudness:", speaker.loudness)
            elif np == 1:
                v = (args.parameters[0]).lower()
                if v == "true":
                    speaker.loudness = True
                elif v == "false":
                    speaker.loudness = False
                else:
                    error_and_exit(
                        "Loudness setting takes parameter 'T/true' or 'F/false'"
                    )
            else:
                error_and_exit(
                    "Zero or one parameter(s) required for the 'loudness' action"
                )
        # Cross Fade ################################################
        elif action == "cross_fade":
            if np == 0:
                print("Cross Fade:", speaker.cross_fade)
            elif np == 1:
                v = (args.parameters[0]).lower()
                if v == "true":
                    speaker.cross_fade = True
                elif v == "false":
                    speaker.cross_fade = False
                else:
                    error_and_exit(
                        "Cross Fade setting takes parameter 'T/true' or 'F/false'"
                    )
            else:
                error_and_exit(
                    "Zero or one parameter(s) required for the 'cross_fade' action"
                )
        # Grouping and pairing ######################################
        elif action == "group":
            if np == 1:
                speaker2 = get_speaker(
                    args.parameters[0], args.use_local_speaker_database
                )
                speaker.join(speaker2)
            else:
                error_and_exit("One parameter (the speaker to group with) required")
        elif action == "ungroup":
            if np == 0:
                speaker.unjoin()
            else:
                error_and_exit("No parameters required for 'ungroup' action")
        # Stereo pairing (requires SoCo >= 0.20) ####################
        elif action == "pair":
            if float(soco.__version__) <= 0.19:
                error_and_exit("Pairing operations require SoCo v0.20 or greater")
            if np == 1:
                right_speaker = get_speaker(args.parameters[0], args.use_local_speaker_database)
                speaker.create_stereo_pair(right_speaker)
            else:
                error_and_exit("One parameter (the right hand speaker) required")
        elif action == "unpair":
            if float(soco.__version__) <= 0.19:
                error_and_exit("Pairing operations require SoCo v0.20 or greater")
            if np == 0:
                speaker.separate_stereo_pair()
            else:
                error_and_exit("No parameters required for 'unpair' action")
        # Invalid Action ############################################
        else:
            error_and_exit("Action '{}' is not defined.".format(action))
    except Exception as e:
        error_and_exit("Exception: {}".format(str(e)))
    exit(0)
