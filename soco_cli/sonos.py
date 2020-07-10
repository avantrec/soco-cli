#!/usr/bin/env python3
import soco
import argparse
import os
import sys
import pprint
import time
from . import speakers
from . import __version__

# Globals
speaker_list = None
pp = pprint.PrettyPrinter(width=100)


def error_and_exit(msg):
    # Print to stderror
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    os._exit(1)


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
    the_fav = None
    # Strict match (case insensitive)
    for f in fs:
        if favourite.lower() == f.title.lower():
            the_fav = f
    # Loose substring match if strict match not available
    if not the_fav:
        for f in fs:
            if favourite.lower() in f.title.lower():
                the_fav = f
    if the_fav:
        # play_uri works for some favourites
        try:
            uri = the_fav.get_uri()
            metadata = the_fav.resource_meta_data
            speaker.play_uri(uri=uri, meta=metadata)
            return  # Success
        except Exception as e:
            e1 = e
            pass
        # Other favourites have to be added to the queue, then played
        try:
            speaker.clear_queue()
            index = speaker.add_to_queue(the_fav)
            speaker.play_from_queue(index=0, start=True)
            return
        except Exception as e2:
            error_and_exit("{}, {}".format(str(e1), str(e2)))
            return
    error_and_exit("Favourite '{}' not found".format(favourite))


def list_favourites(speaker):
    fs = speaker.music_library.get_sonos_favorites()
    favs = []
    for f in fs:
        favs.append(f.title)
    favs.sort()
    index = 0
    for f in favs:
        index += 1
        print("{:3d}: {}".format(index, f))


def list_playlists(speaker):
    ps = speaker.get_sonos_playlists()
    playlists = []
    for p in ps:
        playlists.append(p.title)
    playlists.sort()
    index = 0
    for p in playlists:
        index += 1
        print("{:3d}: {}".format(index, p))


def add_playlist_to_queue(speaker, name):
    playlists = speaker.get_sonos_playlists()
    # Strict match
    for playlist in playlists:
        if name.lower() == playlist.title.lower():
            speaker.add_to_queue(playlist)
            return True
    # Fuzzy match
    for playlist in playlists:
        if name.lower() in playlist.title.lower():
            speaker.add_to_queue(playlist)
            return True
    return False


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


def ungroup_all(speaker):
    zones = speaker.all_zones
    for zone in zones:
        if zone.is_visible:
            try:
                zone.unjoin()
            except:
                # Ignore errors here; don't want to halt on
                # a failed pause (e.g., if speaker isn't playing)
                pass


def get_speaker(name, local=False):
    # Allow the use of an IP address even if 'local' is specified
    if speakers.Speakers.is_ipv4_address(name):
        return soco.SoCo(name)
    if local:
        return speaker_list.find(name)
    else:
        return soco.discovery.by_name(name)


