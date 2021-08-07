"""The main command processing module.

This module requires refactoring, improvements to its argument handling,
and needs to be converted to a Class.
"""

import logging
import pprint
import time
from datetime import datetime, timedelta
from distutils.version import StrictVersion
from os import get_terminal_size
from queue import Empty
from random import randint

import soco
import soco.alarms
import tabulate
from soco.exceptions import NotSupportedException, SoCoUPnPException
from xmltodict import parse

from soco.plugins.sharelink import ShareLinkPlugin

from soco_cli.play_local_file import play_local_file
from soco_cli.play_m3u_file import play_m3u_file
from soco_cli.speaker_info import print_speaker_table
from soco_cli.utils import (
    convert_to_seconds,
    convert_true_false,
    error_report,
    event_unsubscribe,
    get_right_hand_speaker,
    get_speaker,
    one_or_more_parameters,
    one_or_two_parameters,
    one_parameter,
    parameter_number_error,
    parameter_type_error,
    playback_state,
    pretty_print_values,
    read_search,
    rename_speaker_in_cache,
    save_search,
    seconds_until,
    set_sigterm,
    two_parameters,
    zero_one_or_two_parameters,
    zero_or_one_parameter,
    zero_parameters,
)

pp = pprint.PrettyPrinter(width=120)
SONOS_MAX_ITEMS = 66000


def get_playlist(speaker, name, library=False):
    """Returns the playlist object with 'name' otherwise None."""
    if library:
        playlists = speaker.music_library.get_playlists(complete_result=True)
    else:
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
    underline = "=" * len(title)
    print(spacer + title)
    print(spacer + underline)


def get_current_queue_position(speaker, tracks=None):
    """Find the current queue position and whether a speaker is playing
    from the queue.

    'is_playing' will be reported correctly in most, but not all, cases.
    """
    qp = 0
    is_playing = False
    track_title = None

    try:
        track_info = speaker.get_current_track_info()
        qp = int(track_info["playlist_position"])
        track_title = track_info["title"]
    except:
        qp = 0

    try:
        cts = speaker.get_current_transport_info()["current_transport_state"]
        if cts == "PLAYING":
            if tracks is not None:
                try:
                    if tracks[qp - 1].title == track_title:
                        is_playing = True
                    else:
                        is_playing = False
                        qp = 1
                except:
                    is_playing = False
                    qp = 1
            else:
                is_playing = True
        else:
            is_playing = False
    except:
        is_playing = False

    return qp, is_playing


