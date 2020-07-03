#!/usr/bin/env python3
import soco
import argparse
import os
import sys
import ipaddress
import pprint
import pickle
from soco_cli import sonos_discover


class SpeakerList:
    """This class handles a cache of speaker information, stored as
    a pickle file under the user's home directory"""

    def __init__(self):
        self.config_path = os.path.expanduser("~") + "/.soco-cli"
        if not os.path.exists(self.config_path):
            os.mkdir(self.config_path)
        self.pickle_file = self.config_path + "/speakers.pickle"
        self.speakers = None

    def save(self):
        if self.speakers:
            pickle.dump(self.speakers, open(self.pickle_file, "wb"))
            return True
        else:
            return False

    def load(self):
        if os.path.exists(self.pickle_file):
            try:
                self.speakers = pickle.load(open(self.pickle_file, "rb"))
            except:
                return False
            return True
        else:
            return False

    def refresh(self):
        self.speakers = sonos_discover.list_sonos_devices(socket_timeout=5)


def error_and_exit(msg):
    # Print to stderror
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    os._exit(1)


def is_ipv4_address(speaker_name):
    try:
        ipaddress.IPv4Network(speaker_name)
        return True
    except ValueError:
        return False


def get_speaker(
    speaker_name,
    use_local_speaker_list=False,
    refresh_local_speaker_list=False,
    require_coordinator=True,
):
    try:
        if is_ipv4_address(speaker_name):
            return soco.SoCo(speaker_name)
        if not use_local_speaker_list:
            # Use standard SoCo lookup
            speaker = soco.discovery.by_name(speaker_name)
            if speaker:
                return speaker
            else:
                error_and_exit("Speaker '{}' not found.".format(speaker_name))
        else:
            # Use local discovery and cached speaker list if it exists
            speaker_list = SpeakerList()
            if not speaker_list.load() or refresh_local_speaker_list:
                speaker_list.refresh()
                speaker_list.save()
            for speaker in speaker_list.speakers:
                if speaker.speaker_name.lower() == speaker_name.lower():
                    if require_coordinator:
                        if speaker.is_coordinator:
                            return soco.SoCo(speaker.ip_address)
                    else:
                        return soco.SoCo(speaker.ip_address)
            error_and_exit("Speaker '{}' not found.".format(speaker_name))
    except Exception as e:
        error_and_exit("Exception: {}".format(str(e)))


def print_speaker_info(speaker):
    info = speaker.get_speaker_info()
    model = info["model_name"].lower()
    if not ("boost" in model or "bridge" in model):
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
        # Loose match
        if favourite.lower() in f.title.lower():
            uri = f.get_uri()
            metadata = f.resource_meta_data
            # play_uri works for some favourites
            try:
                speaker.play_uri(uri=uri, meta=metadata)
                return
            except Exception as e:
                # error_and_exit(str(e))
                e1 = e
                pass
            # Other favourites have to be added to the queue, then played
            try:
                speaker.clear_queue()
                index = speaker.add_to_queue(f)
                speaker.play_from_queue(index=0, start=True)
                return
            except Exception as e2:
                error_and_exit("{}, {}".format(str(e1), str(e2)))
                return
    error_and_exit("Favourite '{}' not found".format(favourite))


def pause_all(speaker):
    zones = speaker.all_zones
    for zone in zones:
        if zone.is_visible:
            try:
                zone.pause()
            except:
                # Ignore errors here; don't want to halt on
                # a failed pause (e.g., if speaker isn't playing)
                pass


