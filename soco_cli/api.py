import logging
import sys
from io import StringIO
from signal import SIGINT, signal

from soco import SoCo

from .action_processor import process_action
from .speakers import Speakers
from .utils import (
    configure_logging,
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

    :param speaker_name: The name of the speaker, or its IP address, as
        a string
    :param action: The name of the SoCo-CLI action to perform, as a string
    :param args: The list of arguments (strings) for the action. Each argument
        is a string. Arguments are optional depending on the action.
    :param use_local_speaker_list: Whether to use the local speaker
        cache to map the speaker name into an IP address. Bool.
    :return: Three-tuple (exit_code, output_string, error_msg)
    """

    # Prevent errors from causing exit
    set_api()

    # Capture stdout and stderr for the duration of this command
    output = StringIO()
    sys.stdout = output
    error = StringIO()
    sys.stderr = error

    speaker = None

    # Can pass a SoCo object instead of the speaker name (not documented)
    if type(speaker_name) == SoCo:
        speaker = speaker_name
        speaker_name = speaker.player_name

    elif type(speaker_name) == str:
        speaker = _get_soco_object(
            speaker_name, use_local_speaker_list=use_local_speaker_list
        )

    if speaker:
        return_value = process_action(
            speaker, action, args, use_local_speaker_list=use_local_speaker_list
        )
        output_msg = output.getvalue().rstrip()
        error_out = error.getvalue().rstrip()
        if not return_value:
            if error_out == "":
                error_out = "Error: Action '{}' not found".format(action)
            return_value = (1, output_msg, error_out)
        else:
            return_value = (0, output_msg, error_out)
    else:
        return_value = (1, "", "Speaker '{}' not found".format(speaker_name))

    # Restore stdout and stderr
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    return return_value


def set_log_level(log_level="None"):
    """Convenience function to set up logging

    :param log_level: Can be one of None, Critical, Error, Warn, Info, Debug.
    """
    configure_logging(log_level)


def handle_sigint():
    """
    Convenience function to set up a more graceful
    CTRL-C (sigint) handler.
    """
    signal(SIGINT, sig_handler)


def _get_soco_object(speaker_name, use_local_speaker_list=False):
    """Internal helper version that doesn't redirect stderr"""

    if use_local_speaker_list:
        _setup_local_speaker_list()

    return get_speaker(speaker_name, use_local_speaker_list)


def rescan_speakers():
    """Run full network scan to find speakers"""
    speaker_cache().scan(reset=True)


def rediscover_speakers():
    """Run normal SoCo discovery to discover speakers"""
    speaker_cache().discover(reset=True)


def get_all_speakers():
    """Return all SoCo instances"""
    return [s[0] for s in speaker_cache().get_all_speakers()]


def get_all_speaker_names():
    """Return all speaker names"""
    return speaker_cache().get_all_speaker_names()


def get_soco_object(speaker_name, use_local_speaker_list=False):
    """
    Uses the full set of soco_cli strategies to map a speaker name
    into a SoCo object

    :param speaker_name: The name of the speaker as a string
    :param use_local_speaker_list: Whether to use the local speaker cache

    :return Tuple of SoCo object, or None if no speaker is found, and an
        error message.
    """
    set_api()

    error = StringIO()
    sys.stderr = error

    speaker = _get_soco_object(speaker_name, use_local_speaker_list)

    sys.stderr = sys.__stderr__

    return speaker, error.getvalue().rstrip()


SPEAKER_LIST_SET = False


def _setup_local_speaker_list():
    global SPEAKER_LIST_SET
    if not SPEAKER_LIST_SET:
        speaker_list = Speakers()
        if not speaker_list.load():
            logging.info("Start speaker discovery")
            speaker_list.discover()
            speaker_list.save()
        set_speaker_list(speaker_list)
    SPEAKER_LIST_SET = True
