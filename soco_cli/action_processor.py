import os
import sys
import logging
import soco
import soco.alarms
import pprint
import tabulate
import datetime
from collections import namedtuple

from . import sonos
from . import speaker_info

pp = pprint.PrettyPrinter(width=120)


# Error handling functions 3.7
def error_and_exit(msg):
    # Print to stderror
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    os._exit(1)


def parameter_type_error(action, required_params):
    msg = "Action '{}' takes parameter(s): {}".format(action, required_params)
    error_and_exit(msg)


def parameter_number_error(action, parameter_number):
    msg = "Action '{}' takes {} parameter(s)".format(action, parameter_number)
    error_and_exit(msg)


def convert_true_false(true_or_false, conversion="YesOrNo"):
    if conversion == "YesOrNo":
        return "Yes" if true_or_false is True else "No"
    if conversion == "onoroff":
        return "on" if true_or_false is True else "off"


# Parameter checking decorators
def zero_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 0:
            parameter_number_error(args[1], "no")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def one_parameter(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 1:
            parameter_number_error(args[1], "1")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def zero_or_one_parameter(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) not in [0, 1]:
            parameter_number_error(args[1], "0 or 1")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def one_or_two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) not in [1, 2]:
            parameter_number_error(args[1], "1 or 2")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 2:
            parameter_number_error(args[1], "2")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


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
    if soco_function == "separate_stereo_pair" and float(soco.__version__) < 0.20:
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


@zero_parameters
def list_queue(speaker, action, args, soco_function, use_local_speaker_list):
    queue = speaker.get_queue(max_items=1000)
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
    return True


