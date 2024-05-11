"""The main command processing module.

This module requires refactoring, improvements to its argument handling,
and needs to be converted to a Class.
"""

import logging
import pprint
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from os import get_terminal_size
from random import randint

import soco  # type: ignore
import tabulate  # type: ignore
from soco.exceptions import NotSupportedException, SoCoUPnPException  # type: ignore
from soco.plugins.sharelink import ShareLinkPlugin  # type: ignore
from xmltodict import parse  # type: ignore

from soco_cli import alarms
from soco_cli.play_local_file import play_local_file
from soco_cli.play_local_file_lists import play_directory_files, play_m3u_file
from soco_cli.speaker_info import print_speaker_table
from soco_cli.utils import (
    convert_to_seconds,
    create_list_of_items_from_range,
    error_report,
    event_unsubscribe,
    forget_event_sub,
    get_queue_insertion_position,
    get_right_hand_speaker,
    get_speaker,
    one_or_more_parameters,
    one_or_two_parameters,
    one_parameter,
    parameter_type_error,
    playback_state,
    pretty_print_values,
    read_search,
    remember_event_sub,
    rename_speaker_in_cache,
    save_queue_insertion_position,
    save_search,
    seconds_until,
    two_parameters,
    unsub_all_remembered_event_subs,
    zero_one_or_two_parameters,
    zero_or_one_parameter,
    zero_parameters,
)
from soco_cli.wait_actions import process_wait

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
        # Assemble available track data
        info_items = OrderedDict()
        try:
            info_items["Artist"] = track.creator
        except AttributeError:
            pass
        try:
            info_items["Album"] = track.album
        except AttributeError:
            pass
        try:
            info_items["Title"] = track.title
        except AttributeError:
            pass
        try:
            if track.item_class == "object.item.audioItem.podcast":
                info_items["Podcast Episode"] = info_items.pop("Title")
        except (AttributeError, KeyError):
            pass

        # Assemble the info string to be printed
        info_string = ""
        first = True
        for item, info in info_items.items():
            if first:
                first = False
            else:
                info_string += " | "
            info_string += "{}: {}".format(item, info)

        # Print the information; show position and play state if available
        prefix = "    "
        if qp == item_number:
            if is_playing:
                prefix = " *> "
            else:
                prefix = " *  "
        print("{}{:3d}: {}".format(prefix, item_number, info_string))

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
def true_false_action(speaker, action, args, soco_function, use_local_speaker_list):
    """Method to deal with status actions that have 'true|false semantics"""
    state = "yes" if getattr(speaker, soco_function) else "no"
    print(state)
    return True


@zero_parameters
def no_args_no_output(speaker, action, args, soco_function, use_local_speaker_list):
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
        # print("Queue is empty")
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
    if soco_function == "group_volume":
        logging.info("Using speaker group instead of speaker")
        speaker = speaker.group

    np = len(args)
    if np == 0:
        print(speaker.volume)
        return True
    if np == 1:
        try:
            vol = int(args[0])
            if not (0 <= vol <= 100):
                raise ValueError
        except ValueError:
            parameter_type_error(action, "integer 0 to 100")
            return False
        if soco_function == "ramp_to_volume":
            logging.info("Ramping to volume {}".format(vol))
            print(speaker.ramp_to_volume(vol))
        else:
            logging.info("Setting volume to {}".format(vol))
            speaker.volume = vol
        return True


