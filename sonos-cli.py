import soco
import argparse
from os import _exit  # Use os._exit() to avoid the catch-all 'except'
import pprint


# Use lower case
speaker_table = {
    "kitchen": "192.168.0.30",
    "rear reception": "192.168.0.33",
    "front reception": "192.168.0.35",
    "bedroom": "192.168.0.36",
    "bedroom 2": "192.168.0.38",
    "move": "192.168.0.41",
    "study": "192.168.0.39",
    "test": "192.168.0.42",
}


def error_and_exit(msg):
    print("Error:", msg)
    _exit(1)


def get_speaker(speaker_name):
    speaker_ip = speaker_table.get(speaker_name.lower())
    if not speaker_ip:
        print("Error: speaker name '{}' not recognised.".format(speaker_name))
        _exit(1)
    return soco.SoCo(speaker_ip)


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
    parser.add_argument("speaker", help="The name of the speaker")
    parser.add_argument("action", help="The action to perform")
    parser.add_argument(
        "parameters", nargs="*", help="Parameter(s) required by the action"
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
            try:
                speaker.pause()
            except:
                pass
        elif action == "play":
            speaker.play()
        # Volume ####################################################
        elif action == "volume":
            if np == 0:
                print("Volume is", speaker.volume)
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
                error_and_exit("Playing favourite requires one parameter")
            else:
                play_sonos_favourite(speaker, args.parameters[0])
        # Play URI ##################################################
        elif action == "uri" or action == "play_uri":
            if np != 1:
                error_and_exit("Playing URI requires one parameter")
            else:
                print(args.parameters[0])
                speaker.play_uri(args.parameters[0])
        # Sleep Timer ###############################################
        elif action == "sleep" or action == "sleep_timer":
            if np == 0:
                st = speaker.get_sleep_timer()
                if st:
                    print(st, "seconds remaining")
                else:
                    print("No sleep timer set")
            elif np == 1:
                speaker.set_sleep_timer(int(args.parameters[0]))
            else:
                error_and_exit("Too many parameters")
        # Info ######################################################
        elif action == "info":
            pp = pprint.PrettyPrinter(2)
            info = speaker.get_speaker_info()
            pp.pprint(info)
        # Grouping ##################################################
        elif action == "group":
            if np ==1:
                speaker2 = get_speaker(args.parameters[0])
                speaker.join(speaker2)
            else:
                error_and_exit("One parameter (the speaker to group with) required")
        elif action == "ungroup":
            speaker.unjoin()
        # Invalid Action ############################################
        else:
            error_and_exit("Action '{}' is not defined.".format(action))
    except:
        error_and_exit("Exception.")

    exit(0)
