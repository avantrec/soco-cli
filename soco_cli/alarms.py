"""Processing module for alarm actions."""

import logging
import time
from copy import copy
from datetime import datetime

import soco  # type: ignore
import soco.alarms  # type: ignore
import tabulate  # type: ignore
from soco.alarms import Alarm, get_alarms
from soco.core import SoCo
from soco.exceptions import SoCoUPnPException  # type: ignore

from soco_cli.utils import (
    convert_true_false,
    error_report,
    one_parameter,
    parameter_type_error,
    two_parameters,
    zero_parameters,
)

# Stabilisation delay (in seconds) when operating on multiple alarms
ALARM_OPERATION_DELAY = 1.0


@zero_parameters
def list_alarms(speaker, action, args, soco_function, use_local_speaker_list):
    alarms = soco.alarms.get_alarms(speaker)
    if not alarms:
        return True
    details = []
    for alarm in alarms:
        # Skip this alarm if it's not for the target room
        if action == "alarms_zone":
            if alarm.zone != speaker:
                continue
        didl = alarm.program_metadata
        title_start = didl.find("<dc:title>")
        if title_start >= 0:
            title_start += len("<dc:title>")
            title_end = didl.find("</dc:title>")
            title = didl[title_start:title_end]
        elif alarm.program_uri is None:
            title = "Sonos Chime"
        elif alarm.program_uri != "":
            title = alarm.program_uri
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

    # Sort alarms by start time, room. Apply sorts in reverse order.
    details.sort(key=lambda field: field[1])  # Room
    details.sort(key=lambda field: field[2].split(":")[1])  # Minute
    details.sort(key=lambda field: field[2].split(":")[0])  # Hour

    headers = [
        "Alarm ID",
        "Speaker",
        "1: Start Time",
        "2: Duration",
        "3: Recurrence",
        "4: Enabled",
        "5: Title",
        "6: Play Mode",
        "7: Vol.",
        "8: Incl. Grouped",
    ]
    print()
    print(tabulate.tabulate(details, headers, tablefmt="github", numalign="left"))
    print()
    return True


@one_parameter
def remove_alarms(speaker, action, args, soco_function, use_local_speaker_list):
    alarms = get_alarms(speaker)

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

    deleted_counter = 0
    for alarm in alarms:
        if alarm.alarm_id in valid_alarm_ids_to_delete:
            logging.info("Deleting alarm ID: {}".format(alarm.alarm_id))
            alarm.remove()
            deleted_counter += 1
            if deleted_counter < len(valid_alarm_ids_to_delete):
                logging.info(
                    "Waiting for {}s for stabilisation".format(ALARM_OPERATION_DELAY)
                )
                time.sleep(ALARM_OPERATION_DELAY)

    alarms_invalid = alarm_ids_to_delete.difference(valid_alarm_ids_to_delete)
    if len(alarms_invalid) != 0:
        print("Error: Alarm ID(s) {} not found".format(alarms_invalid))

    return True


@one_parameter
def add_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    new_alarm = Alarm(zone=speaker)
    if not _modify_alarm_object(speaker, new_alarm, args[0]):
        return False

    try:
        new_alarm.save()
    except SoCoUPnPException as e:
        error_report("Failed to create alarm: {}".format(e))
        return False

    return True


