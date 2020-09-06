import logging
import soco
import soco.alarms
import pprint
import tabulate
import time
from collections import namedtuple
from queue import Empty
from random import randint
from distutils.version import StrictVersion

from .speaker_info import print_speaker_table
from .utils import (
    error_and_exit,
    parameter_type_error,
    parameter_number_error,
    zero_parameters,
    one_parameter,
    zero_or_one_parameter,
    one_or_two_parameters,
    two_parameters,
    one_or_more_parameters,
    seconds_until,
    convert_true_false,
    convert_to_seconds,
    set_sigterm,
    get_speaker,
)


pp = pprint.PrettyPrinter(width=120)
sonos_max_items = 66000


def get_playlist(speaker, name):
    """Returns the playlist object with 'name' otherwise None"""
    playlists = speaker.get_sonos_playlists(complete_result=True)
    # Strict match
    for playlist in playlists:
        if name == playlist.title:
            logging.info(
                "Found playlist '{}' using strict match".format(playlist.title)
            )
            return playlist
    # Fuzzy match
    name = name.lower()
    for playlist in playlists:
        if name in playlist.title.lower():
            logging.info("Found playlist '{}' using fuzzy match".format(playlist.title))
            return playlist
    return None


def print_list_header(prefix, name):
    spacer = "  "
    title = "{} {}".format(prefix, name)
    underline = "=" * (len(title))
    print(spacer + title)
    print(spacer + underline)


def print_tracks(tracks, single_track=False, track_number=None):
    if single_track:
        item_number = track_number
    else:
        item_number = 1
    for track in tracks:
        try:
            artist = track.creator
        except:
            artist = ""
        try:
            album = track.album
        except:
            album = ""
        try:
            title = track.title
        except:
            title = ""
        print(
            "{:7d}: Artist: {} | Album: {} | Title: {}".format(
                item_number, artist, album, title
            )
        )
        item_number += 1
    return True


def print_albums(albums, omit_first=False):
    item_number = 1
    for album in albums:
        try:
            artist = album.creator
        except:
            artist = ""
        try:
            title = album.title
        except:
            title = ""
        if item_number == 1 and omit_first:
            omit_first = False
        else:
            print("{:7d}: Album: {} | Artist: {}".format(item_number, title, artist))
            item_number += 1
    return True


def print_artists(artists):
    item_number = 1
    for artist in artists:
        artist_name = artist.title
        print("{:7d}: {}".format(item_number, artist_name))
        item_number += 1
    return True


# Action processing functions
@zero_or_one_parameter
def on_off_action(speaker, action, args, soco_function, use_local_speaker_list):
    """Method to deal with actions that have 'on|off semantics"""
    if action == "group_mute":
        speaker = speaker.group
        soco_function = "mute"
    np = len(args)
    if np == 0:
        state = "on" if getattr(speaker, soco_function) else "off"
        print(state)
    elif np == 1:
        arg = args[0].lower()
        if arg == "on":
            setattr(speaker, soco_function, True)
        elif arg == "off":
            setattr(speaker, soco_function, False)
        else:
            parameter_type_error(action, "on|off")
    return True