def main():
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
        "--use-local-speaker-list",
        "-l",
        action="store_true",
        default=False,
        help="Use the local speaker list instead of SoCo discovery",
    )
    parser.add_argument(
        "--refresh-local-speaker_list",
        "-r",
        action="store_true",
        default=False,
        help="Refresh the local speaker list",
    )

    pp = pprint.PrettyPrinter(width=100)

    # Parse the command line
    args = parser.parse_args()

    # Process the actions
    # Wrap everything in a try/except to catch all SoCo (etc.) errors
    # ToDo: improve so there's a single action pattern and a single function to interpret it
    try:
        speaker = get_speaker(
            args.speaker, args.use_local_speaker_list, args.refresh_local_speaker_list
        )
        if not speaker:
            error_and_exit("Speaker not found")
        np = len(args.parameters)
        action = args.action.lower()
        # Mute ######################################################
        if action == "mute":
            if np == 0:
                state = "on" if speaker.mute else "off"
                print(state)
            elif np == 1:
                mute = (args.parameters[0]).lower()
                if mute == "on":
                    speaker.mute = True
                elif mute == "off":
                    speaker.mute = False
                else:
                    error_and_exit("Action 'mute' takes parameter 'on' or 'off'")
            else:
                error_and_exit("Action 'mute' requires 0 or 1 parameter(s)")
        elif action == "group_mute":
            if np == 0:
                state = "on" if speaker.group.mute else "off"
                print(state)
            elif np == 1:
                mute = (args.parameters[0]).lower()
                if mute == "on":
                    speaker.group.mute = True
                elif mute == "off":
                    speaker.group.mute = False
                else:
                    error_and_exit("Action 'group_mute' takes parameter 'on' or 'off'")
            else:
                error_and_exit("Action 'group_mute' requires 0 or 1 parameter(s)")
        # Playback controls #########################################
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
        elif action == "pause_all":
            if np == 0:
                pause_all(speaker)
            else:
                error_and_exit("Action 'pause_all' requires no parameters")
        elif action == "play":
            if np == 0:
                speaker.play()
            else:
                error_and_exit("Action 'play' requires no parameters")
        elif action == "next":
            if np == 0:
                speaker.next()
            else:
                error_and_exit("Action 'next' requires no parameters")
        elif action in ["previous", "prev"]:
            if np == 0:
                speaker.previous()
            else:
                error_and_exit("Action 'previous' requires no parameters")
        elif action == "seek":
            if np == 1:
                speaker.seek(args.parameters[0])
            else:
                error_and_exit(
                    "Action 'seek' requires 1 parameter (seek point using HH:MM:SS)"
                )
        elif action in ["play_mode", "mode"]:
            if np == 0:
                print(speaker.play_mode)
            elif np == 1:
                if args.parameters[0].lower() in [
                    "normal",
                    "repeat_all",
                    "repeat_one",
                    "shuffle",
                    "shuffle_no_repeat",
                ]:
                    speaker.play_mode = args.parameters[0]
                else:
                    error_and_exit("Invalid play mode '{}'".format(args.parameters[0]))
            else:
                error_and_exit("Action 'mode/play_mode' requires 0 or 1 parameeter(s)")
        elif action == "playback":
            if np == 0:
                pp.pprint(speaker.get_current_transport_info())
            else:
                error_and_exit("Action 'playback' requires no parameters")
        elif action == "track":
            if np == 0:
                track_info = speaker.get_current_track_info()
                track_info.pop("metadata", None)
                pp.pprint(track_info)
            else:
                error_and_exit("Action 'track' requires no parameters")
        # Line-In ###################################################
        elif action == "line_in":
            if np == 0:
                state = "on" if speaker.is_playing_line_in else "off"
                print(state)
            elif np == 1 or np == 2:
                if args.parameters[0].lower() == "on":
                    if np == 1:
                        speaker.switch_to_line_in()
                    elif np == 2:
                        line_in_source = get_speaker(
                            args.parameters[1], args.use_local_speaker_list
                        )
                        # The speaker lookup above will error out if not found
                        speaker.switch_to_line_in(line_in_source)
                else:
                    error_and_exit("Action 'line_in' first parameter must be 'on'")
            else:
                error_and_exit("Action 'line_in' takes 0, 1, or 2 parameter(s)")
        # Volume ####################################################
        elif action in ["volume", "vol"]:
            if np == 0:
                print(speaker.volume)
            elif np == 1:
                volume = int(args.parameters[0])
                if 0 <= volume <= 100:
                    speaker.volume = volume
                else:
                    error_and_exit("Volume parameter must be from 0 to 100")
            else:
                error_and_exit("Action 'volume' takes 0 or 1 parameter(s)")
        elif action in ["relative_volume", "rel_vol"]:
            if np == 1:
                volume = int(args.parameters[0])
                if -100 <= volume <= 100:
                    speaker.volume += volume
                else:
                    error_and_exit("Relative Volume parameter must be from -100 to 100")
            else:
                error_and_exit("Action 'relative_volume' takes 1 parameter")
        elif action in ["ramp", "ramp_to_volume"]:
            if np == 1:
                volume = int(args.parameters[0])
                if 0 <= volume <= 100:
                    print(speaker.ramp_to_volume(volume))
                else:
                    error_and_exit("Ramp parameter must be from 0 to 100")
            else:
                error_and_exit("Action 'ramp/ramp_to_volume' requires 1 parameter")
        elif action in ["group_volume", "group_vol"]:
            if np == 0:
                print(speaker.group.volume)
            elif np == 1:
                volume = int(args.parameters[0])
                if 0 <= volume <= 100:
                    speaker.group.volume = volume
                else:
                    error_and_exit("Group Volume parameter must be from 0 to 100")
            else:
                error_and_exit("Action 'group_volume' takes 0 or 1 parameter(s)")
        elif action in ["group_relative_volume", "group_rel_vol"]:
            if np == 1:
                volume = int(args.parameters[0])
                if -100 <= volume <= 100:
                    speaker.group.volume += volume
                else:
                    error_and_exit(
                        "Group Relative Volume parameter must be from -100 to 100"
                    )
            else:
                error_and_exit("Action 'group_relative_volume' takes 1 parameter")
        # Bass ######################################################
        elif action == "bass":
            if np == 0:
                print(speaker.bass)
            elif np == 1:
                bass = int(args.parameters[0])
                if -10 <= bass <= 10:
                    speaker.bass = bass
                else:
                    error_and_exit("Bass parameter must be from -10 to 10")
            else:
                error_and_exit("Action 'bass' takes 0 or 1 parameter(s)")
        # Treble ####################################################
        elif action == "treble":
            if np == 0:
                print(speaker.treble)
            elif np == 1:
                treble = int(args.parameters[0])
                if -10 <= treble <= 10:
                    speaker.treble = treble
                else:
                    error_and_exit("Treble parameter must be from -10 to 10")
            else:
                error_and_exit("Action 'treble' takes 0 or 1 parameter(s)")
        # Balance ###################################################
        elif action == "balance":
            if np == 0:
                print(speaker.balance)
            elif np == 2:
                balance = int(args.parameters[0]), int(args.parameters[1])
                if 0 <= balance[0] <= 100 and 0 <= balance[1] <= 100:
                    speaker.balance = balance
                else:
                    error_and_exit(
                        "Balance parameters 'Left Right' must be from 0 to 100"
                    )
            else:
                error_and_exit("Action 'balance' takes 0 or 2 parameters")
        # Play Favourite ############################################
        elif action in ["favourite", "favorite", "fav"]:
            if np != 1:
                error_and_exit("Action 'favourite/favorite/fav' requires 1 parameter")
            else:
                play_sonos_favourite(speaker, args.parameters[0])
        # Play URI ##################################################
        elif action in ["uri", "play_uri"]:
            if not (np == 1 or np == 2):
                error_and_exit("Action 'uri/play_uri' requires 1 or 2 parameter(s)")
            else:
                force_radio = (
                    True if args.parameters[0][:4].lower() == "http" else False
                )
                if np == 2:
                    speaker.play_uri(
                        args.parameters[0],
                        title=args.parameters[1],
                        force_radio=force_radio,
                    )
                else:
                    speaker.play_uri(args.parameters[0], force_radio=force_radio)
        # Sleep Timer ###############################################
        elif action in ["sleep", "sleep_timer"]:
            if np == 0:
                st = speaker.get_sleep_timer()
                if st:
                    print(st)
                else:
                    print(0)
            elif np == 1:
                speaker.set_sleep_timer(int(args.parameters[0]))
            else:
                error_and_exit(
                    "Action 'sleep/sleep_timer' requires 0 or 1 parameters (sleep time in seconds)"
                )
        # Info ######################################################
        elif action == "info":
            print_speaker_info(speaker)
        # Reindex ###################################################
        elif action == "reindex":
            if np == 0:
                speaker.music_library.start_library_update()
            else:
                error_and_exit("Action 'reindex' requires no parameters")
        # Loudness ##################################################
        elif action == "loudness":
            if np == 0:
                state = "on" if speaker.loudness else "off"
                print(state)
            elif np == 1:
                v = (args.parameters[0]).lower()
                if v == "on":
                    speaker.loudness = True
                elif v == "off":
                    speaker.loudness = False
                else:
                    error_and_exit(
                        "Action 'loudness' with a parameter requires 'on' or 'off'"
                    )
            else:
                error_and_exit(
                    "Action 'loudness' requires 0 or 1 parameter ('on' or 'off')"
                )
        # Cross Fade ################################################
        elif action == "cross_fade":
            if np == 0:
                state = "on" if speaker.cross_fade else "off"
                print(state)
            elif np == 1:
                v = (args.parameters[0]).lower()
                if v == "on":
                    speaker.cross_fade = True
                elif v == "off":
                    speaker.cross_fade = False
                else:
                    error_and_exit(
                        "Action 'cross_fade' with a parameter requires 'on' or 'off'"
                    )
            else:
                error_and_exit(
                    "Action 'cross_fade' requires 0 or 1 parameter ('on' or 'off')"
                )
        # Status Light ##############################################
        elif action in ["status_light", "light"]:
            if np == 0:
                state = "on" if speaker.status_light else "off"
                print(state)
            elif np == 1:
                v = (args.parameters[0]).lower()
                if v == "on":
                    speaker.status_light = True
                elif v == "off":
                    speaker.status_light = False
                else:
                    error_and_exit(
                        "Action 'status_light' with a parameter requires 'on' or 'off'"
                    )
            else:
                error_and_exit(
                    "Action 'status_light' requires 0 or 1 parameter ('on' or 'off')"
                )
        # Grouping ##################################################
        elif action == "group":
            if np == 1:
                speaker2 = get_speaker(args.parameters[0], args.use_local_speaker_list)
                speaker.join(speaker2)
            else:
                error_and_exit(
                    "Action 'group' requires 1 parameter (the speaker to group with"
                )
        elif action == "ungroup":
            if np == 0:
                speaker.unjoin()
            else:
                error_and_exit("Action 'ungroup' requires no parameters")
        elif action in ["party", "party_mode"]:
            if np == 0:
                speaker.partymode()
            else:
                error_and_exit("Action 'party/party_mode' takes 0 parameters")
        elif action == "groups":
            if np == 0:
                for group in speaker.all_groups:
                    if group.coordinator.is_visible:
                        print("[{}] : ".format(group.short_label), end="")
                        for member in group.members:
                            print(
                                "{} ({}) ".format(
                                    member.player_name, member.ip_address
                                ),
                                end="",
                            )
                        print()
            else:
                error_and_exit("Action 'groups' requires no parameters")
        # Zones information #########################################
        elif action in [
            "rooms",
            "all_rooms",
            "visible_rooms",
            "zones",
            "all_zones",
            "visible_zones",
        ]:
            if np == 0:
                zones = speaker.all_zones if "all" in action else speaker.visible_zones
                for zone in zones:
                    print("{} ({})".format(zone.player_name, zone.ip_address))
            else:
                error_and_exit("'Room' actions require no parameters")
        # Stereo pairing ############################################
        elif action == "pair":
            if float(soco.__version__) <= 0.19:
                error_and_exit("Pairing operations require SoCo v0.20 or greater")
            if np == 1:
                right_speaker = get_speaker(
                    args.parameters[0], args.use_local_speaker_list
                )
                speaker.create_stereo_pair(right_speaker)
            else:
                error_and_exit(
                    "Action 'pair' requires 1 parameter (the right hand speaker)"
                )
        elif action == "unpair":
            if float(soco.__version__) <= 0.19:
                error_and_exit("Pairing operations require SoCo v0.20 or greater")
            if np == 0:
                speaker.separate_stereo_pair()
            else:
                error_and_exit("Action 'unpair' requires no parameters")
        # Invalid Action ############################################
        else:
            error_and_exit("Action '{}' is not defined.".format(action))
    except Exception as e:
        error_and_exit("Exception: {}".format(str(e)))
    exit(0)


if __name__ == "__main__":
    main()