def print_tracks(tracks, speaker=None, single_track=False, track_number=None):
    qp = None
    is_playing = None
    if speaker:
        qp, is_playing = get_current_queue_position(speaker, tracks)
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
        if not qp or qp != item_number:
            if track.item_class == "object.item.audioItem.podcast":
                print("{:7d}: Podcast: {}".format(item_number, title))
            else:
                print(
                    "{:7d}: Artist: {} | Album: {} | Title: {}".format(
                        item_number, artist, album, title
                    )
                )
        elif qp == item_number:
            if is_playing:
                prefix = " *> "
            else:
                prefix = "  * "
            if track.item_class == "object.item.audioItem.podcast":
                print("{}{:3d}: Podcast: {}".format(prefix, item_number, title))
            else:
                print(
                    "{}{:3d}: Artist: {} | Album: {} | Title: {}".format(
                        prefix, item_number, artist, album, title
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
            return False
    return True


@zero_parameters
def no_args_no_output(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function == "separate_stereo_pair" and StrictVersion(
        soco.__version__
    ) < StrictVersion("0.20"):
        error_report("Pairing operations require SoCo v0.20 or greater")
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
    queue = speaker.get_queue(max_items=SONOS_MAX_ITEMS)
    if len(queue) == 0:
        print("Queue is empty")
        return True
    if len(args) == 1:
        try:
            track_number = int(args[0])
            if not 0 < track_number <= len(queue):
                error_report(
                    "Track number {} is out of queue range".format(track_number)
                )
                return False
            queue = [queue[track_number - 1]]
        except ValueError:
            parameter_type_error(action, "integer")
            return False
    print()
    if len(args) == 1:
        print_tracks(queue, speaker, single_track=True, track_number=track_number)
    else:
        print_tracks(queue, speaker)
    print()
    return True


@zero_parameters
def list_numbered_things(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function in [
        "get_sonos_favorites",
        "get_favorite_radio_stations",
        "get_playlists",
        # "get_tracks",
    ]:
        things = getattr(speaker.music_library, soco_function)(complete_result=True)
    else:
        things = getattr(speaker, soco_function)(complete_result=True)
    things_list = [thing.title for thing in things]
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
            parameter_type_error(action, "0 to 100")
            return False
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
        speaker.set_relative_volume(vol)
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


@zero_parameters
def track(speaker, action, args, soco_function, use_local_speaker_list):
    state = speaker.get_current_transport_info()["current_transport_state"]

    if speaker.is_playing_line_in:
        print("Using Line In (state: {})".format(state))
        return True

    print(" Playback is {}:".format(playback_state(state)))
    track_info = speaker.get_current_track_info()
    logging.info("Current track info:\n{}".format(track_info))

    # Accumulate info elements to be printed
    elements = {"Channel": speaker.get_current_media_info()["channel"]}

    # Stream
    if track_info["duration"] == "0:00:00":
        logging.info("Track is a radio stream")
        for item in sorted(track_info):
            if item not in [
                "metadata",
                "album_art",
                "duration",
                "playlist_position",
                "position",
                "uri",
            ]:
                elements[item.capitalize()] = track_info[item]
        try:
            logging.info("Attempting to find 'Artist'")
            metadata = parse(track_info["metadata"])
            if elements["Artist"] == "":
                elements["Artist"] = metadata["DIDL-Lite"]["item"]["dc:creator"]
        except:
            logging.info("Unable to find 'Artist'")
        try:
            logging.info("Attempting to find 'Radio Show' using events")
            sub = speaker.avTransport.subscribe()
            event = sub.events.get(timeout=0.5)
            elements["Radio Show"] = event.variables[
                "current_track_meta_data"
            ].radio_show.rpartition(",")[0]
            sub.unsubscribe()
        except:
            logging.info("Unable to find 'Radio Show'")

    # Podcast, Audio Book, or normal track
    else:
        logging.info("Track has a non-zero duration")
        metadata = parse(track_info["metadata"])
        logging.info("Track metadata: {}".format(metadata))

        # Podcast
        if (
            metadata["DIDL-Lite"]["item"]["upnp:class"]
            == "object.item.audioItem.podcast"
        ):
            logging.info("Track is a podcast")
            try:
                elements["Podcast"] = metadata["DIDL-Lite"]["item"]["r:podcast"]
                elements["Release Date"] = metadata["DIDL-Lite"]["item"][
                    "r:releaseDate"
                ][:10]
            except:
                logging.info("Failed to find 'Podcast' and/or 'Release Date'")
            for item in sorted(track_info):
                if item not in ["metadata", "uri", "album_art", "album", "artist"]:
                    elements[item.capitalize()] = track_info[item]

        # Audio book
        elif (
            "object.item.audioItem.audioBook"
            in metadata["DIDL-Lite"]["item"]["upnp:class"]
        ):
            logging.info("Track is an audio book")
            try:
                elements["Book Title"] = elements.pop("Channel", "")
                elements["Creator(s)"] = track_info["artist"]
                elements["Narrator(s)"] = metadata["DIDL-Lite"]["item"]["r:narrator"]
                elements["Chapter"] = metadata["DIDL-Lite"]["item"]["dc:title"]
            except:
                logging.info("Failed to find book details")
            for item in sorted(track_info):
                if item not in [
                    "metadata",
                    "uri",
                    "album_art",
                    "album",
                    "artist",
                    "title",
                    "playlist_position",
                ]:
                    elements[item.capitalize()] = track_info[item]

        # Regular track
        else:
            logging.info("Track is a normal audio track")
            for item in sorted(track_info):
                if item not in ["metadata", "uri", "album_art"]:
                    elements[item.capitalize()] = track_info[item]

    # Remove blank and 'None' items
    elements = {
        key: value
        for key, value in elements.items()
        if value != "" and value is not None
    }

    # Deduplicate 'Channel' and 'Title'
    # Remove 'Title' if it contains no spaces (likely to be a URI or similar)
    try:
        if elements["Channel"] == elements["Title"] or not " " in elements["Title"]:
            elements.pop("Title", None)
    except KeyError:
        pass

    # Rename 'Playlist_position' and 'Position'
    try:
        elements["Playlist Position"] = elements["Playlist_position"]
        elements.pop("Playlist_position", None)
    except KeyError:
        pass
    try:
        elements["Elapsed"] = elements["Position"]
        elements.pop("Position", None)
    except KeyError:
        pass

    logging.info("Items to be printed: {}".format(elements))
    pretty_print_values(elements, indent=3, spacing=5, sort_by_key=True)
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


@zero_or_one_parameter
def shuffle(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        if speaker.shuffle is True:
            print("on")
        else:
            print("off")
    elif np == 1:
        if args[0].lower() == "on":
            speaker.shuffle = True
        elif args[0].lower() == "off":
            speaker.shuffle = False
        else:
            error_report("Action '{}' takes parameter 'on' or 'off'".format(action))
            return False
    return True


@zero_or_one_parameter
def repeat(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        if speaker.repeat is True:
            print("all")
        elif speaker.repeat is False:
            print("off")
        else:
            print("one")
    elif np == 1:
        if args[0].lower() in ["off", "none"]:
            speaker.repeat = False
        elif args[0].lower() == "one":
            speaker.repeat = "ONE"
        elif args[0].lower() == "all":
            speaker.repeat = True
        else:
            error_report(
                "Action '{}' takes parameter 'off', 'one', or 'all'".format(action)
            )
            return False
    return True


@zero_parameters
def transport_state(speaker, action, args, soco_function, use_local_speaker_list):
    print(speaker.get_current_transport_info()["current_transport_state"])
    return True


def play_favourite_core(speaker, favourite, favourite_number=None):
    """Core of the play_favourite action, but doesn't exit on failure"""

    fs = speaker.music_library.get_sonos_favorites(complete_result=True)

    if favourite_number:
        err_msg = "Favourite number must be integer between 1 and {}".format(len(fs))
        try:
            favourite_number = int(favourite_number)
        except ValueError:
            return False, err_msg
        if not 0 < favourite_number <= len(fs):
            return False, err_msg

        # List must be sorted by title to match the output of 'list_favourites'
        fs.sort(key=lambda x: x.title)
        the_fav = fs[favourite_number - 1]
        logging.info(
            "Favourite number {} is '{}'".format(favourite_number, the_fav.title)
        )

    else:
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
        # TODO: this is broken and we should test for the
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
        error_report(msg)
        return False

    return True


@one_parameter
def play_favourite_number(speaker, action, args, soco_function, use_local_speaker_list):
    logging.info("Playing favourite number {}".format(args[0]))
    result, msg = play_favourite_core(speaker, "", args[0])
    if not result:
        error_report(msg)
        return False

    return True


@one_or_two_parameters
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
        position = 0
        if len(args) == 2:
            position = 1
            if len(args) == 2:
                if args[1].lower() in ["first", "start"]:
                    position = 1
                elif args[1].lower() in ["play_next", "next"]:
                    current_position = speaker.get_current_track_info()[
                        "playlist_position"
                    ]
                    if current_position == "NOT_IMPLEMENTED":
                        position = 1
                    else:
                        position = int(current_position) + 1
                else:
                    error_report(
                        "Second parameter for '{}' must be 'next/play_next' or 'first/start'".format(
                            action
                        )
                    )
                    return False
        try:
            # Print the queue position and return
            print(speaker.add_to_queue(the_fav, position=position))
            return True
        except Exception as e:
            error_report("{}".format(str(e)))
            return False
    error_report("Favourite '{}' not found".format(args[0]))
    return False


@one_parameter
def play_favourite_radio_number(
    speaker, action, args, soco_function, use_local_speaker_list
):
    try:
        fav_no = int(args[0])
    except:
        parameter_type_error(action, "integer")
        return False

    logging.info("Playing favourite radio station no. {}".format(fav_no))

    preset = 0
    limit = 99
    stations = speaker.music_library.get_favorite_radio_stations(preset, limit)

    station_titles = sorted([s.title for s in stations])
    logging.info("Sorted station titles are: {}".format(station_titles))

    station_title = station_titles[fav_no - 1]
    logging.info("Requested station is '{}'".format(station_title))

    return play_favourite_radio(
        speaker, action, [station_title], soco_function, use_local_speaker_list
    )


@one_parameter
def play_favourite_radio(speaker, action, args, soco_function, use_local_speaker_list):
    favourite = args[0]
    preset = 0
    limit = 99
    fs = speaker.music_library.get_favorite_radio_stations(preset, limit)
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
        uri = the_fav.get_uri()
        meta_template = """
        <DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
            xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/"
            xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">
            <item id="R:0/0/0" parentID="R:0/0" restricted="true">
                <dc:title>{title}</dc:title>
                <upnp:class>object.item.audioItem.audioBroadcast</upnp:class>
                <desc id="cdudn" nameSpace="urn:schemas-rinconnetworks-com:metadata-1-0/">
                    {service}
                </desc>
            </item>
        </DIDL-Lite>' """
        tunein_service = "SA_RINCON65031_"
        uri = uri.replace("&", "&amp;")
        metadata = meta_template.format(title=the_fav.title, service=tunein_service)
        logging.info("Trying 'play_uri()': URI={}, Metadata={}".format(uri, metadata))
        speaker.play_uri(uri=uri, meta=metadata)
        return True

    error_report("Favourite '{}' not found".format(args[0]))
    return False


@one_or_two_parameters
def play_uri(speaker, action, args, soco_function, use_local_speaker_list):
    uri = args[0]
    title = "" if len(args) == 1 else args[1]
    for radio in [False, True]:
        try:
            speaker.play_uri(uri, title=title, force_radio=radio)
            return True
        except:
            continue

    error_report("Failed to play URI: '{}'".format(uri))
    return False


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
    speaker2 = get_speaker(args[0], use_local_speaker_list)
    if not speaker2:
        error_report("Speaker '{}' not found".format(args[0]))
        return False
    if speaker == speaker2:
        error_report("Speakers are the same")
        return False
    getattr(speaker, soco_function)(speaker2)
    return True


@zero_parameters
def operate_on_all(speaker, action, args, soco_function, use_local_speaker_list):
    zones = speaker.all_zones
    for zone in zones:
        if zone.is_visible:
            try:
                getattr(zone, soco_function)()
            except:
                # Ignore errors here; don't want to halt on
                # a failed pause (e.g., if speaker isn't playing)
                continue
    return True


@zero_parameters
def zones(speaker, action, args, soco_function, use_local_speaker_list):
    zones = speaker.all_zones if "all" in action else speaker.visible_zones
    count = 1
    for zone in zones:
        if 1 < count < len(zones) + 1:
            print(", ", end="")
        print('"{}"'.format(zone.player_name), end="")
        count += 1
    print()
    return True


@zero_or_one_parameter
def play_from_queue(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        speaker.play_from_queue(0)
    elif np == 1:
        try:
            # Play from current queue position?
            if args[0] in ["cp", "current", "current_position"]:
                index, _ = get_current_queue_position(speaker)
            else:
                index = int(args[0])
        except:
            parameter_type_error(action, "integer or 'cp' for current position")
            return False

        if 1 <= index <= speaker.queue_size:
            speaker.play_from_queue(index - 1)
        else:
            error_report("Queue index '{}' is out of range".format(index))
            return False
    return True


@one_parameter
def remove_from_queue(speaker, action, args, soco_function, use_local_speaker_list):
    # Generate a list that represents which tracks to remove, denoted by '0'
    # Initially mark each track as '1' (retain)
    queue = []
    for _ in range(speaker.queue_size):
        queue.append(1)
    # Catch exceptions at the end
    try:
        # Create a list of items to remove based on the input args
        # Mark these as '0'
        items = args[0].split(",")
        for index in items:
            # Check for a range ('x-y') instead of a single integer
            if "-" in index:
                rng = index.split("-")
                if len(rng) != 2:
                    parameter_type_error(
                        action, "two integers and a '-', e.g., '3-7' when using a range"
                    )
                    return False
                index_1 = int(rng[0])
                index_2 = int(rng[1])
                if index_1 < 1 or index_2 < 1:
                    raise IndexError
                if index_1 > index_2:
                    # Reverse the indices
                    index_2, index_1 = index_1, index_2
                for i in range(index_1 - 1, index_2):
                    queue[i] = 0
            else:
                index = int(index)
                if index < 1:
                    raise IndexError
                queue[index - 1] = 0
    # Exception handling
    # Catch any non-integer input values
    except ValueError:
        parameter_type_error(
            action,
            "integer, or comma-separated integers without spaces (e.g., 3,7,4)",
        )
        return False
    # Catch any out-of-range values
    except IndexError:
        error_report(
            "Queue index(es) must be between 1 and {} (inclusive)".format(len(queue))
        )
        return False
    # Walk though the list of tracks from position 1, removing items marked '0'
    # Account for the queue shift by keeping count of those deleted
    logging.info("Created map of queue items to delete (==0) {}".format(queue))
    # Note: do not switch the loop below to 'enumerate'. Yield behaviour breaks
    # the sequencing of requests to Sonos.
    # pylint: disable = consider-using-enumerate
    count_removed = 0
    for index in range(len(queue)):
        if queue[index] == 0:
            updated_index = index - count_removed
            speaker.remove_from_queue(updated_index)
            logging.info(
                "Removing queue item at (adjusted) index {}".format(updated_index + 1)
            )
            count_removed += 1
    return True


@zero_parameters
def remove_current_track_from_queue(
    speaker, action, args, soco_function, use_local_speaker_list
):
    if speaker.queue_size == 0:
        error_report("No tracks in queue")
        return False
    current_track = int(speaker.get_current_track_info()["playlist_position"])
    logging.info("Removing track {}".format(current_track))
    speaker.remove_from_queue(current_track - 1)
    return True


@zero_or_one_parameter
def remove_last_track_from_queue(
    speaker, action, args, soco_function, use_local_speaker_list
):
    queue_size = speaker.queue_size
    logging.info("Queue size is {}".format(queue_size))
    if queue_size == 0:
        error_report("No tracks in queue")
        return False
    if len(args) == 1:
        try:
            count = int(args[0])
        except ValueError:
            parameter_type_error(action, "an integer > 1")
        if not 1 <= count <= queue_size:
            error_report("parameter must be between 1 and {}".format(queue_size))
            return False
    else:
        count = 1
    logging.info("Removing the last {} tracks from the queue".format(count))
    while count > 0:
        logging.info("Removing track {}".format(queue_size))
        speaker.remove_from_queue(queue_size - 1)
        queue_size -= 1
        count -= 1
    return True


@one_parameter
def save_queue(speaker, action, args, soco_function, use_local_speaker_list):
    speaker.create_sonos_playlist_from_queue(args[0])
    return True


@one_parameter
def seek(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        seconds = convert_to_seconds(args[0])
    except ValueError:
        parameter_type_error(action, "a valid time format")
        return False
    if seconds < 0:
        parameter_type_error(action, "cannot seek to before start of track")
        return False
    seek_point = str(timedelta(seconds=seconds))
    logging.info("Seek point is {}".format(seek_point))
    try:
        # seek() will handle out-of-bounds
        speaker.seek(seek_point)
    except:
        parameter_type_error(action, "valid time value on a seekable source")
        return False
    return True


@one_parameter
def seek_forward(speaker, action, args, soco_function, use_local_speaker_list):
    # Calculate the time increment
    increment = int(convert_to_seconds(args[0]))  # Integer number of seconds
    if increment < 0:
        parameter_type_error(action, "a positive time increment")
        return False
    logging.info("Seeking forward by {}s".format(increment))

    # Get the current position
    current_position = speaker.get_current_track_info()["position"]
    logging.info("Current playback position is '{}'".format(current_position))
    h, m, s = [int(s) for s in current_position.split(":")]

    td_current = timedelta(hours=h, minutes=m, seconds=s)
    td_increment = timedelta(seconds=increment)
    td_new_str = str(td_current + td_increment)
    logging.info(
        "Seeking forward to position '{}' ... note: might hit end of track".format(
            td_new_str
        )
    )
    try:
        speaker.seek(td_new_str)
    except:
        parameter_type_error(action, "time increment on a seekable source")
        return False
    return True


@one_parameter
def seek_back(speaker, action, args, soco_function, use_local_speaker_list):
    # Calculate the time increment
    increment = int(convert_to_seconds(args[0]))  # Integer number of seconds
    if increment < 0:
        parameter_type_error(action, "a positive time increment")
        return False
    logging.info("Seeking backward by {}s".format(increment))

    # Get the current position
    current_position = speaker.get_current_track_info()["position"]
    logging.info("Current playback position is '{}'".format(current_position))
    h, m, s = [int(s) for s in current_position.split(":")]

    td_current = timedelta(hours=h, minutes=m, seconds=s)
    td_increment = timedelta(seconds=increment)
    if td_current - td_increment < timedelta():
        logging.info("Cannot seek beyond start of track ... seek to start instead")
        td_new_str = "00:00:00"
    else:
        td_new_str = str(td_current - td_increment)
    logging.info("Seeking backward to position '{}'".format(td_new_str))
    try:
        speaker.seek(td_new_str)
    except:
        parameter_type_error(action, "time increment on a seekable source")
        return False
    return True


@one_or_two_parameters
def playlist_operations(speaker, action, args, soco_function, use_local_speaker_list):
    name = args[0]
    if soco_function == "create_sonos_playlist":
        getattr(speaker, soco_function)(name)
        return True
    if soco_function == "add_uri_to_queue":
        getattr(speaker, soco_function)(name)
        return True

    playlist = None
    if soco_function == "add_to_queue":
        playlist = get_playlist(speaker, name)
    elif soco_function == "add_library_playlist_to_queue":
        playlist = get_playlist(speaker, name, library=True)

    if playlist is not None:
        if soco_function in ["add_to_queue", "add_library_playlist_to_queue"]:
            position = 0
            if len(args) == 2:
                position = 1
                if len(args) == 2:
                    if args[1].lower() in ["first", "start"]:
                        position = 1
                    elif args[1].lower() in ["play_next", "next"]:
                        current_position = speaker.get_current_track_info()[
                            "playlist_position"
                        ]
                        if current_position == "NOT_IMPLEMENTED":
                            position = 1
                        else:
                            position = int(current_position) + 1
                    else:
                        error_report(
                            "Second parameter for '{}' must be 'next/play_next' or 'first/start'".format(
                                action
                            )
                        )
                        return False

            result = speaker.add_to_queue(playlist, position=position)
            print(result)
        else:
            getattr(speaker, soco_function)(playlist)
    else:
        error_report("Playlist '{}' not found".format(args[0]))
        return False
    return True


@one_parameter
def list_playlist_tracks(speaker, action, args, soco_function, use_local_speaker_list):
    playlist = get_playlist(speaker, args[0])
    if playlist:
        print()
        print_list_header("Sonos Playlist:", playlist.title)
        tracks = speaker.music_library.browse_by_idstring(
            "sonos_playlists", playlist.item_id, max_items=SONOS_MAX_ITEMS
        )
        print_tracks(tracks)
        print()
        save_search(tracks)
        return True

    error_report("Playlist '{}' not found".format(args[0]))
    return False


@one_parameter
def list_library_playlist_tracks(
    speaker, action, args, soco_function, use_local_speaker_list
):
    playlist = get_playlist(speaker, args[0], library=True)
    if playlist:
        print()
        print_list_header("Library Playlist:", playlist.title)
        tracks = speaker.music_library.browse_by_idstring(
            "playlists", playlist.item_id, max_items=SONOS_MAX_ITEMS
        )
        print_tracks(tracks)
        print()
        save_search(tracks)
        return True

    error_report("Playlist '{}' not found".format(args[0]))
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

    error_report("Playlist '{}' not found".format(args[0]))
    return False


@zero_one_or_two_parameters
def line_in(speaker, action, args, soco_function, use_local_speaker_list):
    np = len(args)
    if np == 0:
        state = "on" if speaker.is_playing_line_in else "off"
        print(state)
    else:
        source = args[0]
        if source.lower() == "off":
            speaker.stop()
        elif source.lower() in ["on", "left_input"]:
            # Switch to the speaker's own line_in
            logging.info("Switching to the speaker's own Line-In")
            speaker.switch_to_line_in()
            speaker.play()
        else:
            line_in_source = None
            if source.lower() == "right_input":
                # We want the right-hand speaker of the stereo pair
                logging.info("Looking for right-hand speaker")
                line_in_source = get_right_hand_speaker(speaker)
            else:
                # We want to use another speaker's input
                if np == 2:  # Want to select the input of a stereo pair
                    the_input = args[1].lower()
                    if the_input == "right_input":
                        logging.info("Using right-hand speaker's input")
                        logging.info("Looking for right-hand speaker")
                        left_speaker = get_speaker(source, use_local_speaker_list)
                        line_in_source = get_right_hand_speaker(left_speaker)
                    elif the_input == "left_input":
                        logging.info("Using left-hand speaker's input")
                        line_in_source = get_speaker(source, use_local_speaker_list)
                    else:
                        parameter_type_error(
                            action,
                            "second parameter (if present) must be 'left_input' or 'right_input'",
                        )
                        return False
                else:
                    logging.info("Using left-hand speaker's input")
                    line_in_source = get_speaker(source, use_local_speaker_list)
            if not line_in_source:
                error_report("Speaker or input '{}' not found".format(source))
                return False
            logging.info("Switching to Line-In and starting playback")
            speaker.switch_to_line_in(line_in_source)
            speaker.play()
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


@one_parameter
def eq_relative(speaker, action, args, soco_function, use_local_speaker_list):
    """Set an EQ value by a relative amount"""
    try:
        delta = int(args[0])
    except:
        parameter_type_error(action, "integer from -10 to 10")
        return False
    current = getattr(speaker, soco_function)
    new_value = current + delta
    new_value = -10 if new_value < -10 else 10 if new_value > 10 else new_value
    logging.info("Requested delta = '{}', new_value = '{}'".format(delta, new_value))
    setattr(speaker, soco_function, new_value)
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
        info["title"] = speaker.get_current_track_info()["title"]
        info["player_name"] = speaker.player_name
        info["ip_address"] = speaker.ip_address
        info["household_id"] = speaker.household_id
        info["status_light"] = speaker.status_light
        info["is_coordinator"] = speaker.is_coordinator
        info["grouped_or_paired"] = len(speaker.group.members) > 1
        info["loudness"] = speaker.loudness
        info["treble"] = speaker.treble
        info["bass"] = speaker.bass
        info["is_coordinator"] = speaker.is_coordinator
        if speaker.is_coordinator:
            info["cross_fade"] = speaker.cross_fade
            info["state"] = speaker.get_current_transport_info()[
                "current_transport_state"
            ]
        else:
            info["cross_fade"] = speaker.group.coordinator.cross_fade
            info["state"] = speaker.group.coordinator.get_current_transport_info()[
                "current_transport_state"
            ]
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
            print("{}: ".format(group.coordinator.player_name), end="")
            first = True
            for member in group.members:
                if member != group.coordinator:
                    if member.is_visible:
                        if not first:
                            print(", ", end="")
                        print("{}".format(member.player_name), end="")
                        first = False
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
                alarm.alarm_id,
                alarm.zone.player_name,
                time,
                duration,
                alarm.recurrence,
                convert_true_false(alarm.enabled),
                title,
                alarm.play_mode,
                alarm.volume,
                convert_true_false(alarm.include_linked_zones),
            ]
        )
    headers = [
        "Alarm ID",
        "Speaker",
        "Start Time",
        "Duration",
        "Recurrence",
        "Enabled",
        "Title",
        "Play Mode",
        "Vol.",
        "Incl. Grouped",
    ]
    print()
    print(
        tabulate.tabulate(sorted(details), headers, tablefmt="github", numalign="left")
    )
    print()
    return True


@one_parameter
def remove_alarms(speaker, action, args, soco_function, use_local_speaker_list):

    alarms = soco.alarms.get_alarms(speaker)

    if args[0].lower() == "all":
        for alarm in alarms:
            logging.info("Removing alarm ID '{}'".format(alarm.alarm_id))
            alarm.remove()
        return True

    alarm_ids_to_delete = args[0].split(",")
    alarm_ids_to_delete = set(alarm_ids_to_delete)
    logging.info("Attempting to delete alarm ID(s): {}".format(alarm_ids_to_delete))

    alarm_ids = {alarm.alarm_id for alarm in alarms}
    logging.info("Current alarm ID(s): {}".format(alarm_ids))

    valid_alarm_ids_to_delete = alarm_ids.intersection(alarm_ids_to_delete)
    logging.info("Valid alarm ID(s) to delete: {}".format(valid_alarm_ids_to_delete))

    for alarm in alarms:
        if alarm.alarm_id in valid_alarm_ids_to_delete:
            logging.info("Deleting alarm ID: {}".format(alarm.alarm_id))
            alarm.remove()

    alarms_invalid = alarm_ids_to_delete.difference(valid_alarm_ids_to_delete)
    if len(alarms_invalid) != 0:
        print("Error: Alarm ID(s) {} not found".format(alarms_invalid))

    return True


@one_parameter
def add_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    alarm_parameters = args[0].split(",")
    if len(alarm_parameters) != 8:
        error_report("8 comma-separated parameters must be supplied")
        return False

    start_time = alarm_parameters[0]
    try:
        start_time = datetime.strptime(start_time, "%H:%M").time()
    except ValueError:
        error_report("Invalid time format: {}".format(start_time))
        return False

    duration = alarm_parameters[1]
    try:
        duration = datetime.strptime(duration, "%H:%M").time()
    except ValueError:
        error_report("Invalid time format: {}".format(duration))
        return False

    recurrence = alarm_parameters[2]
    if not soco.alarms.is_valid_recurrence(recurrence):
        error_report("'{}' is not a valid recurrence string".format(recurrence))
        return False

    enabled = alarm_parameters[3].lower()
    if enabled in ["on", "yes"]:
        enabled = True
    elif enabled in ["off", "no"]:
        enabled = False
    else:
        error_report(
            "Alarm must be enabled 'on' or 'off', not '{}'".format(alarm_parameters[3])
        )
        return False

    uri = alarm_parameters[4]
    if uri.lower() == "chime":
        uri = None

    play_mode = alarm_parameters[5].upper()
    play_mode_options = [
        "NORMAL",
        "SHUFFLE_NOREPEAT",
        "SHUFFLE",
        "REPEAT_ALL",
        "REPEAT_ONE",
        "SHUFFLE_REPEAT_ONE",
    ]
    if play_mode not in play_mode_options:
        error_report(
            "Play mode is '{}', should be one of:\n  {}".format(
                alarm_parameters[5], play_mode_options
            )
        )
        return False

    volume = alarm_parameters[6]
    try:
        volume = int(volume)
        if not 0 <= volume <= 100:
            error_report(
                "Alarm volume must be between 0 and 100, not '{}'".format(
                    alarm_parameters[6]
                )
            )
            return False
    except ValueError:
        error_report(
            "Alarm volume must be an integer between 0 and 100, not '{}'".format(
                alarm_parameters[6]
            )
        )
        return False

    include_linked = alarm_parameters[7].lower()
    if include_linked in ["on", "yes"]:
        include_linked = True
    elif include_linked in ["off", "no"]:
        include_linked = False
    else:
        error_report(
            "Linked zones must be enabled 'on' or 'off', not '{}'".format(
                alarm_parameters[7]
            )
        )
        return False

    alarm = soco.alarms.Alarm(
        speaker,
        start_time=start_time,
        duration=duration,
        recurrence=recurrence,
        enabled=enabled,
        program_uri=uri,
        play_mode=play_mode,
        volume=volume,
        include_linked_zones=include_linked,
    )
    try:
        alarm.save()
    except soco.exceptions.SoCoUPnPException:
        error_report("Failed to create alarm")
        return False

    print("Alarm ID '{}' created".format(alarm.alarm_id))
    return True


@two_parameters
def modify_alarm(speaker, action, args, soco_function, use_local_speaker_list):

    alarm_ids = args[0].lower().split(",")
    all_alarms = soco.alarms.get_alarms(speaker)
    if alarm_ids[0] == "all":
        alarms = set(all_alarms)
    else:
        alarms = set()
        for alarm_id in alarm_ids:
            for alarm in all_alarms:
                if alarm_id == alarm.alarm_id:
                    alarms.add(alarm)
                    break
            else:
                print("Alarm ID '{}' not found".format(alarm_id))

    alarm_parameters = args[1].split(",")
    if len(alarm_parameters) != 8:
        error_report("8 comma-separated parameters must be supplied")
        return False

    for alarm in alarms:
        start_time = alarm_parameters[0]
        if not start_time == "_":
            try:
                alarm.start_time = datetime.strptime(start_time, "%H:%M").time()
            except ValueError:
                error_report("Invalid time format: {}".format(start_time))
                return False

        duration = alarm_parameters[1]
        if not duration == "_":
            try:
                alarm.duration = datetime.strptime(duration, "%H:%M").time()
            except ValueError:
                error_report("Invalid time format: {}".format(duration))
                return False

        recurrence = alarm_parameters[2]
        if not recurrence == "_":
            if not soco.alarms.is_valid_recurrence(recurrence):
                error_report("'{}' is not a valid recurrence string".format(recurrence))
                return False
            alarm.recurrence = recurrence

        enabled = alarm_parameters[3].lower()
        if not enabled == "_":
            if enabled in ["on", "yes"]:
                enabled = True
            elif enabled in ["off", "no"]:
                enabled = False
            else:
                error_report(
                    "Alarm must be enabled 'on' or 'off', not '{}'".format(
                        alarm_parameters[3]
                    )
                )
                return False
            alarm.enabled = enabled

        uri = alarm_parameters[4]
        if not uri == "_":
            if uri.lower() == "chime":
                uri = None
            alarm.program_uri = uri

        play_mode = alarm_parameters[5].upper()
        if not play_mode == "_":
            play_mode_options = [
                "NORMAL",
                "SHUFFLE_NOREPEAT",
                "SHUFFLE",
                "REPEAT_ALL",
                "REPEAT_ONE",
                "SHUFFLE_REPEAT_ONE",
            ]
            if play_mode not in play_mode_options:
                error_report(
                    "Play mode is '{}', should be one of:\n  {}".format(
                        alarm_parameters[5], play_mode_options
                    )
                )
                return False
            alarm.play_mode = play_mode

        volume = alarm_parameters[6]
        if not volume == "_":
            try:
                volume = int(volume)
                if not 0 <= volume <= 100:
                    error_report(
                        "Alarm volume must be between 0 and 100, not '{}'".format(
                            alarm_parameters[6]
                        )
                    )
                    return False
            except ValueError:
                error_report(
                    "Alarm volume must be an integer between 0 and 100, not '{}'".format(
                        alarm_parameters[6]
                    )
                )
                return False
            alarm.volume = volume

        include_linked = alarm_parameters[7].lower()
        if not include_linked == "_":
            if include_linked in ["on", "yes"]:
                include_linked = True
            elif include_linked in ["off", "no"]:
                include_linked = False
            else:
                error_report(
                    "Linked zones must be enabled 'on' or 'off', not '{}'".format(
                        alarm_parameters[7]
                    )
                )
                return False
            alarm.include_linked_zones = include_linked

        try:
            alarm.save()
        except soco.exceptions.SoCoUPnPException:
            error_report("Failed to modify alarm")
            return False

    return True


@one_parameter
def copy_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    """Copy an alarm to the target speaker."""
    return move_or_copy_alarm(speaker, args[0], copy=True)


@one_parameter
def move_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    """Move an alarm to the target speaker."""
    return move_or_copy_alarm(speaker, args[0], copy=False)


def move_or_copy_alarm(speaker, alarm_id, copy=True):
    alarms = soco.alarms.get_alarms(speaker)
    for alarm in alarms:
        if alarm_id == alarm.alarm_id:
            break
    else:
        error_report("Alarm ID '{}' not found".format(alarm_id))
        return False

    if alarm.zone == speaker:
        error_report("Cannot copy/move an alarm to the same speaker")
        return False

    alarm.zone = speaker
    if copy is True:
        alarm._alarm_id = None
    try:
        alarm.save()
    except soco.exceptions.SoCoUPnPException:
        error_report("Failed to copy/move alarm")
        return False

    if copy is True:
        print("Alarm ID '{}' created".format(alarm.alarm_id))

    return True


@one_parameter
def enable_alarms(speaker, action, args, soco_function, use_local_speaker_list):
    return set_alarms(speaker, args[0], enabled=True)


@one_parameter
def disable_alarms(speaker, action, args, soco_function, use_local_speaker_list):
    return set_alarms(speaker, args[0], enabled=False)


def set_alarms(speaker, alarm_ids, enabled=True):
    alarms = soco.alarms.get_alarms(speaker)
    alarm_ids = set(alarm_ids.lower().split(","))
    all_alarms = bool("all" in alarm_ids)
    if all_alarms:
        alarm_ids.discard("all")

    for alarm in alarms:
        if all_alarms is True or alarm.alarm_id in alarm_ids:
            logging.info(
                "Setting alarm id '{}' to enabled = {}".format(alarm.alarm_id, enabled)
            )
            if alarm.enabled != enabled:
                alarm.enabled = enabled
                alarm.save()
                if len(alarm_ids) != 0 or all_alarms:
                    # Allow alarm update time to quiesce if there are subsequent
                    # updates
                    time.sleep(1.0)
            alarm_ids.discard(alarm.alarm_id)

    if len(alarm_ids) != 0:
        print("Alarm IDs not found: {}".format(alarm_ids))

    return True


@one_parameter
def snooze_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    """Snooze an alarm that's currently playing"""

    duration = args[0].lower()

    # HH:MM:SS format
    h_m_s = duration.split(":")
    if len(h_m_s) == 3:
        try:
            if not (
                0 <= int(h_m_s[0]) <= 23
                and 0 <= int(h_m_s[1]) <= 59
                and 0 <= int(h_m_s[2]) <= 59
            ):
                raise ValueError
        except (ValueError, TypeError):
            logging.info("Invalid snooze duration: '{}'".format(args[0]))
            parameter_type_error(
                action,
                "A valid HH:MM:SS duration, or an integer number of minutes".format(
                    args[0]
                ),
            )
            return False

    # Simple 'Nm' or 'N' for N minutes of snooze
    else:
        try:
            duration = abs(int(duration.replace("m", "")))
            minutes = str(duration % 60).zfill(2)
            hours = str(int(duration / 60)).zfill(2)
            duration = hours + ":" + minutes + ":00"
        except ValueError:
            logging.info("Invalid snooze duration: '{}'".format(args[0]))
            parameter_type_error(
                action,
                "An integer number of minutes, or HH:MM:SS format",
            )
            return False

    logging.info("Sending snooze command using duration '{}'".format(duration))
    try:
        speaker.avTransport.SnoozeAlarm([("InstanceID", 0), ("Duration", duration)])
    except SoCoUPnPException as error:
        logging.info("Exception: {}".format(error))
        if error.error_code == "701":
            error_report("Can only snooze a playing alarm")
        elif error.error_code == "402":
            error_report("Invalid snooze duration: '{}'".format(duration))
        else:
            error_report("{}".format(error))
        return False

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


def wait_stop_core(speaker, not_paused=False):

    playing_states = ["PLAYING", "TRANSITIONING"]
    if not_paused:
        # Also treat 'paused' as a playing state
        playing_states.append("PAUSED_PLAYBACK")

    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
    except Exception as e:
        error_report("Exception {}".format(e))
        return False

    while True:
        try:
            event = sub.events.get(timeout=1.0)
            if event.variables["transport_state"] not in playing_states:
                logging.info(
                    "Speaker '{}' in state '{}'".format(
                        speaker.player_name, event.variables["transport_state"]
                    )
                )
                event_unsubscribe(sub)
                return True
        except Empty:
            pass


@zero_parameters
def wait_stop(speaker, action, args, soco_function, use_local_speaker_list):
    return wait_stop_core(speaker)


@zero_parameters
def wait_stop_not_pause(speaker, action, args, soco_function, use_local_speaker_list):
    return wait_stop_core(speaker, not_paused=True)


def wait_stopped_for_core(speaker, action, duration_arg, not_paused=False):
    try:
        duration = convert_to_seconds(duration_arg)
    except ValueError:
        parameter_type_error(action, "Time h/m/s or HH:MM:SS")

    logging.info("Waiting until playback stopped for {}s".format(duration))

    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
    except Exception as e:
        error_report("Exception {}".format(e))
        return False

    playing_states = ["PLAYING", "TRANSITIONING"]
    if not_paused:
        # Also treat 'paused' as a playing state
        playing_states.append("PAUSED_PLAYBACK")

    while True:
        try:
            # TODO: Remove temporary fix for CTRL-C not exiting
            set_sigterm(True)
            event = sub.events.get(timeout=1.0)
            logging.info(
                "Event received: transport_state = '{}'".format(
                    event.variables["transport_state"]
                )
            )
            if event.variables["transport_state"] not in playing_states:
                logging.info("Speaker is not in states {}".format(playing_states))
                event_unsubscribe(sub)
                # TODO: Should really return here and do this some other way ...
                #       this is what's requiring the SIGKILL

                # Poll for changes; count down reset timer
                # TODO: Polling is not ideal; should be redesigned using events
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
                    if state in playing_states:
                        # Restart the timer
                        start_time = current_time
                    remaining_time = duration - (current_time - start_time)
                    logging.info(
                        "Elapsed since last 'STOPPED' = {}s | total elapsed = {}s | remaining = {}s".format(
                            int(current_time - start_time),
                            int(current_time - original_start_time),
                            int(remaining_time),
                        )
                    )
                    if remaining_time <= poll_interval:
                        time.sleep(remaining_time)
                    else:
                        time.sleep(poll_interval)
                    current_time = time.time()
                logging.info(
                    "Timer expired after 'STOPPED' for {}s | total elapsed = {}s".format(
                        int(current_time - start_time),
                        int(current_time - original_start_time),
                    )
                )
                set_sigterm(False)
                return True
        except:
            set_sigterm(False)


@one_parameter
def wait_stopped_for(speaker, action, args, soco_function, use_local_speaker_list):
    return wait_stopped_for_core(speaker, action, args[0], not_paused=False)


@one_parameter
def wait_stopped_for_not_pause(
    speaker, action, args, soco_function, use_local_speaker_list
):
    return wait_stopped_for_core(speaker, action, args[0], not_paused=True)


@zero_parameters
def wait_start(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
    except Exception as e:
        error_report("Exception {}".format(e))
        return False
    while True:
        try:
            event = sub.events.get(timeout=1.0)
            if event.variables["transport_state"] == "PLAYING":
                logging.info(
                    "Speaker '{}' in state '{}'".format(
                        speaker.player_name, event.variables["transport_state"]
                    )
                )
                event_unsubscribe(sub)
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
    albums = []
    for artist in artists:
        print()
        print_list_header("Sonos Music Library Albums including Artist:", artist.title)
        albums = ml.get_music_library_information(
            "artists", subcategories=[artist.title], max_items=SONOS_MAX_ITEMS
        )
        print_albums(albums, omit_first=True)  # Omit the first (empty) entry
        print()
        # TODO: Debating whether to include lists of all the tracks that feature the artist...
        # print_list_header("Sonos Music Library Tracks with Artist:", artist.title)
        # tracks = ml.search_track(artist.title)
        # # tracks = ml.get_music_library_information("artists", subcategories=[name, ""], complete_result=True)
        # print_tracks(tracks)
        # print()
    if len(artists) == 1:
        # Remove the first (redundant) element from the list before saving
        albums.pop(0)
        save_search(albums)
    elif len(artists) > 1:
        print("Note: multiple artists found ... search not saved\n")
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
    save_search(artists)
    return True


@one_parameter
def search_albums(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    albums = ml.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )
    if len(albums) > 0:
        print()
        print_list_header("Sonos Music Library Album Search:", name)
        print_albums(albums)
        print()
        save_search(albums)
    return True


@one_parameter
def search_tracks(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    tracks = ml.get_music_library_information(
        "tracks", search_term=name, complete_result=True
    )
    if len(tracks) > 0:
        print()
        print_list_header("Sonos Music Library Track Search:", name)
        print_tracks(tracks)
        print()
        save_search(tracks)
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
    albums = ml.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )
    logging.info("Found {} album(s) matching '{}'".format(len(albums), name))
    for album in albums:
        tracks = ml.get_music_library_information(
            "artists", subcategories=["", album.title], complete_result=True
        )
        print()
        print_list_header("Sonos Music Library Tracks in Album:", album.title)
        print_tracks(tracks)
        print()
        save_search(tracks)
    return True


def queue_item_core(speaker, action, args, info_type):
    name = args[0]
    items = speaker.music_library.get_music_library_information(
        info_type, search_term=name, complete_result=True
    )
    if len(items) > 0:
        position = 1
        if len(args) == 2:
            if args[1].lower() in ["first", "start"]:
                position = 1
            elif args[1].lower() in ["play_next", "next"]:
                current_position = speaker.get_current_track_info()["playlist_position"]
                if current_position == "NOT_IMPLEMENTED":
                    position = 1
                else:
                    position = int(current_position) + 1
            else:
                try:
                    position = int(args[1])
                    position = position if position > 0 else 1
                    position = position if position <= speaker.queue_size else 0
                except ValueError:
                    # Note that 'first/start' option is now redundant, but included
                    # here for backward compatibility
                    error_report(
                        "Second parameter for '{}' must be integer or 'next/play_next'".format(
                            action
                        )
                    )
                    return False
        # Select a random entry from the list, in case there's more than one
        item = items[randint(0, len(items) - 1)]
        print(speaker.add_to_queue(item, position=position))
        return True

    error_report("'{}' not found".format(name))
    return False


@one_or_two_parameters
def queue_album(speaker, action, args, soco_function, use_local_speaker_list):
    return queue_item_core(speaker, action, args, "albums")


@one_or_two_parameters
def queue_track(speaker, action, args, soco_function, use_local_speaker_list):
    return queue_item_core(speaker, action, args, "tracks")


@one_or_more_parameters
def if_stopped_or_playing(speaker, action, args, soco_function, use_local_speaker_list):
    """Perform the action only if the speaker is currently in the desired playback state"""
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

    action = args[0]
    args = args[1:]
    logging.info(
        "Action invoked: '{} {} {}'".format(speaker.player_name, action, " ".join(args))
    )
    return process_action(
        speaker, action, args, use_local_speaker_list=use_local_speaker_list
    )


@one_parameter
def cue_favourite(speaker, action, args, soco_function, use_local_speaker_list):
    """Shortcut to mute, play favourite, stop favourite, and unmute.
    Preserve the mute state
    """
    if not speaker.is_coordinator:
        error_report("Action '{}' can only be applied to a coordinator".format(action))
        return False
    unmute = False
    unmute_group = False
    if not speaker.mute:
        speaker.mute = True
        unmute = True
    if not speaker.group.mute:
        speaker.group.mute = True
        unmute_group = True
    if action in ["cfrs", "cue_favourite_radio_station", "cue_favorite_radio_station"]:
        result = play_favourite_radio(
            speaker, action, args, soco_function, use_local_speaker_list
        )
        msg = ""
    else:
        result, msg = play_favourite_core(speaker, args[0])
    speaker.stop()
    if unmute:
        speaker.mute = False
    if unmute_group:
        speaker.group.mute = False
    if not result:
        error_report(msg)
        return False
    return True


@one_parameter
def transfer_playback(speaker, action, args, soco_function, use_local_speaker_list):
    """Transfer playback from one speaker to another, by grouping and ungrouping."""
    if not speaker.is_coordinator:
        error_report("Speaker '{}' is not a coordinator".format(speaker.player_name))
        return False
    speaker2 = get_speaker(args[0], use_local_speaker_list)
    if speaker == speaker2:
        error_report("Source and target speakers are the same")
        return False
    if speaker2:
        speaker2.join(speaker)
        speaker.unjoin()
        return True

    error_report("Speaker '{}' not found".format(args[0]))
    return False


@zero_parameters
def queue_position(speaker, action, args, soco_function, use_local_speaker_list):
    position, _ = get_current_queue_position(speaker)
    print(position)
    return True


@zero_parameters
def last_search(speaker, action, args, soco_function, use_local_speaker_list):
    items = read_search()
    if items:
        if len(items) > 0:
            print()
            print_list_header(
                "Sonos Music Library: Saved {} Search".format(
                    items.search_type.capitalize()
                ),
                "",
            )
            if items.search_type == "albums":
                print_albums(items)
            # 'artists' search_type is used for tracks when 'tracks_in_album' has
            #  been used for the search
            elif items.search_type in ["tracks", "artists", "browse"]:
                print_tracks(items)
            print()
    else:
        error_report("No saved search")
        return False
    return True


@one_or_two_parameters
def queue_search_result_number(
    speaker, action, args, soco_function, use_local_speaker_list
):
    try:
        saved_search_number = int(args[0])
    except ValueError:
        parameter_type_error(
            action, "An integer index from the previous search results"
        )
        return False
    items = read_search()
    if not items:
        error_report("No saved search")
        return False
    logging.info("Loaded saved search")
    position = 0
    if len(args) == 2:
        if args[1].lower() in ["play_next", "next"]:
            # Check if currently playing from the queue
            # If so, add at the next track position
            if (
                speaker.get_current_transport_info()["current_transport_state"]
                == "PLAYING"  # noqa: W503
                and speaker.get_current_track_info()["position"]  # noqa: W503
                != "NOT_IMPLEMENTED"  # noqa: W503
            ):
                logging.info("Currently playing from queue; add as next track")
                offset = 1
            # Otherwise use the current position
            else:
                logging.info("Not currently playing; add at current queue position")
                offset = 0
            position = (
                int(speaker.get_current_track_info()["playlist_position"]) + offset
            )
        elif args[1].lower() in ["first", "start"]:
            position = 1
        else:
            error_report(
                "Second parameter for '{}' must be 'next/play_next' or 'first/start'".format(
                    action
                )
            )
            return False
    # Select the item number from the saved search
    if 1 <= saved_search_number <= len(items):
        item = items[saved_search_number - 1]
        print(speaker.add_to_queue(item, position=position))
        return True

    error_report("Item search index must be between 1 and {}".format(len(items)))
    return False


def cue_favourite_radio_station(
    speaker, action, args, soco_function, use_local_speaker_list
):
    return cue_favourite(speaker, action, args, soco_function, use_local_speaker_list)


@zero_parameters
def battery(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        battery_status = speaker.get_battery_info()
    except NotSupportedException:
        error_report("Battery status not supported by '{}'".format(speaker.player_name))
        return False
    except:
        error_report("Unable to retrieve battery status")
        return False

    for key, value in battery_status.items():
        if key == "Level":
            value = str(value) + "%"
        print("  " + key + ": " + str(value))

    return True


@one_parameter
def rename(speaker, action, args, soco_function, use_local_speaker_list):
    old_name = speaker.player_name
    new_name = args[0]
    if old_name == new_name:
        error_report("Current and new names are identical")
        return False
    speaker.player_name = new_name
    rename_speaker_in_cache(
        old_name, new_name, use_local_speaker_list=use_local_speaker_list
    )
    return True


@zero_parameters
def album_art(speaker, action, args, soco_function, use_local_speaker_list):
    """Get a URL for the current album art"""

    try:
        info = speaker.get_current_track_info()
        album_art_uri = info["album_art"]
        if album_art_uri == "":
            metadata = info["metadata"]
            data = parse(metadata)
            album_art_uri = data["DIDL-Lite"]["item"]["upnp:albumArtURI"]
        logging.info("Album art URI = ".format(album_art_uri))
    except:
        logging.info("No album art URI available")
        print("Album art not available")
        return True

    if not album_art_uri.lower().startswith("http"):
        print("Album art not accessible")
    else:
        print(album_art_uri)

    return True


@one_or_two_parameters
def add_uri_to_queue(speaker, action, args, soco_function, use_local_speaker_list):
    uri = args[0]
    position = 0
    if len(args) == 2:
        if args[1].lower() in ["first", "start"]:
            position = 1
        elif args[1].lower() in ["play_next", "next"]:
            current_position = speaker.get_current_track_info()["playlist_position"]
            if current_position == "NOT_IMPLEMENTED":
                position = 1
            else:
                position = int(current_position) + 1
        else:
            try:
                position = int(args[1])
                position = position if position > 0 else 1
                position = position if position <= speaker.queue_size else 0
            except ValueError:
                # Note that 'first/start' option is now redundant, but included
                # here for backward compatibility
                error_report(
                    "Second parameter for '{}' must be integer or 'next/play_next'".format(
                        action
                    )
                )
                return False

    print(speaker.add_uri_to_queue(uri, position=position))
    return True


@one_or_more_parameters
def play_file(speaker, action, args, soco_function, use_local_speaker_list):
    for audio_file in args:
        result = play_local_file(speaker, audio_file)
        if not result:
            return False
    return True


@one_or_two_parameters
def play_m3u(speaker, action, args, soco_function, use_local_speaker_list):
    m3u_file = args[0]
    options = "" if len(args) == 1 else args[1]
    options = options.lower()

    play_m3u_file(speaker, m3u_file, options=options)
    return True


@zero_or_one_parameter
def buttons(speaker, action, args, soco_function, use_local_speaker_list):
    """Enable or disable a speaker's buttons"""
    np = len(args)
    if np == 0:
        state = "on" if speaker.buttons_enabled else "off"
        print(state)
    elif np == 1:
        arg = args[0].lower()
        if arg == "on":
            speaker.buttons_enabled = True
        elif arg == "off":
            speaker.buttons_enabled = False
        else:
            parameter_type_error(action, "on|off")
    return True


@zero_or_one_parameter
def fixed_volume(speaker, action, args, soco_function, use_local_speaker_list):
    """Enable or disable whether a Connect or Port has its Fixed Volume set"""
    np = len(args)
    if np == 0:
        state = "on" if speaker.fixed_volume else "off"
        print(state)
    elif np == 1:
        arg = args[0].lower()
        try:
            if arg == "on":
                speaker.fixed_volume = True
            elif arg == "off":
                speaker.fixed_volume = False
            else:
                parameter_type_error(action, "on|off")
        except:
            error_report(
                "Fixed Volume feature not supported by '{}'".format(speaker.player_name)
            )
            return False
    return True


@zero_or_one_parameter
def trueplay(speaker, action, args, soco_function, use_local_speaker_list):
    """Enable or disable whether a Trueplay profile is enabled"""
    np = len(args)
    if np == 0:
        state = "on" if speaker.trueplay else "off"
        print(state)
    elif np == 1:
        arg = args[0].lower()
        try:
            if arg == "on":
                speaker.trueplay = True
            elif arg == "off":
                speaker.trueplay = False
            else:
                parameter_type_error(action, "on|off")
        except:
            error_report(
                "No Trueplay profile available for '{}' (or Trueplay not supported)".format(
                    speaker.player_name
                )
            )
            return False
    return True


@zero_parameters
def groupstatus(speaker, action, args, soco_function, use_local_speaker_list):
    """Determine the grouped/paired/bonded status of a speaker."""

    visible_speakers = False
    invisible_speakers = False
    coordinator = None

    for grouped_speaker in speaker.group.members:
        if speaker is grouped_speaker:
            continue
        if grouped_speaker.is_visible:
            visible_speakers = True
        if not grouped_speaker.is_visible:
            invisible_speakers = True
        if grouped_speaker.is_coordinator:
            coordinator = grouped_speaker

    logging.info(
        "Visible = {}, Coordinator = {}, Speakers in Group = {}, Other Visible Speakers = {}, Other Invisible Speakers = {}".format(
            speaker.is_visible,
            speaker.is_coordinator,
            len(speaker.group.members),
            visible_speakers,
            invisible_speakers,
        )
    )

    if len(speaker.group.members) == 1:
        print("Standalone")

    if speaker.is_visible and speaker.is_coordinator and invisible_speakers:
        print("Paired or bonded, coordinator")

    if not speaker.is_visible:
        print(
            "Paired or bonded, not coordinator [coordinator = {} @ {}]".format(
                coordinator.player_name, coordinator.ip_address
            )
        )

    if speaker.is_visible and speaker.is_coordinator and visible_speakers:
        print("Grouped, coordinator")

    if speaker.is_visible and not speaker.is_coordinator:
        print(
            "Grouped, not coordinator [coordinator = {} @ {}]".format(
                coordinator.player_name, coordinator.ip_address
            )
        )

    return True


@zero_parameters
def pauseplay(speaker, action, args, soco_function, use_local_speaker_list):
    """Invert a STOPPED or PAUSED STATE."""

    state = speaker.get_current_transport_info()["current_transport_state"]
    logging.info("Speaker '{}' is in a '{}' state".format(speaker.player_name, state))

    if state in ["PLAYING"]:
        try:
            logging.info("Trying 'pause'")
            speaker.pause()
        except:
            logging.info("'Pause' failed ... using 'stop'")
            speaker.stop()

    elif state in ["STOPPED", "PAUSED_PLAYBACK"]:
        logging.info("Trying 'play'")
        speaker.play()

    return True


@zero_parameters
def available_actions(speaker, action, args, soco_function, use_local_speaker_list):
    """Determine the currently available playback control options."""
    print("Currently available playback actions: {}".format(speaker.available_actions))
    return True


@zero_parameters
def end_control_session(speaker, action, args, soco_function, use_local_speaker_list):
    """Ends a direct control session (e.g., Spotify Connect)."""
    try:
        speaker.end_direct_control_session()
    except SoCoUPnPException:
        error_report("Invalid operation")
        return False
    return True


@zero_parameters
def wait_end_track(speaker, action, args, soco_function, use_local_speaker_list):
    """Wait for the end of the current track, or until playback stops/pauses."""

    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
        logging.info(
            "Subscribing to transport events from {}".format(speaker.player_name)
        )
    except Exception as e:
        error_report("Exception {}".format(e))
        return False

    initial_title = None
    initial_duration = None
    initial_radio_show = None

    while True:
        try:
            event = sub.events.get(timeout=1.0)
            logging.info("Transport event received")

            # The code below didn't work; retain for possible future use
            # Consider using a countdown?
            #
            # info = speaker.get_current_track_info()
            # position = convert_to_seconds(info["position"])
            # duration = convert_to_seconds(info["duration"])
            # logging.info("Position = {}, duration = {}".format(position, duration))
            #
            # if duration - position == 0:
            #     logging.info("Track duration expired")
            #     event_unsubscribe(sub)
            #     return True

            if event.variables["transport_state"] not in ["PLAYING", "TRANSITIONING"]:
                logging.info("Speaker is not playing")
                event_unsubscribe(sub)
                return True

            if initial_title is None:
                track_info = speaker.get_current_track_info()
                initial_title = track_info.pop("title", None)
                initial_duration = track_info.pop("duration", None)
                try:
                    initial_radio_show = event.variables["current_track_meta_data"].radio_show
                except:
                    pass
                logging.info(
                    "Initial title = '{}', initial duration = '{}', initial radio show = '{}'".format(
                        initial_title, initial_duration, initial_radio_show
                    )
                )

            else:
                track_info = speaker.get_current_track_info()
                current_title = track_info.pop("title", None)
                current_duration = track_info.pop("duration", None)
                try:
                    current_radio_show = event.variables["current_track_meta_data"].radio_show
                except:
                    pass
                logging.info(
                    "Current title = '{}', current duration = '{}', current radio show = '{}'".format(
                        current_title, current_duration, current_radio_show
                    )
                )
                # Check whether track title or duration have changed
                if (
                    current_title != initial_title
                    or current_duration != initial_duration
                    or current_radio_show != initial_radio_show
                ):
                    logging.info("Track/show has changed")
                    logging.info("Unsubscribing from events")
                    event_unsubscribe(sub)
                    return True

        except Empty:
            pass


@zero_parameters
def get_uri(speaker, action, args, soco_function, use_local_speaker_list):
    track_info = speaker.get_current_track_info()
    print(track_info["uri"])
    return True


@zero_parameters
def get_channel(speaker, action, args, soco_function, use_local_speaker_list):
    media_info = speaker.get_current_media_info()
    print(media_info["channel"])
    return True


@one_parameter
def add_sharelink_to_queue(
    speaker, action, args, soco_function, use_local_speaker_list
):
    share_link = ShareLinkPlugin(speaker)
    uri = args[0]

    if not share_link.is_share_link(uri):
        error_report("Invalid sharelink: '{}'".format(uri))
        return False

    try:
        # Return the queue position of the first added item
        print(share_link.add_share_link_to_queue(uri))
    except SoCoUPnPException as e:
        error_report("Unable to add sharelink to queue: {}".format(e))
        return False

    return True


def process_action(speaker, action, args, use_local_speaker_list=False):
    sonos_function = actions.get(action, None)
    if sonos_function:
        if sonos_function.switch_to_coordinator:
            if not speaker.is_coordinator:
                speaker = speaker.group.coordinator
                logging.info(
                    "Switching to coordinator speaker '{}'".format(speaker.player_name)
                )
        return sonos_function.processing_function(
            speaker,
            action,
            args,
            sonos_function.soco_function,
            use_local_speaker_list,
        )
    return False


class SonosFunction:
    """Maps actions into processing functions."""

    def __init__(self, function, soco_function=None, switch_to_coordinator=False):
        self._function = function
        self._soco_function = soco_function
        self._switch_to_coordinator = switch_to_coordinator

    @property
    def processing_function(self):
        return self._function

    @property
    def soco_function(self):
        return self._soco_function

    @property
    def switch_to_coordinator(self):
        return self._switch_to_coordinator


def get_actions(include_additional=True):
    action_list = list(actions.keys())
    if include_additional:
        additional_commands = [
            "loop",
            "loop_until",
            "loop_for",
            "loop_to_start",
            "track_follow",
            "wait_until",
            "wait",
            "wait_for",
        ]
        action_list = action_list + additional_commands
    return sorted(action_list)


def list_actions(include_additional=True):
    action_list = get_actions(include_additional=include_additional)
    action_list = sorted(action_list, reverse=True)

    longest_command = len(max(action_list, key=len))
    item_spacing = longest_command + 2
    items_per_line = get_terminal_size().columns // item_spacing

    current_line_position = 1
    while True:
        try:
            command = action_list.pop()
        except IndexError:
            break
        if current_line_position == items_per_line:
            ending = "\n"
            current_line_position = 1
        else:
            ending = " " * (item_spacing - len(command))
            current_line_position += 1
        print(command, end=ending)
    if current_line_position != 1:
        print()


# Actions and associated processing functions
actions = {
    "mute": SonosFunction(on_off_action, "mute"),
    "cross_fade": SonosFunction(on_off_action, "cross_fade"),
    "crossfade": SonosFunction(on_off_action, "cross_fade"),
    "fade": SonosFunction(on_off_action, "cross_fade"),
    "loudness": SonosFunction(on_off_action, "loudness"),
    "status_light": SonosFunction(on_off_action, "status_light"),
    "light": SonosFunction(on_off_action, "status_light"),
    "night_mode": SonosFunction(on_off_action, "night_mode"),
    "night": SonosFunction(on_off_action, "night_mode"),
    "dialog_mode": SonosFunction(on_off_action, "dialog_mode"),
    "dialog": SonosFunction(on_off_action, "dialog_mode"),
    "dialogue_mode": SonosFunction(on_off_action, "dialog_mode"),
    "dialogue": SonosFunction(on_off_action, "dialog_mode"),
    "play": SonosFunction(no_args_no_output, "play", True),
    "start": SonosFunction(no_args_no_output, "play", True),
    "stop": SonosFunction(no_args_no_output, "stop", True),
    "pause": SonosFunction(no_args_no_output, "pause", True),
    "next": SonosFunction(no_args_no_output, "next", True),
    "previous": SonosFunction(no_args_no_output, "previous", True),
    "prev": SonosFunction(no_args_no_output, "previous", True),
    "list_queue": SonosFunction(list_queue, "get_queue", True),
    "lq": SonosFunction(list_queue, "get_queue", True),
    "queue": SonosFunction(list_queue, "get_queue", True),
    "q": SonosFunction(list_queue, "get_queue", True),
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
    "track": SonosFunction(track, "", True),
    "play_mode": SonosFunction(playback_mode, "play_mode", True),
    "mode": SonosFunction(playback_mode, "play_mode", True),
    "playback_state": SonosFunction(
        transport_state, "get_current_transport_info", True
    ),
    "playback": SonosFunction(transport_state, "get_current_transport_info", True),
    "state": SonosFunction(transport_state, "get_current_transport_info", True),
    "status": SonosFunction(transport_state, "get_current_transport_info", True),
    "play_favourite": SonosFunction(play_favourite, "play_favorite", True),
    "play_favorite": SonosFunction(play_favourite, "play_favorite", True),
    "favourite": SonosFunction(play_favourite, "play_favorite", True),
    "favorite": SonosFunction(play_favourite, "play_favorite", True),
    "play_fav": SonosFunction(play_favourite, "play_favorite", True),
    "fav": SonosFunction(play_favourite, "play_favorite", True),
    "pf": SonosFunction(play_favourite, "play_favorite", True),
    "play_uri": SonosFunction(play_uri, "play_uri", True),
    "uri": SonosFunction(play_uri, "play_uri", True),
    "pu": SonosFunction(play_uri, "play_uri", True),
    "sleep_timer": SonosFunction(sleep_timer, "sleep_timer", True),
    "sleep": SonosFunction(sleep_timer, "sleep_timer", True),
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
    "play_from_queue": SonosFunction(play_from_queue, "play_from_queue", True),
    "play_queue": SonosFunction(play_from_queue, "play_from_queue", True),
    "pfq": SonosFunction(play_from_queue, "play_from_queue", True),
    "pq": SonosFunction(play_from_queue, "play_from_queue", True),
    "remove_from_queue": SonosFunction(remove_from_queue, "remove_from_queue", True),
    "rfq": SonosFunction(remove_from_queue, "remove_from_queue", True),
    "rq": SonosFunction(remove_from_queue, "remove_from_queue", True),
    "clear_queue": SonosFunction(no_args_no_output, "clear_queue", True),
    "cq": SonosFunction(no_args_no_output, "clear_queue", True),
    "group_mute": SonosFunction(on_off_action, "group_mute"),
    "save_queue": SonosFunction(save_queue, "create_sonos_playlist_from_queue", True),
    "sq": SonosFunction(save_queue, "create_sonos_playlist_from_queue", True),
    "create_playlist_from_queue": SonosFunction(
        save_queue, "create_sonos_playlist_from_queue", True
    ),
    "queue_length": SonosFunction(no_args_one_output, "queue_size", True),
    "ql": SonosFunction(no_args_one_output, "queue_size", True),
    "add_playlist_to_queue": SonosFunction(playlist_operations, "add_to_queue", True),
    "add_pl_to_queue": SonosFunction(playlist_operations, "add_to_queue", True),
    "queue_playlist": SonosFunction(playlist_operations, "add_to_queue", True),
    "apq": SonosFunction(playlist_operations, "add_to_queue", True),
    "pause_all": SonosFunction(operate_on_all, "pause"),
    "seek": SonosFunction(seek, "seek", True),
    "seek_to": SonosFunction(seek, "seek", True),
    "seek_forward": SonosFunction(seek_forward, "seek_forward", True),
    "sf": SonosFunction(seek_forward, "seek_forward", True),
    "seek_back": SonosFunction(seek_back, "seek_back", True),
    "sb": SonosFunction(seek_back, "seek_back", True),
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
    # "add_uri_to_queue": SonosFunction(playlist_operations, "add_uri_to_queue"),
    "auq": SonosFunction(playlist_operations, "add_uri_to_queue", True),
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
    "frs": SonosFunction(list_numbered_things, "get_favorite_radio_stations"),
    "lfrs": SonosFunction(list_numbered_things, "get_favorite_radio_stations"),
    "play_favourite_radio_station": SonosFunction(play_favourite_radio, "play_uri"),
    "play_favorite_radio_station": SonosFunction(play_favourite_radio, "play_uri"),
    "pfrs": SonosFunction(play_favourite_radio, "play_uri", True),
    # "tracks": SonosFunction(list_numbered_things, "get_tracks"),
    "alarms": SonosFunction(list_alarms, "get_alarms"),
    "list_alarms": SonosFunction(list_alarms, "get_alarms"),
    "libraries": SonosFunction(list_libraries, "list_library_shares"),
    "shares": SonosFunction(list_libraries, "list_library_shares"),
    "sysinfo": SonosFunction(system_info, ""),
    "sleep_at": SonosFunction(sleep_at, "", True),
    "add_favourite_to_queue": SonosFunction(
        add_favourite_to_queue, "add_to_queue", True
    ),
    "add_favorite_to_queue": SonosFunction(
        add_favourite_to_queue, "add_to_queue", True
    ),
    "add_fav_to_queue": SonosFunction(add_favourite_to_queue, "add_to_queue", True),
    "afq": SonosFunction(add_favourite_to_queue, "add_to_queue", True),
    "list_playlist_tracks": SonosFunction(list_playlist_tracks, "list_tracks"),
    "lpt": SonosFunction(list_playlist_tracks, "list_tracks"),
    "list_all_playlist_tracks": SonosFunction(list_all_playlist_tracks, ""),
    "lapt": SonosFunction(list_all_playlist_tracks, ""),
    "wait_stop": SonosFunction(wait_stop, "", True),
    "wait_start": SonosFunction(wait_start, "", True),
    "wait_stopped_for": SonosFunction(wait_stopped_for, "", True),
    "wsf": SonosFunction(wait_stopped_for, "", True),
    "if_stopped": SonosFunction(if_stopped_or_playing, "", True),
    "if_playing": SonosFunction(if_stopped_or_playing, "", True),
    "search_library": SonosFunction(search_library, ""),
    "sl": SonosFunction(search_library, ""),
    "search_artists": SonosFunction(search_artists, ""),
    "search_artist": SonosFunction(search_artists, ""),
    "sart": SonosFunction(search_artists, ""),
    "search_albums": SonosFunction(search_albums, ""),
    "search_album": SonosFunction(search_albums, ""),
    "salb": SonosFunction(search_albums, ""),
    "search_tracks": SonosFunction(search_tracks, ""),
    "search_track": SonosFunction(search_tracks, ""),
    "st": SonosFunction(search_tracks, ""),
    "tracks_in_album": SonosFunction(tracks_in_album, ""),
    "tia": SonosFunction(tracks_in_album, ""),
    "lta": SonosFunction(tracks_in_album, ""),
    "list_albums": SonosFunction(list_albums, ""),
    "albums": SonosFunction(list_albums, ""),
    "list_artists": SonosFunction(list_artists, ""),
    "artists": SonosFunction(list_artists, ""),
    "queue_album": SonosFunction(queue_album, "", True),
    "qa": SonosFunction(queue_album, "", True),
    "queue_track": SonosFunction(queue_track, "", True),
    "qt": SonosFunction(queue_track, "", True),
    "cue_favourite": SonosFunction(cue_favourite, "", True),
    "cue_favorite": SonosFunction(cue_favourite, "", True),
    "cue_fav": SonosFunction(cue_favourite, "", True),
    "cf": SonosFunction(cue_favourite, "", True),
    "transfer_playback": SonosFunction(transfer_playback, "", True),
    "transfer_to": SonosFunction(transfer_playback, "", True),
    "transfer": SonosFunction(transfer_playback, "", True),
    "shuffle": SonosFunction(shuffle, "", True),
    "sh": SonosFunction(shuffle, "", True),
    "repeat": SonosFunction(repeat, "", True),
    "rpt": SonosFunction(repeat, "", True),
    "remove_current_track_from_queue": SonosFunction(
        remove_current_track_from_queue, "", True
    ),
    "rctfq": SonosFunction(remove_current_track_from_queue, "", True),
    "remove_last_track_from_queue": SonosFunction(
        remove_last_track_from_queue, "", True
    ),
    "rltfq": SonosFunction(remove_last_track_from_queue, "", True),
    "queue_position": SonosFunction(queue_position, "", True),
    "qp": SonosFunction(queue_position, "", True),
    "last_search": SonosFunction(last_search, "", True),
    "ls": SonosFunction(last_search, ""),
    "queue_search_result_number": SonosFunction(queue_search_result_number, "", True),
    "queue_search_number": SonosFunction(queue_search_result_number, "", True),
    "qsn": SonosFunction(queue_search_result_number, "", True),
    "cue_favourite_radio_station": SonosFunction(cue_favourite_radio_station, "", True),
    "cue_favorite_radio_station": SonosFunction(cue_favourite_radio_station, "", True),
    "cfrs": SonosFunction(cue_favourite_radio_station, "", True),
    "battery": SonosFunction(battery, ""),
    "rename": SonosFunction(rename, ""),
    "play_file": SonosFunction(play_file, "", True),
    "play_local_file": SonosFunction(play_file, "", True),
    "play_m3u": SonosFunction(play_m3u, "", True),
    "play_local_m3u": SonosFunction(play_m3u, "", True),
    "add_uri_to_queue": SonosFunction(add_uri_to_queue, "", True),
    "wait_stop_not_pause": SonosFunction(wait_stop_not_pause, "", True),
    "wsnp": SonosFunction(wait_stop_not_pause, "", True),
    "wait_stopped_for_not_pause": SonosFunction(wait_stopped_for_not_pause, "", True),
    "wsfnp": SonosFunction(wait_stopped_for_not_pause, "", True),
    "buttons": SonosFunction(buttons, ""),
    "fixed_volume": SonosFunction(fixed_volume, ""),
    "trueplay": SonosFunction(trueplay, ""),
    "play_favourite_number": SonosFunction(play_favourite_number, "", True),
    "play_favorite_number": SonosFunction(play_favourite_number, "", True),
    "pfn": SonosFunction(play_favourite_number, "", True),
    "play_fav_radio_station_no": SonosFunction(play_favourite_radio_number, "", True),
    "pfrsn": SonosFunction(play_favourite_radio_number, "", True),
    "album_art": SonosFunction(album_art, "", True),
    "groupstatus": SonosFunction(groupstatus),
    "pauseplay": SonosFunction(pauseplay, "", True),
    "playpause": SonosFunction(pauseplay, "", True),
    "available_actions": SonosFunction(available_actions, "", True),
    "wait_end_track": SonosFunction(wait_end_track, "", True),
    "remove_alarms": SonosFunction(remove_alarms, "", False),
    "remove_alarm": SonosFunction(remove_alarms, "", False),
    "add_alarm": SonosFunction(add_alarm, "", False),
    "create_alarm": SonosFunction(add_alarm, "", False),
    "enable_alarm": SonosFunction(enable_alarms, "", False),
    "enable_alarms": SonosFunction(enable_alarms, "", False),
    "disable_alarm": SonosFunction(disable_alarms, "", False),
    "disable_alarms": SonosFunction(disable_alarms, "", False),
    "modify_alarm": SonosFunction(modify_alarm, "", False),
    "modify_alarms": SonosFunction(modify_alarm, "", False),
    "copy_alarm": SonosFunction(copy_alarm, "", False),
    "move_alarm": SonosFunction(move_alarm, "", False),
    "snooze_alarm": SonosFunction(snooze_alarm, "", True),
    "relative_bass": SonosFunction(eq_relative, "bass", False),
    "rb": SonosFunction(eq_relative, "bass", False),
    "relative_treble": SonosFunction(eq_relative, "treble", False),
    "rt": SonosFunction(eq_relative, "treble", False),
    "list_library_playlists": SonosFunction(
        list_numbered_things, "get_playlists", False
    ),
    "llp": SonosFunction(list_numbered_things, "get_playlists", False),
    "list_library_playlist_tracks": SonosFunction(
        list_library_playlist_tracks, "", False
    ),
    "llpt": SonosFunction(list_library_playlist_tracks, "", False),
    "add_library_playlist_to_queue": SonosFunction(
        playlist_operations, "add_library_playlist_to_queue", True
    ),
    "alpq": SonosFunction(playlist_operations, "add_library_playlist_to_queue", True),
    "get_uri": SonosFunction(get_uri, "", True),
    "end_session": SonosFunction(end_control_session, "", True),
    "get_channel": SonosFunction(get_channel, "", True),
    "channel": SonosFunction(get_channel, "", True),
    "add_sharelink_to_queue": SonosFunction(add_sharelink_to_queue, "", True),
    "sharelink": SonosFunction(add_sharelink_to_queue, "", True),
}
