""" SoCo-CLI interactive mode handler """

import logging
import readline

from .api import get_soco_object
from .utils import get_speaker, local_speaker_list, set_interactive, speaker_cache

from shlex import split as shlex_split

from .action_processor import list_actions, process_action


def interactive_loop(speaker_name, use_local_speaker_list=False, no_env=False):

    # Is the speaker name set on the command line?
    # Note: ignores SPKR set as part of the environment
    speaker = None
    if speaker_name:
        speaker, error_msg = get_soco_object(
            speaker_name, use_local_speaker_list=use_local_speaker_list
        )
        if not speaker:
            print("Speaker '{}' not found {}".format(speaker_name, error_msg))
            speaker_name = None

    print("\nEntering SoCo-CLI interactive mode")
    print("Type 'help' for available commands.\n")

    # readline.parse_and_bind('tab: complete')
    # readline.set_completer(_completer)
    # readline.set_completer_delims(' ')

    set_interactive()

    # Input loop
    while True:
        if speaker_name and speaker:
            command = input(
                "Enter 'action [args]' (0 to exit) [{}] > ".format(speaker.player_name)
            )
        else:
            command = input("Enter 'speaker action [args]' (0 to exit) [] > ")
        if command == "":
            continue
        command_lower = command.lower()
        if command == "0" or command_lower.startswith("exit"):
            logging.info("Exiting interactive mode")
            print()
            return True
        if command_lower == "help":
            _interactive_help()
            continue
        if command_lower == "actions":
            _show_actions()
            continue
        if command_lower == "speakers":
            print()
            names = _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
            for index, name in enumerate(names, start=1):
                print("  ", str(index).rjust(2), ":", name)
            print()
            continue
        # Is the input a number in the range of speaker numbers?
        try:
            speaker_number = int(command_lower)
            if 1 <= speaker_number <= len(_get_speaker_names(use_local_speaker_list=use_local_speaker_list)):
                speaker_name = _get_speaker_names(use_local_speaker_list=use_local_speaker_list)[speaker_number - 1]
                speaker = get_speaker(speaker_name, use_local_speaker_list)
            elif speaker_number < 0:
                speaker_name = None
                speaker = None
            else:
                print("Error: Speaker number is out of range")
            continue
        except ValueError:
            pass
        # if command_lower == "rediscover":
        #     if use_local_speaker_list:
        #         print("Using cached speaker list: no discovery performed")
        #     else:
        #         speaker_cache().discover(reset=True)
        #     continue
        if command_lower == "rescan":
            if use_local_speaker_list:
                print("Using cached speaker list: no rescan performed")
            else:
                speaker_cache().scan(reset=True)
            continue

        # Command processing
        try:
            args = shlex_split(command)

            # Setting a speaker to operate on?
            try:
                if "speaker" == args[0] and "=" == args[1]:
                    speaker_name = args[2]
                    speaker = get_speaker(speaker_name, use_local_speaker_list)
                    if not speaker:
                        print("Error: Speaker not found")
                        speaker_name = None
                    continue
            except IndexError:
                speaker_name = None
                continue

            if not speaker_name:
                speaker = get_speaker(args.pop(0), use_local_speaker_list)
                if not speaker:
                    print("Error: Speaker not found")
                    continue
            action = args.pop(0)
            response = process_action(
                speaker, action, args, use_local_speaker_list=use_local_speaker_list
            )
            if not response:
                print("Error: Action '{}'".format(action))
        except:
            print("Error: Invalid command")


def _completer(*args, **kwargs):
    pass


def _show_actions():
    print()
    print("Complete list of SoCo-CLI actions:")
    print("==================================")
    print()
    list_actions(include_additional=False)
    print()


def _interactive_help():
    print(HELP_TEXT)


HELP_TEXT = """
This is SoCo-CLI interactive mode. Interactive commands are as follows:

    '1', ...    :   Set the active speaker. Use the numbers shown by the
                    'speakers' command. E.g., to set to speaker number 4
                    in the list, just type '4'. A negative number will
                    unset the active speaker, e.g., enter '-1'.
    'actions'   :   Show the list of SoCo-CLI actions.
    'exit'      :   Exit the program. '0' also works.
    'help'      :   Show this help message.
    'rescan'    :   If your speaker doesn't appear in the 'speakers' list,
                    use this to perform a more comprehensive scan.
    'speakers'  :   List the names of all available speakers
    'speaker =' :   Set the active, using 'speaker = <speaker_name>'
                    Use quotes when needed for the speaker name, e.g.:
                    speaker = "Front Reception". The spaces around '=' are
                    required. Unambiguous partial, case-insensitive matches
                    work.
                    To unset the active speaker, use a blank speaker name,
                    or just enter a negative number.
    
    The command syntax is the same as using 'sonos' from the command line.
    If a speaker been set, the speaker name is omitted from the command.
"""


def _get_speaker_names(use_local_speaker_list=False):
    if use_local_speaker_list:
        names = local_speaker_list().get_all_speaker_names()
    else:
        names = speaker_cache().get_all_speaker_names()
    return names
