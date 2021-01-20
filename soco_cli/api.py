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
)


def run_command(
    speaker_name: str,
    action: str,
    *args: tuple[
        str,
    ],
    use_local_speaker_list: bool = False
) -> (int, str, str):
    """Use SoCo-CLI to run a sonos command.

    The exit code, output string and error message are returned as a
    three-tuple. If the exit code is non-zero, the error message will be
    populated and the output string will always be empty.

    :param speaker_name: The name of the speaker, or its IP address
    :param action: The name of the SoCo-CLI action to perform
    :param args: The list of arguments for the action. Each argument
        is a string. Arguments are optional depending on the action.
    :param use_local_speaker_list: Whether to use the local speaker
        cache to map the speaker name into an IP address.
    :return: Three-tuple (exit_code, output_string, error_msg)
    """

    speaker = get_soco_object(speaker_name, use_local_speaker_list)
    if not speaker:
        return 1, "", "Error: Speaker '{}' not found".format(speaker_name)

    # Capture stdout and stderr for the duration of this command
    output = StringIO()
    sys.stdout = output
    error = StringIO()
    sys.stderr = error

    # Prevent errors from causing exit
    set_api()

    return_value = process_action(
        speaker, action, args, use_local_speaker_list=use_local_speaker_list
    )

    # Restore stdout and stderr
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    output_string = output.getvalue().rstrip()
    error_msg = error.getvalue().rstrip()

    if not return_value and error_msg == "":
        error_msg = "Error: Action '{}' not found".format(action)

    exit_code = 1 if len(error_msg) else 0

    return exit_code, output_string, error_msg


def set_log_level(log_level: str = "None") -> None:
    """Convenience function to set up logging

    :param log_level: Can be one of None, Critical, Error, Warn, Info, Debug.
    """
    configure_logging(log_level)


def handle_sigint() -> None:
    """
    Convenience function to set up a more graceful
    CTRL-C (sigint) handler.
    """
    signal(SIGINT, sig_handler)


def get_soco_object(speaker_name: str, use_local_speaker_list: bool = False) -> SoCo:
    """
    Uses the full set of soco_cli strategies to map a speaker name
    into a SoCo object

    :param speaker_name: The name of the speaker
    :param use_local_speaker_list: Whether to use the local speaker cache

    :return SoCo object, or None if no speaker is found
    """
    if use_local_speaker_list:
        _setup_local_speaker_list()

    return get_speaker(speaker_name, use_local_speaker_list)


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