@zero_parameters
def list_numbered_things(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function in [
        "get_sonos_favorites",
        "get_favorite_radio_stations",
        "get_albums",
        "get_artists",
        "get_tracks",
    ]:
        things = getattr(speaker.music_library, soco_function)(complete_result=True)
    else:
        things = getattr(speaker, soco_function)(complete_result=True)
    things_list = []
    for thing in things:
        things_list.append(thing.title)
    things_list.sort()
    index = 0
    for thing in things_list:
        index += 1
        print("{:5d}: {}".format(index, thing))
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
            print("  {}: {}".format(item, output[item]))
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


@one_parameter
def play_favourite(speaker, action, args, soco_function, use_local_speaker_list):
    favourite = args[0]
    fs = speaker.music_library.get_sonos_favorites()
    the_fav = None
    # Strict match
    for f in fs:
        if favourite == f.title:
            the_fav = f
            break
    # Fuzzy match
    favourite = favourite.lower()
    if not the_fav:
        for f in fs:
            if favourite in f.title.lower():
                the_fav = f
                break
    if the_fav:
        # play_uri works for some favourites
        try:
            uri = the_fav.get_uri()
            metadata = the_fav.resource_meta_data
            speaker.play_uri(uri=uri, meta=metadata)
            return True
        except Exception as e:
            e1 = e
            pass
        # Other favourites will be added to the queue, then played
        try:
            # Add to the end of the current queue and play
            index = speaker.add_to_queue(the_fav, as_next=True)
            speaker.play_from_queue(index, start=True)
            return True
        except Exception as e2:
            error_and_exit("1: {} | 2:{}".format(str(e1), str(e2)))
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
            the_fav = f
            break
    # Fuzzy match
    favourite = favourite.lower()
    if not the_fav:
        for f in fs:
            if favourite in f.title.lower():
                the_fav = f
                break
    if the_fav:
        # play_uri works for some favourites
        try:
            uri = the_fav.get_uri()
            metadata = the_fav.resource_meta_data
            speaker.play_uri(uri=uri, meta=metadata)
            return True
        except Exception as e:
            e1 = e
            pass
        # Other favourites will be added to the queue, then played
        try:
            # Add to the end of the current queue and play
            index = speaker.add_to_queue(the_fav, as_next=True)
            speaker.play_from_queue(index, start=True)
            return True
        except Exception as e2:
            error_and_exit("1: {} | 2:{}".format(str(e1), str(e2)))
            return False
    error_and_exit("Favourite '{}' not found".format(args[0]))
    return False


@one_or_two_parameters
def play_uri(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np not in [1, 2]:
        parameter_number_error(action, "1 or 2")
        return False
    else:
        force_radio = True if args[0][:4].lower() == "http" else False
        if np == 2:
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
            duration = sonos.convert_to_seconds(args[0])
            if duration is None:
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


def create_time(time_str):
    """Process times in HH:MM(:SS) format. Return a 'time' object."""
    time_str = time_str.lower()
    try:
        if ":" in time_str:  # Assume form is HH:MM:SS or HH:MM
            parts = time_str.split(":")
            if len(parts) == 3:  # HH:MM:SS
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                if not (0 <= hours <= 24 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                    return None
            elif len(parts) == 2:  # HH:MM
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = 0
                if not (0 <= hours <= 24 and 0 <= minutes <= 59):
                    return None
            else:
                return None
            return datetime.time(hour=hours, minute=minutes, second=seconds)
    except ValueError:
        return None


def seconds_until(time_str):
    # target_time = datetime.time.fromisoformat(time_str)
    target_time = create_time(time_str)
    if not target_time:
        raise ValueError
    now_time = datetime.datetime.now().time()
    delta_target = datetime.timedelta(
        hours=target_time.hour, minutes=target_time.minute, seconds=target_time.second
    )
    delta_now = datetime.timedelta(
        hours=now_time.hour, minutes=now_time.minute, seconds=now_time.second
    )
    diff = int((delta_target - delta_now).total_seconds())
    # Ensure 'past' times are treated as future times by adding 24hr
    return diff if diff > 0 else diff + 24 * 60 * 60


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
    if soco_function == "create_stereo_pair" and float(soco.__version__) < 0.20:
        error_and_exit("Pairing operations require SoCo v0.20 or greater")
        return False
    speaker2 = sonos.get_speaker(args[0], use_local_speaker_list)
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
        error_and_exit("Queue index should be between 1 and {}".format(qs))
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
    playlists = speaker.get_sonos_playlists()
    # Strict match
    for playlist in playlists:
        if name == playlist.title:
            getattr(speaker, soco_function)(playlist)
            return True
    # Fuzzy match
    name = name.lower()
    for playlist in playlists:
        if name in playlist.title.lower():
            getattr(speaker, soco_function)(playlist)
            return True
    error_and_exit("Playlist {} not found".format(args[0]))
    return False


@two_parameters
def remove_from_playlist(speaker, action, args, soco_function, use_local_speaker_list):
    name = args[0]
    try:
        track_number = int(args[1])
    except:
        parameter_type_error(action, "integer (track number)")
        return False
    playlists = speaker.get_sonos_playlists()
    # Strict match
    for playlist in playlists:
        if name == playlist.title:
            getattr(speaker, soco_function)(playlist, track_number - 1)
            return True
    # Fuzzy match
    name = name.lower()
    for playlist in playlists:
        if name in playlist.title.lower():
            getattr(speaker, soco_function)(playlist, track_number - 1)
            return True
    error_and_exit("Playlist {} not found".format(args[0]))
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
            line_in_source = sonos.get_speaker(args[0], use_local_speaker_list)
            if not line_in_source:
                error_and_exit("Speaker {} not found".format(args[0]))
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
    speaker_info.print_speaker_table(speaker)
    return True


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
    "albums": SonosFunction(list_numbered_things, "get_albums"),
    "artists": SonosFunction(list_numbered_things, "get_artists"),
    "tracks": SonosFunction(list_numbered_things, "get_tracks"),
    "alarms": SonosFunction(list_alarms, "get_alarms"),
    "libraries": SonosFunction(list_libraries, "list_library_shares"),
    "shares": SonosFunction(list_libraries, "list_library_shares"),
    "sysinfo": SonosFunction(system_info, ""),
    "sleep_at": SonosFunction(sleep_at, ""),
}
