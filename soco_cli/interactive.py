""" SoCo-CLI interactive mode handler """

import logging
from os import path

# Readline is only available on Unix
try:
    import readline

    RL = True
except ImportError:

    RL = False

from shlex import split as shlex_split

from .action_processor import get_actions, list_actions
from .api import get_soco_object, run_command
from .cmd_parser import CLIParser
from .utils import (
    get_readline_history,
    get_speaker,
    local_speaker_list,
    save_readline_history,
    set_interactive,
    speaker_cache,
)
from .wait_actions import process_wait


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

    print("\nEntering SoCo-CLI interactive shell.")
    print("Type 'help' for available shell commands.\n")
    if not RL:
        print(
            "Note: Command history and autocompletion not currently available on Windows.\n"
        )

    if RL:
        _set_actions_and_commands_list(use_local_speaker_list=use_local_speaker_list)
        readline.parse_and_bind("tab: complete")
        readline.set_completer(_completer)
        readline.set_completer_delims(" ")
        _get_readline_history()

    set_interactive()

    # Input loop
    while True:
        if speaker_name and speaker:
            command_line = input("SoCo-CLI [{}] > ".format(speaker.player_name))
        else:
            command_line = input("SoCo-CLI [] > ")

        if command_line == "":
            continue

        # Parse multiple action sequences
        cli_parser = CLIParser()
        cli_parser.parse(shlex_split(command_line))

        # Loop through action sequences
        for command in cli_parser.get_sequences():

            command_lower = command[0].lower()

            if command[0] == "0":
                # Unset the active speaker
                speaker_name = None
                speaker = None
                continue

            if command_lower.startswith("exit"):
                logging.info("Exiting interactive mode")
                _save_readline_history()
                return True

            if command_lower in ["help", "?"]:
                _interactive_help()
                continue

            if command_lower == "actions":
                _show_actions()
                continue

            if command_lower == "speakers":
                _print_speaker_list(use_local_speaker_list=use_local_speaker_list)
                continue

            if command_lower in ["wait", "wait_until", "wait_for"]:
                process_wait(command)
                continue

            # Is the input a number in the range of speaker numbers?
            try:
                speaker_number = int(command_lower)
                limit = len(
                    _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
                )
                if 1 <= speaker_number <= limit:
                    speaker_name = _get_speaker_names(
                        use_local_speaker_list=use_local_speaker_list
                    )[speaker_number - 1]
                    speaker = get_speaker(speaker_name, use_local_speaker_list)
                else:
                    print(
                        "Error: Speaker number is out of range (0 to {})".format(limit)
                    )
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
                    _print_speaker_list(use_local_speaker_list=use_local_speaker_list)
                    _set_actions_and_commands_list(
                        use_local_speaker_list=use_local_speaker_list
                    )
                continue

            # Command processing
            try:
                args = command

                # Setting a speaker to operate on?
                try:
                    if args[0] == "set":
                        new_speaker_name = args[1]
                        new_speaker = get_speaker(
                            new_speaker_name, use_local_speaker_list
                        )
                        if not new_speaker:
                            print(
                                "Error: Speaker '{}' not found".format(new_speaker_name)
                            )
                        else:
                            speaker_name = new_speaker_name
                            speaker = new_speaker
                        continue
                except IndexError:
                    speaker_name = None
                    continue

                if not speaker_name:
                    speaker = get_speaker(args.pop(0), use_local_speaker_list)
                    if not speaker:
                        print("Error: Speaker not found")
                        continue

                action = args.pop(0).lower()
                exit_code, output, error_msg = run_command(
                    speaker,
                    action,
                    *args,
                    use_local_speaker_list=use_local_speaker_list,
                )
                if exit_code:
                    if not error_msg == "":
                        print(error_msg)
                else:
                    if not output == "":
                        lines = output.splitlines()
                        if len(lines) > 1 and lines[0] != "":
                            print()
                        print(output)
                        if len(lines) > 1 and output[len(lines) - 1] != "":
                            print()
            except:
                print("Error: Invalid command")


COMMANDS = ["actions", "exit", "help", "rescan", "set ", "speakers"]


def _completer(text, context):
    """Auto-complete commands using TAB"""
    matches = [cmd for cmd in _get_actions_and_commands() if cmd.startswith(text)]
    return matches[context]


def _show_actions():
    print()
    print("Complete list of SoCo-CLI actions:")
    print("==================================")
    print()
    list_actions(include_additional=False)
    print()


ACTIONS_LIST = []


def _set_actions_and_commands_list(use_local_speaker_list=False):
    global ACTIONS_LIST
    ACTIONS_LIST = [
        action + " "
        for action in get_actions()
        + _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
    ] + COMMANDS


def _get_actions_and_commands():
    return ACTIONS_LIST


def _interactive_help():
    print(HELP_TEXT)


HELP_TEXT = """
This is SoCo-CLI interactive mode. Interactive commands are as follows:

    '1', ...    :   Set the active speaker. Use the numbers shown by the
                    'speakers' command. E.g., to set to speaker number 4
                    in the list, just type '4'.
                    '0' will unset the active speaker.
    'actions'   :   Show the complete list of SoCo-CLI actions.
    'exit'      :   Exit the shell.
    'help'      :   Show this help message (available shell commands).
    'rescan'    :   If your speaker doesn't appear in the 'speakers' list,
                    use this to perform a more comprehensive scan.
    'set <spkr> :   Set the active speaker using its name.
                    Use quotes when needed for the speaker name, e.g.,
                    'set "Front Reception"'. Unambiguous partial, case-insensitive
                    matches are supported, e.g., 'set front'.
                    To unset the active speaker, omit the speaker name,
                    or just enter '0'.   
    'speakers'  :   List the names of all available speakers
    
    The command syntax is the same as when using 'sonos' from the command line.
    If a speaker been set, the speaker name is omitted from the command.
    
    [Not Available on Windows]
    Use the TAB key for autocompletion of shell commands, SoCo-CLI actions, and
    speaker names. Use the arrow keys for command history and command editing.
"""


def _get_speaker_names(use_local_speaker_list=False):
    if use_local_speaker_list:
        names = local_speaker_list().get_all_speaker_names()
    else:
        names = speaker_cache().get_all_speaker_names()
    return names


def _print_speaker_list(use_local_speaker_list=False):
    print()
    names = _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
    names.insert(0, "Unset the active speaker")
    for index, name in enumerate(names, start=0):
        print("  ", str(index).rjust(2), ":", name)
    print()


def _save_readline_history():
    if RL:
        save_readline_history()


def _get_readline_history():
    if RL:
        get_readline_history()
