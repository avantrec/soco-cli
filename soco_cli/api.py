"""The SoCo-CLI API.

Provides a few simple, high-level functions that allow the features of SoCo-CLI
to be used in other programs.
"""

import logging
import sys
from io import StringIO
from signal import SIGINT, signal

from soco import SoCo

from soco_cli.action_processor import process_action
from soco_cli.speakers import Speakers
from soco_cli.utils import (
    configure_logging,
    create_speaker_cache,
    get_speaker,
    set_api,
    set_speaker_list,
    sig_handler,
    speaker_cache,
)


def run_command(speaker_name, action, *args, use_local_speaker_list=False):
    """Use SoCo-CLI to run a sonos command.

    The exit code, output string and error message string are returned as a
    three-tuple. If the exit code is non-zero, the error message will be
    populated and the output string will always be empty.

    All exceptions are caught when this function is run. Exception details
    will be returned in the error message string.

    Args:
        speaker_name (str): The name of the speaker, or its IP address.
            Alternatively, a 'SoCo' object can be supplied.
        action (str): The The name of the SoCo-CLI action to perform
        *args (list[str]): The set of arguments that accompany the action

    Returns:
        int, str, str: a three-tuple of exit_code, output_string and
        error_msg.
    """

    # Prevent errors from causing exit
    set_api()

    # Capture stdout and stderr for the duration of this command
    output = StringIO()
    sys.stdout = output
    error = StringIO()
    sys.stderr = error

    speaker = None
    exception_error = None

    # Can pass a SoCo object instead of the speaker name
    if isinstance(speaker_name, SoCo):
        speaker = speaker_name

    elif isinstance(speaker_name, str):
        try:
            speaker = _get_soco_object(
                speaker_name, use_local_speaker_list=use_local_speaker_list
            )
        except Exception as e:
            logging.info("Exception: {}".format(e))
            exception_error = e

    return_value = False

    if speaker:
        try:
            return_value = process_action(
                speaker, action, args, use_local_speaker_list=use_local_speaker_list
            )
        except Exception as e:
            logging.info("Exception: {}".format(e))
            exception_error = e

        output_msg = output.getvalue().rstrip()
        error_out = error.getvalue().rstrip()

        if not output_msg == "":
            lines = output_msg.splitlines()
            if len(lines) > 1 and lines[0] != "":
                output_msg = "\n" + output_msg
            if len(lines) > 1 and output_msg[len(lines) - 1] != "":
                output_msg = output_msg + "\n"

        if exception_error:
            if error_out:
                error_out = error_out + "\nError: " + str(exception_error)
            else:
                error_out = "Error: " + str(exception_error)

        if not return_value:
            if error_out == "":
                hint = " ... missing spaces around ':'?" if ":" in action else ""
                error_out = "Error: Action '{}' not found{}".format(action, hint)
            return_value = (1, output_msg, error_out)
        else:
            return_value = (0, output_msg, error_out)
    else:
        return_value = (
            1,
            "",
            "Speaker '{}' not found: {}".format(speaker_name, exception_error),
        )

    # Restore stdout and stderr
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    logging.info("Return value: {}".format(return_value))

    return return_value


def set_log_level(log_level="None"):
    """Convenience function to set up logging.

    Args:
        log_level (str): Can be one of None, Critical, Error, Warn, Info, Debug.
    """
    configure_logging(log_level)


def handle_sigint():
    """Convenience function to set up a more graceful CTRL-C (sigint) handler."""
    signal(SIGINT, sig_handler)


def rescan_speakers(timeout=None):
    """Run full network scan to find speakers."""
    _check_for_speaker_cache()
    speaker_cache().scan(reset=True, scan_timeout_override=timeout)


def rediscover_speakers():
    """Run normal SoCo discovery to discover speakers."""
    _check_for_speaker_cache()
    speaker_cache().discover(reset=True)


def get_all_speakers(use_scan=False):
    """Return all SoCo instances."""
    _check_for_speaker_cache()
    return [s[0] for s in speaker_cache().get_all_speakers(use_scan=use_scan)]


def get_all_speaker_names(use_scan=False):
    """Return all speaker names."""
    _check_for_speaker_cache()
    return speaker_cache().get_all_speaker_names(use_scan=use_scan)


def get_soco_object(speaker_name, use_local_speaker_list=False):
    """Uses the full set of soco_cli strategies to find a speaker.

    Args:
        speaker_name (str): The name of the speaker to find.
        use_local_speaker_list (bool): Whether to use the local speaker cache.

    Returns:
        (SoCo, str): Tuple of SoCo object, or None if no speaker is found,
        and an error message.
    """
    set_api()

    error = StringIO()
    sys.stderr = error

    speaker = _get_soco_object(speaker_name, use_local_speaker_list)

    sys.stderr = sys.__stderr__

    error_msg = error.getvalue().rstrip()
    if not speaker and error_msg == "":
        error_msg = "Speaker not found"

    return speaker, error_msg


def _get_soco_object(speaker_name, use_local_speaker_list=False):
    """Internal helper version that doesn't redirect stderr."""

    if use_local_speaker_list:
        _setup_local_speaker_list()

    _check_for_speaker_cache()

    return get_speaker(speaker_name, use_local_speaker_list)


def _check_for_speaker_cache():
    if not speaker_cache():
        create_speaker_cache(max_threads=256, scan_timeout=1.0, min_netmask=24)


# For local speaker list operations
speaker_list_set = False


def _setup_local_speaker_list():
    global speaker_list_set
    if not speaker_list_set:
        speaker_list = Speakers()
        if not speaker_list.load():
            logging.info("Start speaker discovery")
            speaker_list.discover()
            speaker_list.save()
        set_speaker_list(speaker_list)
    speaker_list_set = True