@one_parameter
def relative_volume(speaker, action, args, soco_function, use_local_speaker_list):
    if soco_function == "group_relative_volume":
        logging.info("Using speaker group instead of speaker")
        speaker = speaker.group
    try:
        vol = int(args[0])
        if not -100 <= vol <= 100:
            raise ValueError
    except ValueError:
        parameter_type_error(action, "integer from -100 to 100")

    logging.info("Adjusting relative volume by {}".format(vol))
    speaker.set_relative_volume(vol)
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

    def title_not_useful(title):
        indicators = ["m3u", "stream", "sonos", "http", "=", "ZPSTR_"]
        for indicator in indicators:
            if indicator in title:
                return True
        return False

    stream = False

    print(" Playback is {}:".format(playback_state(state)))
    track_info = speaker.get_current_track_info()
    logging.info("Current track info:\n{}".format(track_info))

    # Accumulate info elements to be printed
    elements = {"Channel": speaker.get_current_media_info()["channel"]}

    # Stream
    if track_info["duration"] in ["0:00:00", "NOT_IMPLEMENTED"]:
        logging.info("Track is a radio stream")
        stream = True
        for item in sorted(track_info):
            if item not in [
                "metadata",
                "album_art",
                "duration",
                "playlist_position",
                # "position",
                "uri",
            ]:
                elements[item.capitalize()] = track_info[item]

        try:
            metadata = parse(track_info["metadata"])
            if elements["Artist"] == "":
                logging.info("Attempting to find 'Artist' from metadata")
                try:
                    elements["Artist"] = metadata["DIDL-Lite"]["item"]["dc:creator"]
                except:
                    logging.info("Unable to find 'Artist'")
            if elements["Title"] == "":
                logging.info("Attempting to find 'Title' from metadata")
                try:
                    elements["Title"] = metadata["DIDL-Lite"]["item"]["dc:title"]
                except:
                    logging.info("Unable to find 'Title'")
        except:
            pass

        try:
            logging.info("Attempting to find 'Radio Show' using events")
            sub = speaker.avTransport.subscribe()
            remember_event_sub(sub)
            event = sub.events.get(timeout=0.5)
            elements["Radio Show"] = event.variables[
                "current_track_meta_data"
            ].radio_show.rpartition(",")[0]
            event_unsubscribe(sub)
            forget_event_sub(sub)
        except Exception as e:
            logging.info("Unable to find 'Radio Show': {}".format(e))
        finally:
            unsub_all_remembered_event_subs()

    # Podcast, Audio Book, or normal track
    else:
        logging.info("Track has a non-zero duration")
        try:
            metadata = parse(track_info["metadata"])
            logging.info("Track metadata: {}".format(metadata))
        except:
            logging.info("No usable metadata available")
            metadata = None

        # Podcast
        if (
            metadata
            and metadata["DIDL-Lite"]["item"]["upnp:class"]
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
            try:
                elements["Episode"] = elements.pop("Title")
            except KeyError:
                pass

        # Audio book
        elif (
            metadata
            and "object.item.audioItem.audioBook"
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
            # If there's no title, look in the metadata
            try:
                if elements["Title"] == "" or title_not_useful(elements["Title"]):
                    metadata = parse(track_info["metadata"])
                    elements["Title"] = metadata["DIDL-Lite"]["item"]["dc:title"]
                    logging.info(
                        "Found title in metadata: {}".format(elements["Title"])
                    )
            except KeyError:
                pass

    # Remove blank and 'None' items
    elements = {
        key: value
        for key, value in elements.items()
        if value != "" and value is not None and value != "NOT_IMPLEMENTED"
    }

    # Deduplicate 'Channel' and 'Title'
    # Remove 'Title' if it looks unuseful
    try:
        if (elements["Channel"] == elements["Title"]) or (
            stream and title_not_useful(elements["Title"])
        ):
            logging.info("Removing Title: '{}'".format(elements["Title"]))
            elements.pop("Title", None)
    except KeyError:
        pass

    # Rename 'Playlist_position' and 'Position'
    try:
        if int(elements["Playlist_position"]) != 0:
            elements["Playlist Position"] = elements["Playlist_position"]
        elements.pop("Playlist_position", None)
    except KeyError:
        pass
    try:
        elements["Elapsed"] = elements["Position"]
        elements.pop("Position", None)
    except KeyError:
        pass

    # Reorder the elements
    element_order = [
        "Channel",
        "Radio Show",
        "Podcast",
        "Artist",
        "Creator(s)",
        "Narrator(s)",
        "Book Title",
        "Chapter",
        "Album",
        "Title",
        "Episode",
        "Release Date",
        "Playlist Position",
        "Duration",
        "Elapsed",
    ]
    ordered_elements = OrderedDict()
    for element in element_order:
        try:
            ordered_elements[element] = elements.pop(element)
        except KeyError:
            pass
    # Add any elements we've missed
    ordered_elements.update(elements)

    logging.info("Items to be printed: {}".format(ordered_elements))
    pretty_print_values(ordered_elements, indent=3, spacing=5, sort_by_key=False)
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
        if len(args) == 2:
            position = get_queue_insertion_position(speaker, args[1], action)
        else:
            position = speaker.queue_size + 1
        try:
            # Print the queue position and return
            speaker.add_to_queue(the_fav, position=position)
            save_queue_insertion_position(position)
            print(position)
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
        if st is not None:
            time_now = datetime.now()
            remaining_seconds = timedelta(0, st)
            expiry_time = time_now + remaining_seconds
            print(
                "Sleep timer expires in {} at {}".format(
                    remaining_seconds, expiry_time.strftime("%H:%M")
                )
            )
        else:
            print("0 (No sleep timer set)")
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
    logging.info(
        "Executing '{}' on speakers '{}', '{}'".format(
            soco_function, speaker.player_name, speaker2.player_name
        )
    )
    getattr(speaker, soco_function)(speaker2)
    return True


@one_or_more_parameters
def multi_group(speaker, action, args, soco_function, use_local_speaker_list):
    """
    Group one or more speakers with a coordinator speaker. Note: reverses the usual
    order; the target speaker is the coordinator, not the speaker to be grouped.
    """
    logging.info("Grouping speakers '{}' with '{}'".format(args, speaker.player_name))
    for speaker_name in args:
        target_speaker = get_speaker(speaker_name, use_local_speaker_list)
        if not target_speaker:
            error_report("Speaker '{}' not found".format(speaker_name))
            continue
        logging.info(
            "Grouping speaker '{}' with coordinator '{}'".format(
                target_speaker.player_name, speaker.player_name
            )
        )
        group_or_pair(
            target_speaker,
            action,
            [speaker.player_name],
            soco_function,
            use_local_speaker_list,
        )
    return True


@zero_parameters
def operate_on_all(speaker, action, args, soco_function, use_local_speaker_list):
    zones = speaker.all_zones
    for zone in zones:
        if zone.is_visible:
            try:
                logging.info(
                    "Executing '{}' on speaker '{}'".format(
                        soco_function, zone.player_name
                    )
                )
                getattr(zone, soco_function)()
            except:
                logging.info("Operation failed ... continuing")
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
        return True
    if args[0] in ["current", "cp", "current_position"]:
        index, _ = get_current_queue_position(speaker)
    elif args[0] in ["last", "lp", "last_position"]:
        index = len(speaker.get_queue(max_items=SONOS_MAX_ITEMS))
    elif args[0] in ["random", "rand", "r"]:
        index = randint(1, len(speaker.get_queue(max_items=SONOS_MAX_ITEMS)))
    elif args[0] in ["last_added", "la"]:
        try:
            index = get_queue_insertion_position()
        except Exception as e:
            error_report("No saved queue position: {}".format(e))
            return False
    else:
        try:
            index = int(args[0])
        except ValueError:
            parameter_type_error(
                action,
                "integer, 'current', 'last', or 'random'",
            )
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
    if speaker.queue_size == 0:
        error_report("Queue is empty")
        return False
    queue = []
    for _ in range(speaker.queue_size):
        queue.append(1)
    # Catch exceptions at the end
    # Note: this can be refactored using utils.create_list_of_items_from_range()
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
        error_report("Queue is empty")
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
        error_report("Queue is empty")
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
    if speaker.queue_size == 0:
        error_report("Queue is empty")
        return False
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

    if soco_function == "remove_sonos_playlist":
        try:
            playlist = get_playlist(speaker, name)
            speaker.remove_sonos_playlist(playlist)
        except SoCoUPnPException:
            error_report("Playlist '{}' not found".format(name))
        return True

    playlist = None
    if soco_function == "add_to_queue":
        playlist = get_playlist(speaker, name)
    elif soco_function == "add_library_playlist_to_queue":
        playlist = get_playlist(speaker, name, library=True)

    if playlist is not None:
        if soco_function in ["add_to_queue", "add_library_playlist_to_queue"]:
            if len(args) == 2:
                position = get_queue_insertion_position(speaker, args[1], action)
            else:
                position = speaker.queue_size + 1
            result = speaker.add_to_queue(playlist, position=position)
            save_queue_insertion_position(position)
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
    return line_in_core(speaker, action, args, True, use_local_speaker_list)


@zero_one_or_two_parameters
def cue_line_in(speaker, action, args, soco_function, use_local_speaker_list):
    if len(args) == 0:
        logging.info("'cue_line_in' invoked without parameters; insert 'on'")
        new_args = ("on",)
    else:
        new_args = args
    return line_in_core(speaker, action, new_args, False, use_local_speaker_list)


def line_in_core(speaker, action, args, start_playback, use_local_speaker_list):
    np = len(args)
    if np == 0:
        state = "on" if speaker.is_playing_line_in else "off"
        state = state + " ({})".format(
            speaker.get_current_transport_info()["current_transport_state"]
        )
        print(state)
    else:
        source = args[0]
        if source.lower() == "off":
            logging.info("Stopping playback")
            speaker.stop()
        elif source.lower() in ["on", "left_input"]:
            # Switch to the speaker's own line_in
            logging.info("Switching to the speaker's own Line-In")
            try:
                speaker.switch_to_line_in()
                if start_playback:
                    logging.info("Starting playback")
                    speaker.play()
                else:
                    logging.info("Stopping playback")
                    speaker.stop()
            except SoCoUPnPException:
                error_report("Line In operation failed ... not supported?")
                return False
        else:
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
                            "second parameter (if present) must be 'left_input' or"
                            " 'right_input'",
                        )
                        return False
                else:
                    logging.info("Using left-hand speaker's input")
                    line_in_source = get_speaker(source, use_local_speaker_list)
            if not line_in_source:
                error_report("Speaker or input '{}' not found".format(source))
                return False
            logging.info("Switching to Line-In")
            try:
                speaker.switch_to_line_in(line_in_source)
                if start_playback:
                    logging.info("Starting playback")
                    speaker.play()
                else:
                    logging.info("Stopping playback")
                    speaker.stop()
            except SoCoUPnPException:
                error_report("Line In operation failed ... not supported?")
                return False
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
    upper_limit = 15 if soco_function == "sub_gain" else 10
    lower_limit = upper_limit * -1
    try:
        delta = int(args[0])
    except:
        parameter_type_error(
            action, "integer from {} to {}".format(lower_limit, upper_limit)
        )
        return False
    current = getattr(speaker, soco_function)
    new_value = current + delta
    new_value = (
        lower_limit
        if new_value < lower_limit
        else upper_limit if new_value > upper_limit else new_value
    )
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
    if not speaker.music_library.library_updating:
        speaker.music_library.start_library_update()
        print("Library reindex started")
    else:
        print("A library reindex is already in progress")
    return True


@zero_parameters
def is_indexing(speaker, action, args, soco_function, use_local_speaker_list):
    if speaker.music_library.library_updating:
        print("yes")
    else:
        print("no")
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
        info["sub_gain"] = speaker.sub_gain
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
        remember_event_sub(sub)
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
                forget_event_sub(sub)
                return True
        except:
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

    wait_stop_core(speaker, not_paused=not_paused)

    playing_states = ["PLAYING", "TRANSITIONING"]
    if not_paused:
        # Also treat 'paused' as a playing state
        playing_states.append("PAUSED_PLAYBACK")

    # Poll for changes; count down reset timer
    # TODO: Polling is not ideal; should be redesigned using events
    original_start_time = start_time = current_time = time.time()
    poll_interval = 10
    logging.info(
        "Checking for not {}, poll interval = {}s".format(playing_states, poll_interval)
    )
    while (current_time - start_time) < duration:
        state = speaker.get_current_transport_info()["current_transport_state"]
        logging.info("Transport state = '{}'".format(state))
        if state in playing_states:
            # Restart the timer
            logging.info("Restarting the timer")
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
    return True


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
        remember_event_sub(sub)
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
                forget_event_sub(sub)
                return True
        except:
            pass


@one_or_two_parameters
def search_artists(speaker, action, args, soco_function, use_local_speaker_list):
    """
    Search for albums featuring the specified artist
    """
    ml = speaker.music_library
    name = args[0]
    artists = ml.get_music_library_information(
        "artists", search_term=name, complete_result=True
    )

    # Accumulate search results & artist names
    all_search_results = None
    all_artists = ""
    for index, artist in enumerate(artists):
        if (
            len(args) == 2
            and "strict" in args[1].lower()
            and name.lower() != artist.title.lower()
        ):
            continue
        search_result = ml.get_music_library_information(
            "artists", subcategories=[artist.title], max_items=SONOS_MAX_ITEMS
        )
        # Remove the first, unnecessary element from the list
        search_result.pop(0)
        if len(search_result) > 0:
            if index == 0:
                all_artists += artist.title
            else:
                all_artists += ", " + artist.title
        if all_search_results is None:
            all_search_results = search_result
        else:
            # The SearchResult class is a subclass of List
            all_search_results += search_result

    if all_search_results is None:
        return True

    print()
    print_list_header("Sonos Music Library Albums including Artist(s):", all_artists)
    print_albums(all_search_results, omit_first=False)
    print()

    save_search(all_search_results)
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


@one_or_two_parameters
def search_albums(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    albums = ml.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )

    if len(args) == 2:
        if "strict" == args[1].lower():
            albums = [album for album in albums if album.title.lower() == name.lower()]
        else:
            error_report("Second parameter must be 'strict' not '{}'".format(args[1]))
            return False

    if len(albums) > 0:
        print()
        print_list_header("Sonos Music Library Album Search:", name)
        print_albums(albums)
        print()
        save_search(albums)
    return True


@one_or_two_parameters
def search_tracks(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    tracks = ml.get_music_library_information(
        "tracks", search_term=name, complete_result=True
    )

    if len(args) == 2:
        if "strict" == args[1].lower():
            tracks = [track for track in tracks if track.title.lower() == name.lower()]
        else:
            error_report("Second parameter must be 'strict' not '{}'".format(args[1]))
            return False

    if len(tracks) > 0:
        print()
        print_list_header("Sonos Music Library Track Search:", name)
        print_tracks(tracks)
        print()
        save_search(tracks)
    return True


@one_or_two_parameters
def search_library(speaker, action, args, soco_function, use_local_speaker_list):
    search_artists(speaker, action, args, soco_function, use_local_speaker_list)
    search_albums(speaker, action, args, soco_function, use_local_speaker_list)
    search_tracks(speaker, action, args, soco_function, use_local_speaker_list)
    return True


@one_or_two_parameters
def tracks_in_album(speaker, action, args, soco_function, use_local_speaker_list):
    ml = speaker.music_library
    name = args[0]
    albums = ml.get_music_library_information(
        "albums", search_term=name, complete_result=True
    )

    if len(args) == 2:
        if "strict" == args[1].lower():
            albums = [album for album in albums if album.title.lower() == name.lower()]
        else:
            error_report("Second parameter must be 'strict' not '{}'".format(args[1]))
            return False

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
        if len(args) == 2:
            position = get_queue_insertion_position(speaker, args[1], action)
        else:
            position = speaker.queue_size + 1
        # Select a random entry from the list, in case there's more than one
        item = items[randint(0, len(items) - 1)]
        queue_position = speaker.add_to_queue(item, position=position)
        save_queue_insertion_position(queue_position)
        print(queue_position)
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
    """
    Perform the action only if the speaker is currently in the desired playback state
    """
    # If this is not the coordinator speaker, we need to check the state
    # of the coordinator instead
    state_speaker = speaker if speaker.is_coordinator else speaker.group.coordinator
    logging.info(
        "Checking playback state of coordinator speaker: '{}'".format(
            state_speaker.player_name
        )
    )
    state = state_speaker.get_current_transport_info()["current_transport_state"]
    logging.info(
        "Condition: '{}': Speaker '{}' is in state '{}'".format(
            action, state_speaker.player_name, state
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


@one_or_more_parameters
def if_coordinator(speaker, action, args, soco_function, use_local_speaker_list):
    """
    Perform the action only if the target speaker is (or is not) a coordinator.
    """

    if (speaker.is_coordinator and action == "if_not_coordinator") or (
        not speaker.is_coordinator and action == "if_coordinator"
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


@one_or_more_parameters
def if_queue(speaker, action, args, soco_function, use_local_speaker_list):
    """
    Perform the action only if the queue is empty or non-empty
    """
    # If this is not the coordinator speaker, we need to check the state
    # of the coordinator instead
    queue_speaker = speaker if speaker.is_coordinator else speaker.group.coordinator
    logging.info(
        "Checking queue of coordinator speaker: '{}'".format(queue_speaker.player_name)
    )
    logging.info(
        "Condition: '{}': Speaker '{}' has {} item(s) in the queue".format(
            action, queue_speaker.player_name, queue_speaker.queue_size
        )
    )
    if (queue_speaker.queue_size == 0 and action == "if_queue") or (
        queue_speaker.queue_size > 0 and action == "if_no_queue"
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
            print_list_header("Sonos Music Library: Saved Search", "")
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


def get_queue_insertion_position(speaker, insertion_point, action):
    """
    Helper function to find out where to insert something in the queue.
    Position is 1-based.
    Options:
       - integer queue position
       - first/start
       - next/play_next
       - last/end
    """
    try:
        position = int(insertion_point)
        if not 1 <= position <= speaker.queue_size + 1:
            logging.info(
                "Position {} is out of range ... will be constrained".format(
                    insertion_point
                )
            )
        if position < 1:
            position = 1
        elif position > speaker.queue_size + 1:
            position = speaker.queue_size + 1
        logging.info("Setting position to {}".format(position))
        return position
    except ValueError:
        pass

    if insertion_point.lower() in ["play_next", "next"]:
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
            logging.info(
                "Not currently playing from queue; add at current queue position"
            )
            offset = 0
        position = int(speaker.get_current_track_info()["playlist_position"]) + offset
    elif insertion_point.lower() in ["first", "start"]:
        position = 1
    elif insertion_point.lower() in ["last", "end"]:
        position = speaker.queue_size + 1
    else:
        raise Exception(
            "Additional parameter for '{}' must be 'first/start', 'next/play_next',"
            " 'last/end', or an integer queue position".format(action)
        )
    logging.info("Setting position to {}".format(position))
    return position


@one_or_two_parameters
def queue_search_results(speaker, action, args, soco_function, use_local_speaker_list):
    """
    Queue one or more items from the last saved search.
    """
    items = read_search()
    if not items:
        error_report("No saved search")
        return False
    logging.info("Loaded saved search")

    item_numbers = create_list_of_items_from_range(args[0], len(items))
    logging.info("Search items to add to queue: {}".format(item_numbers))

    if len(args) == 2:
        insertion_position = get_queue_insertion_position(speaker, args[1], action)
    else:
        insertion_position = speaker.queue_size + 1
    save_queue_insertion_position(insertion_position)
    logging.info("Inserting at queue position: {}".format(insertion_position))

    current_position = insertion_position
    for index, item_number in enumerate(item_numbers):
        current_queue_size = speaker.queue_size
        speaker.add_to_queue(items[item_number - 1], current_position)
        if index + 1 != len(item_numbers):
            current_position += speaker.queue_size - current_queue_size
            logging.info(
                "Advancing queue insertion point to: {}".format(current_position)
            )

    print(insertion_position)
    return True


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

    # Normal approach using track_info
    try:
        info = speaker.get_current_track_info()
        album_art_uri = info["album_art"]
        if album_art_uri == "":
            metadata = info["metadata"]
            data = parse(metadata)
            album_art_uri = data["DIDL-Lite"]["item"]["upnp:albumArtURI"]
        logging.info("Found album art directly: '{}'".format(album_art_uri))
    except:
        logging.info("Unable to find album art directly")
        album_art_uri = None

    # Try using transport events
    if not album_art_uri:
        try:
            sub = speaker.avTransport.subscribe()
            remember_event_sub(sub)
            event = sub.events.get(timeout=0.5)
            album_art_uri = event.variables["current_track_meta_data"].album_art_uri
            event_unsubscribe(sub)
            forget_event_sub(sub)
            logging.info("Found album art using events: '{}'".format(album_art_uri))
        except Exception as e:
            logging.info("Unable to find album art using events: {}".format(e))
            album_art_uri = None
        finally:
            unsub_all_remembered_event_subs()

    if not album_art_uri:
        logging.info("Album art not available: '{}'".format(album_art_uri))
        error_report("Album art not available")
        return False

    if not album_art_uri.startswith("http"):
        album_art_uri = "http://" + speaker.ip_address + ":1400" + album_art_uri
        logging.info("Prefixed HTTP: '{}'".format(album_art_uri))

    print(album_art_uri)
    return True


@one_or_two_parameters
def add_uri_to_queue(speaker, action, args, soco_function, use_local_speaker_list):
    uri = args[0]
    if len(args) == 2:
        position = get_queue_insertion_position(speaker, args[1], action)
    else:
        position = speaker.queue_size + 1

    speaker.add_uri_to_queue(uri, position=position)
    save_queue_insertion_position(position)
    print(position)
    return True


@one_or_more_parameters
def play_file(speaker, action, args, soco_function, use_local_speaker_list):
    end_on_pause = True if "_end_on_pause_" in args else False
    for audio_file in args:
        if audio_file == "_end_on_pause_":
            continue
        result = play_local_file(speaker, audio_file, end_on_pause=end_on_pause)
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


@one_or_two_parameters
def play_directory(speaker, action, args, soco_function, use_local_speaker_list):
    directory = args[0]
    options = "" if len(args) == 1 else args[1]
    options = options.lower()

    play_directory_files(speaker, directory, options=options)
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
        "Visible = {}, Coordinator = {}, Speakers in Group = {}, Other Visible Speakers"
        " = {}, Other Invisible Speakers = {}".format(
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
        remember_event_sub(sub)
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

            if event.variables["transport_state"] not in ["PLAYING", "TRANSITIONING"]:
                logging.info("Speaker is not playing")
                event_unsubscribe(sub)
                forget_event_sub(sub)
                return True

            if initial_title is None:
                track_info = speaker.get_current_track_info()
                initial_title = track_info.pop("title", None)
                initial_duration = track_info.pop("duration", None)
                try:
                    initial_radio_show = event.variables[
                        "current_track_meta_data"
                    ].radio_show
                except:
                    pass
                logging.info(
                    "Initial title = '{}', initial duration = '{}', initial radio show"
                    " = '{}'".format(
                        initial_title, initial_duration, initial_radio_show
                    )
                )

            else:
                track_info = speaker.get_current_track_info()
                current_title = track_info.pop("title", None)
                current_duration = track_info.pop("duration", None)
                try:
                    current_radio_show = event.variables[
                        "current_track_meta_data"
                    ].radio_show
                except:
                    current_radio_show = None
                logging.info(
                    "Current title = '{}', current duration = '{}', current radio show"
                    " = '{}'".format(
                        current_title, current_duration, current_radio_show
                    )
                )
                # Check whether track title, duration or radio show name have changed
                if (
                    current_title != initial_title
                    or current_duration != initial_duration
                    or current_radio_show != initial_radio_show
                ):
                    logging.info("Track/show has changed")
                    logging.info("Unsubscribing from events")
                    event_unsubscribe(sub)
                    forget_event_sub(sub)
                    return True
        except:
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


@one_or_two_parameters
def add_sharelink_to_queue(
    speaker, action, args, soco_function, use_local_speaker_list
):
    share_link = ShareLinkPlugin(speaker)
    uri = args[0]

    if len(args) == 2:
        position = get_queue_insertion_position(speaker, args[1], action)
    else:
        position = speaker.queue_size + 1

    if not share_link.is_share_link(uri):
        error_report("Invalid sharelink: '{}'".format(uri))
        return False

    try:
        # Return the queue position of the first added item
        queue_position = share_link.add_share_link_to_queue(uri, position)
        save_queue_insertion_position(queue_position)
        print(queue_position)
    except SoCoUPnPException as e:
        error_report("Unable to add sharelink to queue: {}".format(e))
        return False

    return True


@one_parameter
def play_sharelink(speaker, action, args, soco_function, use_local_speaker_list):
    share_link = ShareLinkPlugin(speaker)
    uri = args[0]

    if not share_link.is_share_link(uri):
        error_report("Invalid sharelink: '{}'".format(uri))
        return False

    position = speaker.queue_size + 1

    try:
        # Return the queue position of the first added item
        queue_position = share_link.add_share_link_to_queue(uri, position)
        save_queue_insertion_position(queue_position)
    except SoCoUPnPException as e:
        error_report("Unable to play sharelink to queue: {}".format(e))
        return False

    speaker.play_from_queue(queue_position - 1)
    return True


@zero_parameters
def reboot_count(speaker, action, args, soco_function, use_local_speaker_list):
    print(speaker.boot_seqnum)
    return True


@zero_parameters
def switch_to_tv(speaker, action, args, soco_function, use_local_speaker_list):
    if speaker.is_soundbar:
        speaker.switch_to_tv()
        return True

    error_report("Speaker '{}' is not a soundbar".format(speaker.player_name))
    return False


@zero_parameters
def audio_format(speaker, action, args, soco_function, use_local_speaker_list):
    if speaker.is_soundbar:
        audio_format = speaker.soundbar_audio_input_format
        if audio_format is None:
            print("No audio format information is available")
        else:
            print(audio_format)
        return True

    error_report("Speaker '{}' is not a soundbar".format(speaker.player_name))
    return False


@zero_parameters
def mic_enabled(
    speaker: soco.SoCo, action, args, soco_function, use_local_speaker_list
):
    if speaker.mic_enabled is None:
        error_report(
            "Speaker '{}' has no microphone, or voice services are not enabled".format(
                speaker.player_name
            )
        )
        return False

    print("{}".format(speaker.mic_enabled))
    return True


@zero_or_one_parameter
def tv_audio_delay(speaker, action, args, soco_function, use_local_speaker_list):
    if not speaker.is_soundbar:
        error_report("Speaker '{}' has no TV input".format(speaker.player_name))
        return False

    if len(args) == 0:
        print(speaker.audio_delay)
    else:
        try:
            speaker.audio_delay = int(args[0])
            return True
        except ValueError:
            error_report("TV audio delay must be an integer from 0 to 5")
            return False


@one_parameter
def group_volume_equalise(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        vol = int(args[0])
        if not (0 <= vol <= 100):
            raise ValueError
    except ValueError:
        parameter_type_error(action, "integer 0 to 100")
        return False

    for member in speaker.group.members:
        if member.is_visible:
            member.volume = vol
            logging.info(
                "Setting volume of speaker '{}' to {}".format(member.player_name, vol)
            )
    return True


@zero_parameters
def ungroup_all_in_group(speaker, action, args, soco_function, use_local_speaker_list):
    for member in speaker.group.members:
        if member.is_visible:
            if member.is_coordinator:
                logging.info(
                    "Not ungrouping coordinator speaker '{}'".format(member.player_name)
                )
            else:
                member.unjoin()
                logging.info("Ungrouped speaker '{}'".format(member.player_name))
    return True


@zero_or_one_parameter
def sub_gain(speaker, action, args, soco_function, use_local_speaker_list):
    if speaker.sub_gain is None:
        error_report("Speaker '{}' doesn't include a Sub".format(speaker.player_name))
        return False
    if len(args) == 0:
        print(speaker.sub_gain)
        return True
    try:
        gain = int(args[0])
        if not -15 <= gain <= 15:
            raise ValueError
        speaker.sub_gain = gain
        return True
    except ValueError:
        error_report("Sub gain must be an integer between -15 and 15")
        return False


@one_parameter
def set_queue_position(speaker, action, args, soco_function, use_local_speaker_list):
    try:
        qp = int(args[0])
    except ValueError:
        parameter_type_error(action, "integer")
        return False
    if 1 <= qp <= speaker.queue_size:
        speaker.stop()
        speaker.play_from_queue(index=qp - 1, start=False)
    else:
        error_report(
            "Queue position '{}' is out of range (queue length = {})".format(
                qp, speaker.queue_size
            )
        )
        return False
    return True


@zero_or_one_parameter
def surround_volume(speaker, action, args, soco_function, use_local_speaker_list):
    if getattr(speaker, soco_function) is None:
        error_report(
            "Speaker '{}' doesn't include surround speakers".format(speaker.player_name)
        )
        return False
    if len(args) == 0:
        print(getattr(speaker, soco_function))
        return True
    try:
        gain = int(args[0])
        if not -15 <= gain <= 15:
            raise ValueError
        setattr(speaker, soco_function, gain)
        return True
    except ValueError:
        error_report("Argument must be an integer between -15 and 15")
        return False


@one_parameter
def process_wait_action(speaker, action, args, soco_function, use_local_speaker_list):
    sequence = [action, args[0]]
    logging.info("Processing wait: {}".format(sequence))
    process_wait(sequence)
    return True


def process_action(speaker, action, args, use_local_speaker_list=False) -> bool:
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


def get_actions(
    include_loop_actions=True,
    include_wait_actions=False,
    include_track_follow_actions=True,
):
    action_list = list(actions.keys())
    if include_loop_actions:
        loop_actions = [
            "loop",
            "loop_until",
            "loop_for",
            "loop_to_start",
        ]
        action_list += loop_actions
    if include_wait_actions:
        wait_actions = ["wait", "wait_for", "wait_until"]
        action_list += wait_actions
    if include_track_follow_actions:
        action_list += ["track_follow", "tf", "track_follow_compact", "tfc"]
    return sorted(action_list)


def list_actions(
    include_loop_actions=True,
    include_wait_actions=False,
    include_track_follow_actions=True,
):
    action_list = get_actions(
        include_loop_actions=include_loop_actions,
        include_wait_actions=include_wait_actions,
        include_track_follow_actions=include_track_follow_actions,
    )

    longest_command = len(max(action_list, key=len))
    item_spacing = longest_command + 2
    try:
        items_per_line = get_terminal_size().columns // item_spacing
    except OSError:
        logging.info("Can't determine terminal width; printing simple list")
        action_list = sorted(action_list)
        for action in action_list:
            print(action)
        return

    action_list = sorted(action_list, reverse=True)

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
    "multi_group": SonosFunction(multi_group, "join"),
    "mg": SonosFunction(multi_group, "join"),
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
    "cue_line_in": SonosFunction(cue_line_in, ""),
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
    "if_stopped": SonosFunction(if_stopped_or_playing, ""),
    "if_playing": SonosFunction(if_stopped_or_playing, ""),
    "if_coordinator": SonosFunction(if_coordinator, ""),
    "if_not_coordinator": SonosFunction(if_coordinator, ""),
    "if_queue": SonosFunction(if_queue, ""),
    "if_no_queue": SonosFunction(if_queue, ""),
    "wait": SonosFunction(process_wait_action, ""),
    "wait_for": SonosFunction(process_wait_action, ""),
    "wait_until": SonosFunction(process_wait_action, ""),
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
    "queue_search_results": SonosFunction(queue_search_results, "", True),
    "qsr": SonosFunction(queue_search_results, "", True),
    "queue_search_result_number": SonosFunction(
        queue_search_results, "", True
    ),  # Legacy
    "queue_search_number": SonosFunction(queue_search_results, "", True),  # Legacy
    "qsn": SonosFunction(queue_search_results, "", True),  # Legacy
    "queue_multiple_search_results": SonosFunction(
        queue_search_results, "", True
    ),  # Legacy
    "qmsr": SonosFunction(queue_search_results, "", True),  # Legacy
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
    "alarms": SonosFunction(alarms.list_alarms, "get_alarms"),
    "list_alarms": SonosFunction(alarms.list_alarms, "get_alarms"),
    "remove_alarms": SonosFunction(alarms.remove_alarms, "", False),
    "remove_alarm": SonosFunction(alarms.remove_alarms, "", False),
    "add_alarm": SonosFunction(alarms.add_alarm, "", False),
    "create_alarm": SonosFunction(alarms.add_alarm, "", False),
    "enable_alarm": SonosFunction(alarms.enable_alarms, "", False),
    "enable_alarms": SonosFunction(alarms.enable_alarms, "", False),
    "disable_alarm": SonosFunction(alarms.disable_alarms, "", False),
    "disable_alarms": SonosFunction(alarms.disable_alarms, "", False),
    "modify_alarm": SonosFunction(alarms.modify_alarm, "", False),
    "modify_alarms": SonosFunction(alarms.modify_alarm, "", False),
    "copy_alarm": SonosFunction(alarms.copy_alarm, "", False),
    "move_alarm": SonosFunction(alarms.move_alarm, "", False),
    "snooze_alarm": SonosFunction(alarms.snooze_alarm, "", True),
    "relative_bass": SonosFunction(eq_relative, "bass", False),
    "rel_bass": SonosFunction(eq_relative, "bass", False),
    "rb": SonosFunction(eq_relative, "bass", False),
    "relative_treble": SonosFunction(eq_relative, "treble", False),
    "rel_treble": SonosFunction(eq_relative, "treble", False),
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
    "play_sharelink": SonosFunction(play_sharelink, "", True),
    "is_indexing": SonosFunction(is_indexing, "", False),
    "reboot_count": SonosFunction(reboot_count, "", False),
    "play_directory": SonosFunction(play_directory, "", True),
    "play_dir": SonosFunction(play_directory, "", True),
    "play_cd": SonosFunction(play_directory, "", True),  # Undocumented
    "switch_to_tv": SonosFunction(switch_to_tv, "", False),
    "has_subwoofer": SonosFunction(true_false_action, "has_subwoofer", False),
    "is_subwoofer": SonosFunction(true_false_action, "is_subwoofer", False),
    "has_satellites": SonosFunction(true_false_action, "has_satellites", False),
    "is_satellite": SonosFunction(true_false_action, "is_satellite", False),
    "sub_enabled": SonosFunction(on_off_action, "sub_enabled", False),
    "surround_enabled": SonosFunction(on_off_action, "surround_enabled", False),
    "audio_format": SonosFunction(audio_format, "", True),
    "copy_modify_alarm": SonosFunction(alarms.copy_modify_alarm, "", False),
    "tv_audio_delay": SonosFunction(tv_audio_delay, "", True),
    "alarms_zone": SonosFunction(alarms.list_alarms, "", False),
    "mic_enabled": SonosFunction(mic_enabled, "", False),
    "group_volume_equalise": SonosFunction(group_volume_equalise, "", True),
    "group_volume_equalize": SonosFunction(group_volume_equalise, "", True),
    "gve": SonosFunction(group_volume_equalise, "", True),
    "ungroup_all_in_group": SonosFunction(ungroup_all_in_group, "", True),
    "ugaig": SonosFunction(ungroup_all_in_group, "", True),
    "sub_gain": SonosFunction(sub_gain, "", False),
    "relative_sub_gain": SonosFunction(eq_relative, "sub_gain", False),
    "rel_sub_gain": SonosFunction(eq_relative, "sub_gain", False),
    "rsg": SonosFunction(eq_relative, "sub_gain", False),
    "surround_volume_tv": SonosFunction(surround_volume, "surround_volume_tv", False),
    "surround_volume_music": SonosFunction(
        surround_volume, "surround_volume_music", False
    ),
    "surround_full_volume_enabled": SonosFunction(
        on_off_action, "surround_full_volume_enabled", False
    ),
    "playing_tv": SonosFunction(true_false_action, "is_playing_tv", True),
    "is_playing_tv": SonosFunction(true_false_action, "is_playing_tv", True),
    "stop_all": SonosFunction(operate_on_all, "stop", False),
    "set_queue_position": SonosFunction(set_queue_position, "", True),
    "sqp": SonosFunction(set_queue_position, "", True),
}
