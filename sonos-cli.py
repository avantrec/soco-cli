import soco
import argparse


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


def get_speaker(speaker_name):
    speaker_ip = speaker_table.get(speaker_name.lower())
    if not speaker_ip:
        print("Error: speaker name '{}' not recognised.".format(speaker_name))
        exit(1)
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
        if action == "mute":
            speaker.mute = True
        elif action == "unmute":
            speaker.mute = False
        elif action == "stop":
            speaker.stop()
        elif action == "pause":
            try:
                speaker.pause()
            except:
                pass
        elif action == "play":
            speaker.play()
        elif action == "volume":
            if np == 0:
                print(speaker.volume)
            elif np == 1:
                volume = int(args.parameters[0])
                if 0 <= volume <= 100:
                    speaker.volume = volume
                else:
                    print("Error: Volume parameter must be from 0 to 100")
                    exit(1)
            else:
                print("Error: Too many parameters")
                exit(1)
        elif action == "favourite" or action == "favorite":
            if np != 1:
                print("Error: Playing favourite requires one parameter")
                exit(1)
            else:
                play_sonos_favourite(speaker, args.parameters[0])
        elif action == "uri" or action == "play_uri":
            if np != 1:
                print("Error: Playing URI requires one parameter")
                exit(1)
            else:
                print(args.parameters[0])
                speaker.play_uri(args.parameters[0])
        else:
            print("Error: Action '{}' is not defined.".format(action))
            exit(1)
    except:
        print("Error: Exception.")
        exit(1)

    exit(0)