def process_action(speaker, action, args, use_local_speaker_list):
    np = len(args)
    if action == "mute":
        if np == 0:
            state = "on" if speaker.mute else "off"
            print(state)
        elif np == 1:
            mute = (args[0]).lower()
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
            mute = (args[0]).lower()
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
            speaker.seek(args[0])
        else:
            error_and_exit(
                "Action 'seek' requires 1 parameter (seek point using HH:MM:SS)"
            )
    elif action in ["play_mode", "mode"]:
        if np == 0:
            print(speaker.play_mode)
        elif np == 1:
            if args[0].lower() in [
                "normal",
                "repeat_all",
                "repeat_one",
                "shuffle",
                "shuffle_no_repeat",
            ]:
                speaker.play_mode = args[0]
            else:
                error_and_exit("Invalid play mode '{}'".format(args[0]))
        else:
            error_and_exit("Action 'mode/play_mode' requires 0 or 1 parameter(s)")
    elif action in ["playback", "state"]:
        if np == 0:
            print(speaker.get_current_transport_info()["current_transport_state"])
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
            if args[0].lower() == "on":
                if np == 1:
                    speaker.switch_to_line_in()
                elif np == 2:
                    line_in_source = get_speaker(args[1], use_local_speaker_list)
                    # The speaker lookup above will error out if not found
                    speaker.switch_to_line_in(line_in_source)
            else:
                error_and_exit("Action 'line_in' first parameter must be 'on'")
        else:
            error_and_exit("Action 'line_in' takes 0, 1, or 2 parameter(s)")
    # Volume ####################################################
    elif action in ["volume", "vol", "v"]:
        if np == 0:
            print(speaker.volume)
        elif np == 1:
            volume = int(args[0])
            if 0 <= volume <= 100:
                speaker.volume = volume
            else:
                error_and_exit("Volume parameter must be from 0 to 100")
        else:
            error_and_exit("Action 'volume' takes 0 or 1 parameter(s)")
    elif action in ["relative_volume", "rel_vol", "relvol", "rv"]:
        if np == 1:
            volume = int(args[0])
            if -100 <= volume <= 100:
                speaker.volume += volume
            else:
                error_and_exit("Relative Volume parameter must be from -100 to 100")
        else:
            error_and_exit("Action 'relative_volume' takes 1 parameter")
    elif action in ["ramp", "ramp_to_volume"]:
        if np == 1:
            volume = int(args[0])
            if 0 <= volume <= 100:
                print(speaker.ramp_to_volume(volume))
            else:
                error_and_exit("Ramp parameter must be from 0 to 100")
        else:
            error_and_exit("Action 'ramp/ramp_to_volume' requires 1 parameter")
    elif action in ["group_volume", "group_vol", "gv"]:
        if np == 0:
            print(speaker.group.volume)
        elif np == 1:
            volume = int(args[0])
            if 0 <= volume <= 100:
                speaker.group.volume = volume
            else:
                error_and_exit("Group Volume parameter must be from 0 to 100")
        else:
            error_and_exit("Action 'group_volume' takes 0 or 1 parameter(s)")
    elif action in ["group_relative_volume", "group_rel_vol", "grv"]:
        if np == 1:
            volume = int(args[0])
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
            bass = int(args[0])
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
            treble = int(args[0])
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
            balance = int(args[0]), int(args[1])
            if 0 <= balance[0] <= 100 and 0 <= balance[1] <= 100:
                speaker.balance = balance
            else:
                error_and_exit("Balance parameters 'Left Right' must be from 0 to 100")
        else:
            error_and_exit("Action 'balance' takes 0 or 2 parameters")
    # Play Favourite ############################################
    elif action in ["favourite", "favorite", "fav", "pf", "play_fav"]:
        if np != 1:
            error_and_exit("Action 'favourite/favorite/fav' requires 1 parameter")
        else:
            play_sonos_favourite(speaker, args[0])
    elif action in ["list_favs", "list_favorites", "list_favourites", "lf"]:
        if np == 0:
            list_favourites(speaker)
        else:
            error_and_exit("Action 'list_favs' requires no parameters")
    # Play URI ##################################################
    elif action in ["uri", "play_uri"]:
        if not (np == 1 or np == 2):
            error_and_exit("Action 'play_uri' requires 1 or 2 parameter(s)")
        else:
            force_radio = True if args[0][:4].lower() == "http" else False
            if np == 2:
                speaker.play_uri(
                    args[0], title=args[1], force_radio=force_radio,
                )
            else:
                speaker.play_uri(args[0], force_radio=force_radio)
    # Sleep Timer ###############################################
    elif action in ["sleep", "sleep_timer"]:
        if np == 0:
            st = speaker.get_sleep_timer()
            if st:
                print(st)
            else:
                print(0)
        elif np == 1:
            speaker.set_sleep_timer(int(args[0]))
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
            v = (args[0]).lower()
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
            v = (args[0]).lower()
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
            v = (args[0]).lower()
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
    elif action in ["group", "g"]:
        if np == 1:
            speaker2 = get_speaker(args[0], use_local_speaker_list)
            speaker.join(speaker2)
        else:
            error_and_exit(
                "Action 'group' requires 1 parameter (the speaker to group with"
            )
    elif action in ["ungroup", "u"]:
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
                            "{} ({}) ".format(member.player_name, member.ip_address),
                            end="",
                        )
                    print()
        else:
            error_and_exit("Action 'groups' requires no parameters")
    elif action in ["ungroup_all"]:
        if np == 0:
            ungroup_all(speaker)
        else:
            error_and_exit("Action 'ungroup_all' requires no parameters")
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
            right_speaker = get_speaker(args[0], use_local_speaker_list)
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
    # Version ###################################################
    elif action == "version":
        print("soco-cli version: {}".format(__version__))
        print("soco version:     {}".format(soco.__version__))
    # Queues ####################################################
    elif action in ["list_queue", "lq", "queue", "q"]:
        if np == 0:
            queue = speaker.get_queue()
            for i in range(len(queue)):
                try:
                    artist = queue[i].creator
                except:
                    artist = ""
                try:
                    album = queue[i].album
                except:
                    album = ""
                try:
                    title = queue[i].title
                except:
                    title = ""
                print(
                    "{:3d}: Artist: {} | Album: {} | Title: {}".format(
                        i + 1, artist, album, title
                    )
                )
        else:
            error_and_exit("Action 'list_queue' requires no parameters")
    elif action in ["play_from_queue", "pfq", "pq"]:
        if np == 1:
            index = int(args[0])
            speaker.play_from_queue(index - 1)
        else:
            error_and_exit("Action 'play_from_queue' requires 1 (integer) parameter")
    elif action in ["remove_from_queue", "rq"]:
        if np == 1:
            index = int(args[0])
            speaker.remove_from_queue(index - 1)
        else:
            error_and_exit("Action 'remove_from_queue' requires 1 (integer) parameter")
    elif action in ["clear_queue", "cq"]:
        if np == 0:
            speaker.clear_queue()
        else:
            error_and_exit("Action 'clear_queue' requires no parameters")
    elif action in ["play_from_queue", "play_queue", "pfq", "pq"]:
        if np == 1:
            index = int(args[0])
            if 1 <= index <= speaker.queue_size:
                speaker.play_from_queue(index - 1)
            else:
                error_and_exit("Queue index '{}' is out of range".format(index))
        else:
            error_and_exit("Action 'play_from_queue' takes 1 parameter")
    # Night / Dialogue Modes ####################################
    elif action in ["night_mode", "night"]:
        if np == 0:
            state = "on" if speaker.night_mode else "off"
            print(state)
        elif np == 1:
            v = (args[0]).lower()
            if v == "on":
                speaker.night_mode = True
            elif v == "off":
                speaker.night_mode = False
            else:
                error_and_exit(
                    "Action 'night_mode' with a parameter requires 'on' or 'off'"
                )
        else:
            error_and_exit(
                "Action 'night_mode' requires 0 or 1 parameter ('on' or 'off')"
            )
    elif action in ["dialogue_mode", "dialog_mode", "dialogue", "dialog"]:
        if np == 0:
            state = "on" if speaker.dialog_mode else "off"
            print(state)
        elif np == 1:
            v = (args[0]).lower()
            if v == "on":
                speaker.dialog_mode = True
            elif v == "off":
                speaker.dialog_mode = False
            else:
                error_and_exit(
                    "Action 'dialog_mode' with a parameter requires 'on' or 'off'"
                )
        else:
            error_and_exit(
                "Action 'dialog_mode' requires 0 or 1 parameter ('on' or 'off')"
            )
    # Playlists #################################################
    elif action in ["list_playlists", "playlists", "lp"]:
        if np == 0:
            list_playlists(speaker)
        else:
            error_and_exit("Action 'list_playlists' requires no parameters")
    elif action in ["add_playlist_to_queue", "add_pl_to_queue", "apq"]:
        if np == 1:
            name = args[0]
            if not add_playlist_to_queue(speaker, name):
                error_and_exit("Playlist not found")
        else:
            error_and_exit(
                "Action 'add_playlist_to_queue' requires one (integer) parameter"
            )
    # Invalid Action ############################################
    else:
        error_and_exit("Action '{}' is not defined.".format(action))


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
        "--refresh-local-speaker-list",
        "-r",
        action="store_true",
        default=False,
        help="Refresh the local speaker list",
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

    # Parse the command line
    args = parser.parse_args()

    use_local_speaker_list = args.use_local_speaker_list
    if use_local_speaker_list:
        global speaker_list
        speaker_list = speakers.Speakers(
            network_threads=args.network_discovery_threads,
            network_timeout=args.network_discovery_timeout,
        )
        if args.refresh_local_speaker_list or not speaker_list.load():
            speaker_list.discover()
            speaker_list.save()

    # Break up the command line into command sequences, observing the separator.
    # Introduce an internal separator to split up arguments within a command.
    # I'm sure there must be a neater way of doing this, but it works for now.
    command_line_separator = ":"
    internal_separator = "%%%"
    args.parameters.insert(0, args.action)
    args.parameters.insert(0, args.speaker)
    all_args = ""
    previous_arg = ""
    for arg in args.parameters:
        if len(arg) > 1 and (
            arg.endswith(command_line_separator)
            or arg.startswith(command_line_separator)
        ):
            error_and_exit("Spaces are required each side of the ':' command separator")
        # Suppress internal separator either side of a command line separator
        if (
            arg == command_line_separator
            or previous_arg == command_line_separator
            or previous_arg == ""
        ):
            all_args = "{}{}".format(all_args, arg)
        else:
            all_args = "{}{}{}".format(all_args, internal_separator, arg)
        previous_arg = arg
    commands = all_args.split(sep=command_line_separator)

    # Loop through processing command sequences
    for command in commands:
        speaker = None
        elements = command.split(sep=internal_separator)
        speaker_name = elements[0]
        action = elements[1].lower()
        # Special case of a "wait" command
        # We're assuming there aren't any speakers called this!
        if speaker_name in ["wait", "w", "sleep"]:
            time.sleep(int(action))
            continue
        args = elements[2:]
        try:
            if action not in ["version"]:
                # Some actions don't require a valid speaker
                speaker = get_speaker(speaker_name, use_local_speaker_list)
                if not speaker:
                    error_and_exit("Speaker '{}' not found".format(speaker_name))
            process_action(speaker, action, args, use_local_speaker_list)
        except Exception as e:
            error_and_exit("Exception: {}".format(str(e)))
    exit(0)


if __name__ == "__main__":
    main()