@zero_parameters
def no_args_no_output(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function == "separate_stereo_pair" and StrictVersion(
        soco.__version__
    ) < StrictVersion("0.20"):
        error_and_exit("Pairing operations require SoCo v0.20 or greater")
        return False
    getattr(speaker, soco_function)()
    return True


@zero_parameters
def no_args_one_output(speaker, action, args, soco_function, use_local_speaker_list):
    result = getattr(speaker, soco_function)
    if callable(result):
        print(getattr(speaker, soco_function)())
    else:
        print(result)
    return True


@zero_or_one_parameter
def list_queue(speaker, action, args, soco_function, use_local_speaker_list):
    queue = speaker.get_queue(max_items=sonos_max_items)
    if len(queue) == 0:
        print("Queue is empty")
        return True
    if len(args) == 1:
        try:
            track_number = int(args[0])
            if not (0 < track_number <= len(queue)):
                error_and_exit(
                    "Track number {} is out of queue range".format(track_number)
                )
            queue = [queue[track_number - 1]]
        except ValueError:
            parameter_type_error(action, "integer")
    print()
    if len(args) == 1:
        print_tracks(queue, single_track=True, track_number=track_number)
    else:
        print_tracks(queue)
    print()
    return True


@zero_parameters
def list_numbered_things(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function in [
        "get_sonos_favorites",
        "get_favorite_radio_stations",
        # "get_tracks",
    ]:
        things = getattr(speaker.music_library, soco_function)(complete_result=True)
    else:
        things = getattr(speaker, soco_function)(complete_result=True)
    things_list = []
    for thing in things:
        things_list.append(thing.title)
    things_list.sort()
    print()
    index = 0
    for thing in things_list:
        index += 1
        print("{:5d}: {}".format(index, thing))
    print()
    return True


@zero_or_one_parameter
def volume_actions(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    # Special case for ramp_to_volume
    if soco_function == "ramp_to_volume":
        if np == 1:
            vol = int(args[0])
            if 0 <= vol <= 100:
                print(speaker.ramp_to_volume(vol))
                return True
            else:
                parameter_type_error(action, "0 to 100")
                return False
        else:
            parameter_number_error(action, "1")
            return False
    if soco_function == "group_volume":
        speaker = speaker.group
    if np == 0:
        print(speaker.volume)
    elif np == 1:
        try:
            vol = int(args[0])
        except:
            parameter_type_error(action, "integer from 0 to 100")
            return False
        if 0 <= vol <= 100:
            speaker.volume = vol
        else:
            parameter_type_error(action, "0 to 100")
            return False
    return True


@one_parameter
def relative_volume(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function == "group_relative_volume":
        speaker = speaker.group
    try:
        vol = int(args[0])
    except:
        parameter_type_error(action, "integer from -100 to 100")
        return False
    if -100 <= vol <= 100:
        speaker.volume += vol
    else:
        parameter_type_error(action, "integer from -100 to 100")
        return False
    return True


@zero_parameters
def print_info(speaker, action, args, soco_function, use_local_speaker_list):
    output = getattr(speaker, soco_function)()
    for item in sorted(output):
        if item not in ["metadata", "uri", "album_art"]:
            print("  {}: {}".format(item.capitalize(), output[item]))
    return True


@zero_or_one_parameter
def playback_mode(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    possible_args = [
        "normal",
        "repeat_all",
        "repeat_one",
        "shuffle",
        "shuffle_norepeat",
        "shuffle_repeat_one",
    ]
    if np == 0:
        print(speaker.play_mode)
    elif np == 1:
        if args[0].lower() in possible_args:
            speaker.play_mode = args[0]
        else:
            parameter_type_error(action, possible_args)
    return True


@zero_parameters
def transport_state(speaker, action, args, soco_function, use_local_speaker_list):
    print(speaker.get_current_transport_info()["current_transport_state"])
    return True


def play_favourite_core(speaker, favourite):
    """Core of the play_favourite action, but doesn't exit on failure
    """
    fs = speaker.music_library.get_sonos_favorites(complete_result=True)
    the_fav = None
    # Strict match
    for f in fs:
        if favourite == f.title:
            logging.info("Strict match '{}' found".format(f.title))
            the_fav = f
            break
    # Fuzzy match
    if not the_fav:
        favourite = favourite.lower()
        for f in fs:
            if favourite in f.title.lower():
                logging.info("Fuzzy match '{}' found".format(f.title))
                the_fav = f
                break
    if the_fav:
        # play_uri works for some favourites
        # ToDo: this is broken and we should test for the
        #       type of favourite
        try:
            uri = the_fav.get_uri()
            metadata = the_fav.resource_meta_data
            logging.info(
                "Trying 'play_uri()': URI={}, Metadata={}".format(uri, metadata)
            )
            speaker.play_uri(uri=uri, meta=metadata)
            return True, ""
        except Exception as e:
            e1 = e
            pass
        # Other favourites will be added to the queue, then played
        try:
            # Add to the end of the current queue and play
            logging.info("Trying 'add_to_queue()'")
            index = speaker.add_to_queue(the_fav, as_next=True)
            speaker.play_from_queue(index, start=True)
            return True, ""
        except Exception as e2:
            msg = "1: {} | 2: {}".format(str(e1), str(e2))
            return False, msg
    msg = "Favourite '{}' not found".format(favourite)
    return False, msg


@one_parameter
def play_favourite(speaker, action, args, soco_function, use_local_speaker_list):
    result, msg = play_favourite_core(speaker, args[0])
    if not result:
        error_and_exit(msg)
        return False
    else:
        return True


@one_parameter
def add_favourite_to_queue(
    speaker, action, args, soco_function, use_local_speaker_list
):
    favourite = args[0]
    fs = speaker.music_library.get_sonos_favorites()
    the_fav = None
    # Strict match
    for f in fs:
        if favourite == f.title:
            logging.info("Strict match '{}' found".format(f.title))
            the_fav = f
            break
    # Fuzzy match
    favourite = favourite.lower()
    if not the_fav:
        for f in fs:
            if favourite in f.title.lower():
                logging.info("Fuzzy match '{}' found".format(f.title))
                the_fav = f
                break
    if the_fav:
        try:
            # Print the queue position and return
            print(speaker.add_to_queue(the_fav))
            return True
        except Exception as e:
            error_and_exit("{}".format(str(e)))
            return False
    error_and_exit("Favourite '{}' not found".format(args[0]))
    return False


@one_parameter
def play_favourite_radio(speaker, action, args, soco_function, use_local_speaker_list):
    favourite = args[0]
    fs = speaker.music_library.get_favorite_radio_stations()
    the_fav = None
    # Strict match
    for f in fs:
        if favourite == f.title:
            logging.info("Strict match '{}' found".format(f.title))
            the_fav = f
            break
    # Fuzzy match
    favourite = favourite.lower()
    if not the_fav:
        for f in fs:
            if favourite in f.title.lower():
                logging.info("Fuzzy match '{}' found".format(f.title))
                the_fav = f
                break
    if the_fav:
        # play_uri works for some favourites
        try:
            uri = the_fav.get_uri()
            metadata = the_fav.resource_meta_data
            "Trying 'play_uri()': URI={}, Metadata={}".format(uri, metadata)
            speaker.play_uri(uri=uri, meta=metadata)
            return True
        except Exception as e:
            e1 = e
            pass
        # Other favourites will be added to the queue, then played
        try:
            # Add to the end of the current queue and play
            index = speaker.add_to_queue(the_fav, as_next=True)
            logging.info("Used'add_to_queue() [at {}], then play'".format(index))
            speaker.play_from_queue(index, start=True)
            return True
        except Exception as e2:
            error_and_exit("1: {} | 2:{}".format(str(e1), str(e2)))
            return False
    error_and_exit("Favourite '{}' not found".format(args[0]))
    return False


@one_or_two_parameters
def play_uri(speaker, action, args, soco_function, use_local_speaker_list):
    force_radio = True if args[0][:4].lower() == "http" else False
    if len(args) == 2:
        speaker.play_uri(
            args[0], title=args[1], force_radio=force_radio,
        )
    else:
        speaker.play_uri(args[0], force_radio=force_radio)
    return True


@zero_or_one_parameter
def sleep_timer(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        st = speaker.get_sleep_timer()
        if st:
            print(st)
        else:
            print(0)
    elif np == 1:
        if args[0].lower() in ["off", "cancel"]:
            logging.info("Cancelling sleep timer")
            speaker.set_sleep_timer(None)
        else:
            try:
                duration = convert_to_seconds(args[0])
            except ValueError:
                parameter_type_error(
                    action,
                    "number of hours, seconds or minutes + 'h/m/s', or off|cancel",
                )
                return False
            if 0 <= duration <= 86399:
                logging.info("Setting sleep timer to {}s".format(duration))
                speaker.set_sleep_timer(duration)
            else:
                parameter_type_error(action, "maximum duration is 23.999hrs")
                return False
    return True


@one_parameter
def sleep_at(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        duration = seconds_until(args[0])
    except ValueError:
        parameter_type_error(action, "a time in 24hr 'HH:MM' or 'HH:MM:SS' format")
        return False
    if 0 <= duration <= 86399:
        logging.info("Setting sleep timer to {}s".format(duration))
        speaker.set_sleep_timer(duration)
    else:
        parameter_type_error(action, "maximum duration is 23.999hrs")
        return False
    return True


@one_parameter
def group_or_pair(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function == "create_stereo_pair" and StrictVersion(
        soco.__version__
    ) < StrictVersion("0.20"):
        error_and_exit("Pairing operations require SoCo v0.20 or greater")
        return False
    speaker2 = get_speaker(args[0], use_local_speaker_list)
    getattr(speaker, soco_function)(speaker2)
    return True


@zero_parameters
def operate_on_all(speaker, action, args, soco_function, use_local_speaker_list):
    zones = speaker.all_zones
    for zone in zones:
        if zone.is_visible:
            try:
                # zone.unjoin()
                getattr(zone, soco_function)()
            except:
                # Ignore errors here; don't want to halt on
                # a failed pause (e.g., if speaker isn't playing)
                continue
    return True


@zero_parameters
def zones(speaker, action, args, soco_function, use_local_speaker_list):
    zones = speaker.all_zones if "all" in action else speaker.visible_zones
    for zone in zones:
        print("{} ({})".format(zone.player_name, zone.ip_address))
    return True


@zero_or_one_parameter
def play_from_queue(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        speaker.play_from_queue(0)
    elif np == 1:
        try:
            index = int(args[0])
        except:
            parameter_type_error(action, "integer")
            return False
        if 1 <= index <= speaker.queue_size:
            speaker.play_from_queue(index - 1)
        else:
            error_and_exit("Queue index '{}' is out of range".format(index))
            return False
    return True


@one_parameter
def remove_from_queue(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        index = int(args[0])
    except:
        parameter_type_error(action, "integer")
        return False
    qs = speaker.queue_size
    if 1 <= index <= qs:
        speaker.remove_from_queue(index - 1)
    else:
        error_and_exit("Queue index must be between 1 and {}".format(qs))
        return False
    return True


@one_parameter
def save_queue(speaker, action, args, soco_function, use_local_speaker_list):
    speaker.create_sonos_playlist_from_queue(args[0])
    return True


@one_parameter
def seek(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        speaker.seek(args[0])
    except:
        parameter_type_error(action, "HH:MM:SS on a seekable source")
        return False
    return True


@one_parameter
def playlist_operations(speaker, action, args, soco_function, use_local_speaker_list):
    name = args[0]
    if soco_function == "create_sonos_playlist":
        getattr(speaker, soco_function)(name)
        return True
    if soco_function == "add_uri_to_queue":
        getattr(speaker, soco_function)(name)
        return True
    playlist = get_playlist(speaker, name)
    if playlist is not None:
        result = getattr(speaker, soco_function)(playlist)
        if soco_function in ["add_to_queue"]:
            print(result)
    else:
        error_and_exit("Playlist '{}' not found".format(args[0]))
        return False
    return True


@one_parameter
def list_playlist_tracks(speaker, action, args, soco_function, use_local_speaker_list):
    playlist = get_playlist(speaker, args[0])
    if playlist:
        print()
        print_list_header("Sonos Playlist:", playlist.title)
        tracks = speaker.music_library.browse_by_idstring(
            "sonos_playlists", playlist.item_id, max_items=sonos_max_items
        )
        print_tracks(tracks)
        print()
        return True
    else:
        error_and_exit("Playlist '{}' not found".format(args[0]))
        return False


@two_parameters
def remove_from_playlist(speaker, action, args, soco_function, use_local_speaker_list):
    name = args[0]
    try:
        track_number = int(args[1])
    except:
        parameter_type_error(action, "integer (track number)")
        return False
    playlist = get_playlist(speaker, name)
    if playlist:
        speaker.remove_from_sonos_playlist(playlist, track_number - 1)
        return True
    else:
        error_and_exit("Playlist '{}' not found".format(args[0]))
        return False


@zero_or_one_parameter
def line_in(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        state = "on" if speaker.is_playing_line_in else "off"
        print(state)
    else:
        if args[0].lower() == "on":
            speaker.switch_to_line_in()
        else:
            line_in_source = get_speaker(args[0], use_local_speaker_list)
            if not line_in_source:
                error_and_exit("Speaker '{}' not found".format(args[0]))
                return False
            speaker.switch_to_line_in(line_in_source)
    return True


@zero_or_one_parameter
def eq(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        print(getattr(speaker, soco_function))
    elif np == 1:
        try:
            setting = int(args[0])
        except:
            parameter_type_error(action, "integer from -10 to 10")
            return False
        if -10 <= setting <= 10:
            setattr(speaker, soco_function, setting)
        else:
            parameter_type_error(action, "integer from -10 to 10")
            return False
    return True


@zero_or_one_parameter
def balance(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        left, right = getattr(speaker, soco_function)
        # Convert to something more intelligible than a 2-tuple
        # Use range from -100 (full left) to +100 (full right)
        print(right - left)
    elif np == 1:
        try:
            setting = int(args[0])
        except:
            parameter_type_error(action, "integer from -100 to 100")
            return False
        if -100 <= setting <= 100:
            if setting >= 0:
                left = 100 - setting
                right = 100
            elif setting < 0:
                left = 100
                right = 100 + setting
            setattr(speaker, soco_function, (left, right))
        else:
            parameter_type_error(action, "integer from -100 to 100")
            return False
    return True


@zero_parameters
def reindex(speaker, action, args, soco_function, use_local_speaker_list):
    speaker.music_library.start_library_update()
    return True


@zero_parameters
def info(speaker, action, args, soco_function, use_local_speaker_list):
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
        info["is_playing_radio"] = speaker.is_playing_radio
        info["is_playing_tv"] = speaker.is_playing_tv
        info["is_visible"] = speaker.is_visible
    for item in sorted(info):
        print("  {} = {}".format(item, info[item]))
    return True


@zero_parameters
def groups(speaker, action, args, soco_function, use_local_speaker_list):
    for group in speaker.all_groups:
        if group.coordinator.is_visible:
            print("[{}] : ".format(group.short_label), end="")
            for member in group.members:
                print(
                    "{} ({}) ".format(member.player_name, member.ip_address), end="",
                )
            print()
    return True


@zero_parameters
def list_alarms(speaker, action, args, soco_function, use_local_speaker_list):
    alarms = soco.alarms.get_alarms(speaker)
    if not alarms:
        return True
    details = []
    for alarm in alarms:
        didl = alarm.program_metadata
        title_start = didl.find("<dc:title>")
        if title_start >= 0:
            title_start += len("<dc:title>")
            title_end = didl.find("</dc:title>")
            title = didl[title_start:title_end]
        else:
            title = "Unknown"
        time = alarm.start_time.strftime("%H:%M")
        if alarm.duration:
            duration = alarm.duration.strftime("%H:%M")
        else:
            duration = "No Limit"
        details.append(
            [
                alarm.zone.player_name,
                time,
                duration,
                title,
                alarm.volume,
                convert_true_false(alarm.enabled),
                alarm.play_mode,
                alarm.recurrence,
                convert_true_false(alarm.include_linked_zones),
            ]
        )
    headers = [
        "Speaker",
        "Start Time",
        "Duration",
        "Title",
        "Volume",
        "Enabled",
        "Play Mode",
        "Recurrence",
        "Include Grouped",
    ]
    print()
    print(tabulate.tabulate(sorted(details), headers, numalign="center"))
    return True


@zero_parameters
def list_libraries(speaker, action, args, soco_function, use_local_speaker_list):
    shares = speaker.music_library.list_library_shares()
    index = 0
    for share in sorted(shares):
        index += 1
        print("{:2d}: {}".format(index, share))
    return True


@zero_parameters
def system_info(speaker, action, args, soco_function, use_local_speaker_list):
    print_speaker_table(speaker)
    return True


@zero_parameters
def list_all_playlist_tracks(
    speaker, action, args, soco_function, use_local_speaker_list
):
    playlists = speaker.get_sonos_playlists(complete_result=True)
    print()
    for playlist in playlists:
        print_list_header("Sonos Playlist:", playlist.title)
        tracks = speaker.music_library.browse_by_idstring(
            "sonos_playlists", playlist.item_id
        )
        print_tracks(tracks)
        print()
    return True


@zero_parameters
def wait_stop(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
    except Exception as e:
        error_and_exit("Exception {}".format(e))
    while True:
        try:
            event = sub.events.get(timeout=1.0)
            if event.variables["transport_state"] not in ["PLAYING", "TRANSITIONING"]:
                logging.info(
                    "Speaker '{}' in state '{}'".format(
                        speaker.player_name, event.variables["transport_state"]
                    )
                )
                sub.unsubscribe()
                return True
        except Empty:
            pass


@one_parameter
def wait_stopped_for(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        duration = convert_to_seconds(args[0])
    except ValueError:
        parameter_type_error(action, "Time h/m/s or HH:MM:SS")
    logging.info("Waiting until playback stopped for {}s".format(duration))
    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
    except Exception as e:
        error_and_exit("Exception {}".format(e))
    while True:
        try:
            # ToDo: Remove temporary fix for CTRL-C not exiting
            set_sigterm(True)
            event = sub.events.get(timeout=1.0)
            logging.info(
                "Event received: transport_state = '{}'".format(
                    event.variables["transport_state"]
                )
            )
            if event.variables["transport_state"] not in ["PLAYING", "TRANSITIONING"]:
                logging.info("Speaker is not 'PLAYING' or 'TRANSITIONING'")
                sub.unsubscribe()
                # ToDo: Should really return here and do this some other way ...
                #       this is what's requiring the SIGKILL

                # Poll for changes; count down reset timer
                # ToDo: Polling is not ideal; should be redesigned using events
                original_start_time = start_time = current_time = time.time()
                poll_interval = 10
                logging.info(
                    "Checking for not PLAYING, poll interval = {}s".format(
                        poll_interval
                    )
                )
                while (current_time - start_time) < duration:
                    state = speaker.get_current_transport_info()[
                        "current_transport_state"
                    ]
                    logging.info("Transport state = '{}'".format(state))
                    if state == "PLAYING":
                        # Restart the timer
                        start_time = current_time
                    logging.info(
                        "Elapsed since not 'PLAYING' = {}s, Total elapsed = {}s".format(
                            int(current_time - start_time),
                            int(current_time - original_start_time),
                        )
                    )
                    time.sleep(poll_interval)
                    current_time = time.time()
                logging.info(
                    "Timer expired after not 'PLAYING' for {}s, total elapsed = {}s".format(
                        int(current_time - start_time),
                        int(current_time - original_start_time),
                    )
                )
                set_sigterm(False)
                return True
        except:
            set_sigterm(False)
            pass


@zero_parameters
def wait_start(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
    except Exception as e:
        error_and_exit("Exception {}".format(e))
    while True:
        try:
            event = sub.events.get(timeout=1.0)
            if event.variables["transport_state"] == "PLAYING":
                logging.info(
                    "Speaker '{}' in state '{}'".format(
                        speaker.player_name, event.variables["transport_state"]
                    )
                )
                sub.unsubscribe()
                return True
        except Empty:
            pass


@one_parameter
def search_artists(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    artists = ml.get_music_library_information(
        "artists", search_term=name, complete_result=True
    )
    for artist in artists:
        print()
        print_list_header("Sonos Music Library Albums including Artist:", artist.title)
        albums = ml.get_music_library_information(
            "artists", subcategories=[artist.title], max_items=sonos_max_items
        )
        print_albums(albums, omit_first=True)  # Omit the first (empty) entry
        print()
        # ToDo: Debating whether to include lists of all the tracks that feature the artist...
        # print_list_header("Sonos Music Library Tracks with Artist:", artist.title)
        # tracks = ml.search_track(artist.title)
        # # tracks = ml.get_music_library_information("artists", subcategories=[name, ""], complete_result=True)
        # print_tracks(tracks)
        # print()
    return True


@zero_parameters
def list_artists(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    artists = ml.get_artists(complete_result=True)
    print()
    print_list_header("Sonos Music Library Artists", "")
    print_artists(artists)
    print()
    return True


@zero_parameters
def list_albums(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    artists = ml.get_albums(complete_result=True)
    print()
    print_list_header("Sonos Music Library Albums", "")
    print_albums(artists)
    print()
    return True


@one_parameter
def search_albums(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    albums = ml.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )
    if len(albums):
        print()
        print_list_header("Sonos Music Library Album Search:", name)
        print_albums(albums)
        print()
    return True


@one_parameter
def search_tracks(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    tracks = ml.get_music_library_information(
        "tracks", search_term=name, complete_result=True
    )
    if len(tracks):
        print()
        print_list_header("Sonos Music Library Track Search:", name)
        print_tracks(tracks)
        print()
    return True


@one_parameter
def search_library(speaker, action, args, soco_function, use_local_speaker_list):
    search_artists(speaker, action, args, soco_function, use_local_speaker_list)
    search_albums(speaker, action, args, soco_function, use_local_speaker_list)
    search_tracks(speaker, action, args, soco_function, use_local_speaker_list)
    return True


@one_parameter
def tracks_in_album(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    # tracks = ml.get_music_library_information("tracks", subcategories=[name], max_items=sonos_max_items)
    albums = ml.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )
    logging.info("Found {} album(s) matching '{}'".format(len(albums), name))
    print(albums)
    for album in albums:
        tracks = ml.get_music_library_information(
            "artists", subcategories=["", album.title], complete_result=True
        )
        print()
        print_list_header("Sonos Music Library Tracks in Album:", album.title)
        print_tracks(tracks)
        print()
    return True


@one_parameter
def queue_album(speaker, action, args, soco_function, use_local_speaker_list):
    """Add an album to the queue. If there are multiple matches, a random
    match will be selected.
    :returns: The position in the queue of the first track in the album
    """
    name = args[0]
    albums = speaker.music_library.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )
    if len(albums):
        album = albums[randint(0, len(albums) - 1)]
        print(speaker.add_to_queue(album))
        return True
    else:
        error_and_exit("Album '{}' not found".format(name))


@one_parameter
def queue_track(speaker, action, args, soco_function, use_local_speaker_list):
    """Add a track to the queue. If there are multiple matches, a random match
    will be selected.
    :returns: The position in the queue of the track
    """
    name = args[0]
    tracks = speaker.music_library.get_music_library_information(
        "tracks", search_term=name, complete_result=True
    )
    if len(tracks):
        track = tracks[randint(0, len(tracks) - 1)]
        print(speaker.add_to_queue(track))
        return True
    else:
        error_and_exit("Track '{}' not found".format(name))


@one_or_more_parameters
def if_stopped_or_playing(speaker, action, args, soco_function, use_local_speaker_list):
    """Perform the action only if the speaker is currently in the desired playback state
    """
    state = speaker.get_current_transport_info()["current_transport_state"]
    logging.info(
        "Condition: '{}': Speaker '{}' is in state '{}'".format(
            action, speaker.player_name, state
        )
    )
    if (state != "PLAYING" and action == "if_playing") or (
        state == "PLAYING" and action == "if_stopped"
    ):
        logging.info("Action suppressed")
        return True
    else:
        action = args[0]
        args = args[1:]
        logging.info(
            "Action invoked: '{} {} {}'".format(
                speaker.player_name, action, " ".join(args)
            )
        )
        return process_action(speaker, action, args, use_local_speaker_list)


@one_parameter
def cue_favourite(speaker, action, args, soco_function, use_local_speaker_list):
    """Shortcut to mute, play favourite, stop favourite, and unmute.
    Preserve the mute state
    """
    if not speaker.is_coordinator:
        error_and_exit(
            "Action '{}' can only be applied to a coordinator".format(action)
        )
        return False
    unmute = False
    unmute_group = False
    if not speaker.mute:
        speaker.mute = True
        unmute = True
    if not speaker.group.mute:
        speaker.group.mute = True
        unmute_group = True
    result, msg = play_favourite_core(speaker, args[0])
    speaker.stop()
    if unmute:
        speaker.mute = False
    if unmute_group:
        speaker.group.mute = False
    if not result:
        error_and_exit(msg)
        return False
    return True


@one_parameter
def transfer_playback(speaker, action, args, soco_function, use_local_speaker_list):
    """Transfer playback from one speaker to another, by grouping and ungrouping.
    """
    if not speaker.is_coordinator:
        error_and_exit("Speaker '{}' is not a coordinator".format(speaker.player_name))
        return False
    speaker2 = get_speaker(args[0], use_local_speaker_list)
    if speaker2:
        speaker2.join(speaker)
        speaker.unjoin()
        return True
    else:
        error_and_exit("Speaker '{}' not found".format(args[0]))
        return False


def process_action(speaker, action, args, use_local_speaker_list):
    sonos_function = actions.get(action, None)
    if sonos_function:
        return sonos_function.processing_function(
            speaker, action, args, sonos_function.soco_function, use_local_speaker_list,
        )
    else:
        return False


# Type for holding action processing functions
SonosFunction = namedtuple(
    "SonosFunction", ["processing_function", "soco_function",], rename=False,
)

# Actions and associated processing functions
actions = {
    "mute": SonosFunction(on_off_action, "mute"),
    "cross_fade": SonosFunction(on_off_action, "cross_fade"),
    "crossfade": SonosFunction(on_off_action, "cross_fade"),
    "loudness": SonosFunction(on_off_action, "loudness"),
    "status_light": SonosFunction(on_off_action, "status_light"),
    "light": SonosFunction(on_off_action, "status_light"),
    "night_mode": SonosFunction(on_off_action, "night_mode"),
    "night": SonosFunction(on_off_action, "night_mode"),
    "dialog_mode": SonosFunction(on_off_action, "dialog_mode"),
    "dialog": SonosFunction(on_off_action, "dialog_mode"),
    "dialogue_mode": SonosFunction(on_off_action, "dialog_mode"),
    "dialogue": SonosFunction(on_off_action, "dialog_mode"),
    "play": SonosFunction(no_args_no_output, "play"),
    "start": SonosFunction(no_args_no_output, "play"),
    "stop": SonosFunction(no_args_no_output, "stop"),
    "pause": SonosFunction(no_args_no_output, "pause"),
    "next": SonosFunction(no_args_no_output, "next"),
    "previous": SonosFunction(no_args_no_output, "previous"),
    "prev": SonosFunction(no_args_no_output, "previous"),
    "list_queue": SonosFunction(list_queue, "get_queue"),
    "lq": SonosFunction(list_queue, "get_queue"),
    "queue": SonosFunction(list_queue, "get_queue"),
    "q": SonosFunction(list_queue, "get_queue"),
    "list_playlists": SonosFunction(list_numbered_things, "get_sonos_playlists"),
    "playlists": SonosFunction(list_numbered_things, "get_sonos_playlists"),
    "lp": SonosFunction(list_numbered_things, "get_sonos_playlists"),
    "list_favourites": SonosFunction(list_numbered_things, "get_sonos_favorites"),
    "list_favorites": SonosFunction(list_numbered_things, "get_sonos_favorites"),
    "list_favs": SonosFunction(list_numbered_things, "get_sonos_favorites"),
    "lf": SonosFunction(list_numbered_things, "get_sonos_favorites"),
    "volume": SonosFunction(volume_actions, "volume"),
    "vol": SonosFunction(volume_actions, "volume"),
    "v": SonosFunction(volume_actions, "volume"),
    "group_volume": SonosFunction(volume_actions, "group_volume"),
    "group_vol": SonosFunction(volume_actions, "group_volume"),
    "gv": SonosFunction(volume_actions, "group_volume"),
    "ramp_to_volume": SonosFunction(volume_actions, "ramp_to_volume"),
    "ramp": SonosFunction(volume_actions, "ramp_to_volume"),
    "relative_volume": SonosFunction(relative_volume, "relative_volume"),
    "rel_vol": SonosFunction(relative_volume, "relative_volume"),
    "rv": SonosFunction(relative_volume, "relative_volume"),
    "group_relative_volume": SonosFunction(relative_volume, "group_relative_volume"),
    "group_rel_vol": SonosFunction(relative_volume, "group_relative_volume"),
    "grv": SonosFunction(relative_volume, "group_relative_volume"),
    "track": SonosFunction(print_info, "get_current_track_info"),
    "play_mode": SonosFunction(playback_mode, "play_mode"),
    "mode": SonosFunction(playback_mode, "play_mode"),
    "playback_state": SonosFunction(transport_state, "get_current_transport_info"),
    "playback": SonosFunction(transport_state, "get_current_transport_info"),
    "state": SonosFunction(transport_state, "get_current_transport_info"),
    "status": SonosFunction(transport_state, "get_current_transport_info"),
    "play_favourite": SonosFunction(play_favourite, "play_favorite"),
    "play_favorite": SonosFunction(play_favourite, "play_favorite"),
    "favourite": SonosFunction(play_favourite, "play_favorite"),
    "favorite": SonosFunction(play_favourite, "play_favorite"),
    "play_fav": SonosFunction(play_favourite, "play_favorite"),
    "fav": SonosFunction(play_favourite, "play_favorite"),
    "pf": SonosFunction(play_favourite, "play_favorite"),
    "play_uri": SonosFunction(play_uri, "play_uri"),
    "uri": SonosFunction(play_uri, "play_uri"),
    "pu": SonosFunction(play_uri, "play_uri"),
    "sleep_timer": SonosFunction(sleep_timer, "sleep_timer"),
    "sleep": SonosFunction(sleep_timer, "sleep_timer"),
    "group": SonosFunction(group_or_pair, "join"),
    "g": SonosFunction(group_or_pair, "join"),
    "ungroup": SonosFunction(no_args_no_output, "unjoin"),
    "ug": SonosFunction(no_args_no_output, "unjoin"),
    "u": SonosFunction(no_args_no_output, "unjoin"),
    "party_mode": SonosFunction(no_args_no_output, "partymode"),
    "party": SonosFunction(no_args_no_output, "partymode"),
    "ungroup_all": SonosFunction(operate_on_all, "unjoin"),
    "zones": SonosFunction(zones, "zones"),
    "all_zones": SonosFunction(zones, "zones"),
    "rooms": SonosFunction(zones, "zones"),
    "all_rooms": SonosFunction(zones, "zones"),
    "visible_zones": SonosFunction(zones, "zones"),
    "visible_rooms": SonosFunction(zones, "zones"),
    "play_from_queue": SonosFunction(play_from_queue, "play_from_queue"),
    "play_queue": SonosFunction(play_from_queue, "play_from_queue"),
    "pfq": SonosFunction(play_from_queue, "play_from_queue"),
    "pq": SonosFunction(play_from_queue, "play_from_queue"),
    "remove_from_queue": SonosFunction(remove_from_queue, "remove_from_queue"),
    "rfq": SonosFunction(remove_from_queue, "remove_from_queue"),
    "rq": SonosFunction(remove_from_queue, "remove_from_queue"),
    "clear_queue": SonosFunction(no_args_no_output, "clear_queue"),
    "cq": SonosFunction(no_args_no_output, "clear_queue"),
    "group_mute": SonosFunction(on_off_action, "group_mute"),
    "save_queue": SonosFunction(save_queue, "create_sonos_playlist_from_queue"),
    "sq": SonosFunction(save_queue, "create_sonos_playlist_from_queue"),
    "queue_length": SonosFunction(no_args_one_output, "queue_size"),
    "ql": SonosFunction(no_args_one_output, "queue_size"),
    "add_playlist_to_queue": SonosFunction(playlist_operations, "add_to_queue"),
    "add_pl_to_queue": SonosFunction(playlist_operations, "add_to_queue"),
    "queue_playlist": SonosFunction(playlist_operations, "add_to_queue"),
    "apq": SonosFunction(playlist_operations, "add_to_queue"),
    "pause_all": SonosFunction(operate_on_all, "pause"),
    "seek": SonosFunction(seek, "seek"),
    "line_in": SonosFunction(line_in, ""),
    "bass": SonosFunction(eq, "bass"),
    "treble": SonosFunction(eq, "treble"),
    "balance": SonosFunction(balance, "balance"),
    "reindex": SonosFunction(reindex, "start_library_update"),
    "info": SonosFunction(info, "get_info"),
    "groups": SonosFunction(groups, "groups"),
    "pair": SonosFunction(group_or_pair, "create_stereo_pair"),
    "unpair": SonosFunction(no_args_no_output, "separate_stereo_pair"),
    "delete_playlist": SonosFunction(playlist_operations, "remove_sonos_playlist"),
    "remove_playlist": SonosFunction(playlist_operations, "remove_sonos_playlist"),
    "clear_playlist": SonosFunction(playlist_operations, "clear_sonos_playlist"),
    "create_playlist": SonosFunction(playlist_operations, "create_sonos_playlist"),
    "add_uri_to_queue": SonosFunction(playlist_operations, "add_uri_to_queue"),
    "auq": SonosFunction(playlist_operations, "add_uri_to_queue"),
    "remove_from_playlist": SonosFunction(
        remove_from_playlist, "remove_from_sonos_playlist"
    ),
    "rfp": SonosFunction(remove_from_playlist, "remove_from_sonos_playlist"),
    "favorite_radio_stations": SonosFunction(
        list_numbered_things, "get_favorite_radio_stations"
    ),
    "favourite_radio_stations": SonosFunction(
        list_numbered_things, "get_favorite_radio_stations"
    ),
    "play_favourite_radio_station": SonosFunction(play_favourite_radio, "play_uri"),
    "play_favorite_radio_station": SonosFunction(play_favourite_radio, "play_uri"),
    "pfrs": SonosFunction(play_favourite_radio, "play_uri"),
    # "tracks": SonosFunction(list_numbered_things, "get_tracks"),
    "alarms": SonosFunction(list_alarms, "get_alarms"),
    "libraries": SonosFunction(list_libraries, "list_library_shares"),
    "shares": SonosFunction(list_libraries, "list_library_shares"),
    "sysinfo": SonosFunction(system_info, ""),
    "sleep_at": SonosFunction(sleep_at, ""),
    "add_favourite_to_queue": SonosFunction(add_favourite_to_queue, "add_to_queue"),
    "add_favorite_to_queue": SonosFunction(add_favourite_to_queue, "add_to_queue"),
    "add_fav_to_queue": SonosFunction(add_favourite_to_queue, "add_to_queue"),
    "afq": SonosFunction(add_favourite_to_queue, "add_to_queue"),
    "list_playlist_tracks": SonosFunction(list_playlist_tracks, "list_tracks"),
    "lpt": SonosFunction(list_playlist_tracks, "list_tracks"),
    "list_all_playlist_tracks": SonosFunction(list_all_playlist_tracks, ""),
    "lapt": SonosFunction(list_all_playlist_tracks, ""),
    "wait_stop": SonosFunction(wait_stop, ""),
    "wait_start": SonosFunction(wait_start, ""),
    "wait_stopped_for": SonosFunction(wait_stopped_for, ""),
    "wsf": SonosFunction(wait_stopped_for, ""),
    "if_stopped": SonosFunction(if_stopped_or_playing, ""),
    "if_playing": SonosFunction(if_stopped_or_playing, ""),
    "search_library": SonosFunction(search_library, ""),
    "sl": SonosFunction(search_library, ""),
    "search_artists": SonosFunction(search_artists, ""),
    "sart": SonosFunction(search_artists, ""),
    "search_albums": SonosFunction(search_albums, ""),
    "salb": SonosFunction(search_albums, ""),
    "search_tracks": SonosFunction(search_tracks, ""),
    "st": SonosFunction(search_tracks, ""),
    "tracks_in_album": SonosFunction(tracks_in_album, ""),
    "tia": SonosFunction(tracks_in_album, ""),
    "list_albums": SonosFunction(list_albums, ""),
    "albums": SonosFunction(list_albums, ""),
    "list_artists": SonosFunction(list_artists, ""),
    "artists": SonosFunction(list_artists, ""),
    "queue_album": SonosFunction(queue_album, ""),
    "qa": SonosFunction(queue_album, ""),
    "queue_track": SonosFunction(queue_track, ""),
    "qt": SonosFunction(queue_track, ""),
    "cue_favourite": SonosFunction(cue_favourite, ""),
    "cue_favorite": SonosFunction(cue_favourite, ""),
    "cue_fav": SonosFunction(cue_favourite, ""),
    "cf": SonosFunction(cue_favourite, ""),
    "transfer_playback": SonosFunction(transfer_playback, ""),
    "transfer": SonosFunction(transfer_playback, ""),
}