@two_parameters
def modify_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    alarm_ids = args[0].lower().split(",")
    all_alarms = get_alarms(speaker)
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

    for index, alarm in enumerate(alarms):
        if not _modify_alarm_object(speaker, alarm, args[1]):
            continue
        try:
            logging.info("Saving alarm '{}'".format(alarm.alarm_id))
            alarm.save()
            if index < len(alarms) - 1:
                # Allow alarm update to stabilise
                logging.info(
                    "Waiting {}s after saving alarm '{}'".format(
                        ALARM_OPERATION_DELAY, alarm.alarm_id
                    )
                )
                time.sleep(ALARM_OPERATION_DELAY)
        except SoCoUPnPException as e:
            error_report("Failed to modify alarm {}: {}".format(alarm.alarm_id, e))
            continue

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
    alarms = get_alarms(speaker)
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
    except SoCoUPnPException as e:
        error_report("Failed to copy/move alarm: {}".format(e))
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
    alarms = get_alarms(speaker)
    alarm_ids = set(alarm_ids.lower().split(","))

    all_alarms = False
    if "all" in alarm_ids:
        all_alarms = True
        alarm_ids.discard("all")
    elif "_all_" in alarm_ids:
        all_alarms = True
        alarm_ids.discard("_all_")

    for alarm in alarms:
        if all_alarms is True or alarm.alarm_id in alarm_ids:
            logging.info(
                "Setting alarm id '{}' to enabled = {}".format(alarm.alarm_id, enabled)
            )
            if alarm.enabled != enabled:
                alarm.enabled = enabled
                logging.info("Saving alarm '{}'".format(alarm.alarm_id))
                try:
                    alarm.save()
                except SoCoUPnPException as e:
                    error_report(
                        "Failed to change state of alarm {}: {}".format(
                            alarm.alarm_id, e
                        )
                    )
                if len(alarm_ids) != 0 or all_alarms:
                    # Stabilisation delay
                    logging.info(
                        "Waiting {}s after saving alarm '{}'".format(
                            ALARM_OPERATION_DELAY, alarm.alarm_id
                        )
                    )
                    time.sleep(ALARM_OPERATION_DELAY)
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
                "A valid HH:MM:SS duration, or an integer number of minutes",
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


@two_parameters
def copy_modify_alarm(speaker, action, args, soco_function, use_local_speaker_list):
    alarm_id = args[0]
    alarm_parms = args[1]

    # Find the alarm
    alarms = get_alarms(speaker)
    for alarm in alarms:
        if alarm_id == alarm.alarm_id:
            break
    else:
        error_report(
            "Alarm ID '{}' not found; use the 'alarms' action to find the integer ID".format(
                alarm_id
            )
        )
        return False

    # Create a new alarm from the existing one
    new_alarm = copy(alarm)
    new_alarm._alarm_id = None
    new_alarm.zone = speaker

    # Apply modifications
    if not _modify_alarm_object(speaker, new_alarm, alarm_parms):
        return False

    # Save the new alarm
    try:
        new_alarm.save()
    except SoCoUPnPException as e:
        error_report(
            "Failed to copy/move alarm; did you remember to modify the start time?: {}".format(
                e
            )
        )
        return False

    return True


def _modify_alarm_object(speaker: SoCo, alarm: Alarm, parms_string: str) -> bool:
    alarm_parameters = parms_string.split(",")
    if len(alarm_parameters) != 8:
        error_report(
            "8 comma-separated parameters required for alarm modification specification"
        )
        return False

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

    fav = alarm_parameters[4]
    if not fav == "_":
        if fav.lower() == "chime":
            alarm.program_uri = None
        else:
            set_program_data(speaker, alarm, fav)

    play_mode = alarm_parameters[5].upper()
    if not play_mode == "_":
        play_mode_options = [
            "NORMAL",
            "SHUFFLE_NOREPEAT",
            "SHUFFLE",  # Note: this means SHUFFLE and REPEAT
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

    return True


def set_program_data(speaker: SoCo, alarm: Alarm, fav: str):
    """
    Set the program URI and metadata for the alarm, using a selection
    from the list of Sonos Favourites.
    """
    s_favs = speaker.music_library.get_sonos_favorites(complete_result=True)
    for s_fav in s_favs:
        # This will pick the first, case-insensitive partial match
        if fav.lower() in s_fav.title.lower():
            logging.info(
                "Found Sonos Favourite match for '{}' = '{}'".format(fav, s_fav.title)
            )
            alarm.program_metadata = s_fav.resource_meta_data
            # Assume there's only one 'resources' object in the list
            logging.info("Using URI = {}".format(s_fav.resources[0].uri))
            alarm.program_uri = s_fav.resources[0].uri
            return
    else:
        raise Exception("Favourite '{}' not found".format(fav))
