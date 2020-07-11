import os
import sys
import soco
from collections import namedtuple


def error_and_exit(msg):
    # Print to stderror
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    os._exit(1)


def parameter_type_error(action, required_params):
    msg = "Action '{}' takes parameter(s): {}".format(action, required_params)
    error_and_exit(msg)


def parameter_number_error(action, parameter_number):
    msg = "Action '{}' requires {} parameters".format(action, parameter_number)
    error_and_exit(msg)


# Action processing functions
def on_off_action(speaker, action, args, soco_function, use_local_speaker_list):
    """Method to deal with actions that have 'on|off semantics"""
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
    else:
        parameter_number_error(action, "0 or 1")
    return True


def no_args_no_output(speaker, action, args, soco_function, use_local_speaker_list):
    if len(args) == 0:
        getattr(speaker, soco_function)()
        return True
    else:
        parameter_number_error(action, "no")
        # Probably doesn't get here, but just in case
        return True


def list_queue(speaker, action, args, soco_function, use_local_speaker_list):
    if len(args) == 0:
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
    else:
        parameter_number_error(action, "no")
        # Probably doesn't get here, but just in case
        return True


def list_numbered_things(speaker, action, args, sonos_function, use_local_speaker_list):
    if len(args) == 0:
        if sonos_function == "get_sonos_favorites":
            things = getattr(speaker.music_library, sonos_function)()
        else:
            things = getattr(speaker, sonos_function)()
        things_list = []
        for thing in things:
            things_list.append(thing.title)
        things_list.sort()
        index = 0
        for thing in things_list:
            index += 1
            print("{:3d}: {}".format(index, thing))
        return True
    else:
        parameter_number_error(action, "no")
        # Probably doesn't get here, but just in case
        return True


def volume_actions(speaker, action, args, sonos_function, use_local_speaker_list):
    np = len(args)
    if sonos_function == "ramp_to_volume":
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
    group = True if sonos_function == "group_volume" else False
    if np == 0:
        if group:
            print(speaker.group.volume)
        else:
            print(speaker.volume)
    elif np == 1:
        vol = int(args[0])
        if 0 <= vol <= 100:
            if group:
                speaker.group.volume = vol
            else:
                speaker.volume = vol
        else:
            parameter_type_error(action, "0 to 100")
            return False
    else:
        parameter_number_error(action, "0 or 1")
        return False
    return True


def relative_volume_actions(speaker, action, args, sonos_function, use_local_speaker_list):
    np = len(args)
    group = True if sonos_function == "group_relative_volume" else False
    if np == 1:
        vol = int(args[0])
        if -100 <= vol <= 100:
            if group:
                speaker.group.volume += vol
            else:
                speaker.volume += vol
        else:
            parameter_type_error(action, "-100 to 100")
            return False
    else:
        parameter_number_error(action, "1")
        return False
    return True


def process_action(speaker, action, args, use_local_speaker_list):
    sonos_function = actions.get(action, None)
    if sonos_function:
        return sonos_function.processing_function(
            speaker,
            action,
            args,
            sonos_function.soco_function,
            use_local_speaker_list,
        )
    else:
        return False


# Type for holding action processing functions
SonosFunction = namedtuple(
    "SonosFunction",
    ["processing_function", "soco_function",],
    rename=False,
)

# Actions and associated processing methods
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
    "relative_volume": SonosFunction(relative_volume_actions, "relative_volume"),
    "rel_vol": SonosFunction(relative_volume_actions, "relative_volume"),
    "rv": SonosFunction(relative_volume_actions, "relative_volume"),
    "group_relative_volume": SonosFunction(relative_volume_actions, "group_relative_volume"),
    "group_rel_vol": SonosFunction(relative_volume_actions, "group_relative_volume"),
    "grv": SonosFunction(relative_volume_actions, "group_relative_volume"),
}