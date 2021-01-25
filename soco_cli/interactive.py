""" SoCo-CLI interactive mode handler """

import logging

# Readline is only available on Unix
try:
    import readline

    RL = True
except ImportError:

    RL = False

from shlex import split as shlex_split

from .action_processor import get_actions, list_actions
from .aliases import AliasManager
from .api import get_soco_object, run_command
from .cmd_parser import CLIParser
from .utils import (
    RewindableList,
    get_readline_history,
    get_speaker,
    local_speaker_list,
    save_readline_history,
    set_interactive,
    speaker_cache,
)
from .wait_actions import process_wait


# Alias Manager
am = AliasManager()


def interactive_loop(speaker_name, use_local_speaker_list=False, no_env=False):

    # Is the speaker name set on the command line?
    # Note: ignores SPKR set as part of the environment
    speaker = None
    saved_speaker = None
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
        print("Note: Autocompletion not currently available on Windows.\n")

    set_interactive()
    am.load_aliases()

    if RL:
        _set_actions_and_commands_list(use_local_speaker_list=use_local_speaker_list)
        readline.parse_and_bind("tab: complete")
        readline.set_completer(_completer)
        readline.set_completer_delims(" ")
        _get_readline_history()

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
        command_sequences = RewindableList(cli_parser.get_sequences())
        logging.info("Command sequences = {}".format(command_sequences))

        # The command_sequence list can change, so we use pop() until the
        # list is exhausted
        while True:
            try:
                command = command_sequences.pop_next()
                logging.info("Current command = '{}'".format(command))
            except IndexError:
                break

            # Replace the command sequence with the contents of an alias
            # This is tricky for multiple sequences
            if command[0] in am.alias_names():
                action = am.action(command[0])
                actions = shlex_split(action)
                cli_parser.parse(actions)
                new_sequences = cli_parser.get_sequences()
                logging.info("Sequences in the alias: {}".format(new_sequences))
                command = new_sequences.pop(0)
                # Multiple sequences?
                if len(new_sequences):
                    # Insert the additional sequences in the list
                    index = command_sequences.index()
                    for sequence in new_sequences:
                        logging.info(
                            "Inserting new sequence {} at {}".format(sequence, index)
                        )
                        command_sequences.insert(index, sequence)
                        index += 1

            if command[0] == "0":
                # Unset the active speaker
                logging.info("Unset active speaker")
                speaker_name = None
                speaker = None
                continue

            command_lower = command[0].lower()

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
                logging.info("Processing a 'wait' action")
                process_wait(command)
                continue

            # Is the input a number in the range of speaker numbers?
            try:
                speaker_number = int(command_lower)
                limit = len(
                    _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
                )
                if 1 <= speaker_number <= limit:
                    logging.info(
                        "Setting to active speaker no. {} ".format(speaker_number)
                    )
                    speaker_name = _get_speaker_names(
                        use_local_speaker_list=use_local_speaker_list
                    )[speaker_number - 1]
                    speaker = get_speaker(speaker_name, use_local_speaker_list)
                    logging.info("{} : {}".format(speaker, speaker_name))
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
                    logging.info("Full network rescan")
                    speaker_cache().scan(reset=True)
                    _print_speaker_list(use_local_speaker_list=use_local_speaker_list)
                    _set_actions_and_commands_list(
                        use_local_speaker_list=use_local_speaker_list
                    )
                continue

            if command_lower == "push":
                if speaker:
                    logging.info(
                        "Pushing current active speaker: {}".format(speaker.player_name)
                    )
                else:
                    logging.info("No active speaker to push")
                saved_speaker = speaker
                speaker_name = None
                speaker = None
                continue

            if command_lower == "pop":
                logging.info("Popping the saved speaker state")
                if saved_speaker:
                    speaker = saved_speaker
                    speaker_name = speaker.player_name
                    logging.info("Saved speaker = '{}'".format(speaker_name))
                    saved_speaker = None
                else:
                    logging.info("No saved speaker")
                continue

            # Alias creation, update, and deletion
            if command_lower == "alias":
                if len(command) == 1:
                    am.print_aliases()
                    continue
                # Remove 'alias'
                command.pop(0)
                alias_name = command.pop(0)
                if alias_name == "alias":
                    print("Cannot create alias for 'alias'")
                    continue
                if len(command) == 0:
                    if am.create_alias(alias_name, None):
                        print("Alias '{}' removed".format(alias_name))
                    else:
                        print("Alias '{}' not found".format(alias_name))
                else:
                    # Have to collect the remaining sequences: they're all
                    # part of the alias. Reconstruction required.
                    # Multi-word parameters need quotes reinstated
                    _restore_quotes(command)
                    actions = [" ".join(command)]
                    logging.info("Action = '{}'".format(command))
                    while True:
                        try:
                            command = command_sequences.pop_next()
                            _restore_quotes(command)
                            actions.append(" ".join(command))
                            logging.info("Action = '{}'".format(command))
                        except IndexError:
                            break
                    action = " : ".join(actions)
                    logging.info("Action sequence = '{}'".format(action))
                    _, new = am.create_alias(alias_name, action)
                    if new:
                        print("Alias '{}' created".format(alias_name))
                    else:
                        print("Alias '{}' updated".format(alias_name))
                am.save_aliases()
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
                            logging.info(
                                "Set new active speaker: '{}'".format(new_speaker_name)
                            )
                            speaker = new_speaker
                            speaker_name = speaker.player_name
                        continue
                except IndexError:
                    # No speaker name given
                    logging.info("Unset active speaker ('set' with no arguments)")
                    speaker_name = None
                    speaker = None
                    continue

                if not speaker_name:
                    logging.info(
                        "Treating first parameter '{}' as speaker name".format(args[0])
                    )
                    name = args.pop(0)
                    speaker = get_speaker(name, use_local_speaker_list)
                    if not speaker:
                        print(
                            "Error: Speaker '{}' not found; should an active speaker be set?".format(
                                name
                            )
                        )
                        continue

                action = args.pop(0).lower()
                logging.info("Action = '{}'; args = '{}'".format(action, args))
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


COMMANDS = [
    "actions",
    "alias ",
    "exit",
    "help",
    "pop",
    "push",
    "rescan",
    "set ",
    "speakers",
]


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
    logging.info("Rebuilding commands/action list")
    global ACTIONS_LIST
    ACTIONS_LIST = (
        [
            action + " "
            for action in get_actions()
            + _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
        ]
        + COMMANDS
        + am.alias_names()
    )


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
    'alias'     :   Add an alias: alias <alias_name> <actions>
                    Remove an alias: alias <alias_name>
                    Update an alias by creating a new alias with the same name.
                    Using 'alias' without parameters shows the current list of
                    aliases.
                    Aliases override existing actions and can contain
                    sequences of actions.
    'exit'      :   Exit the shell.
    'help'      :   Show this help message (available shell commands).
    'pop'       :   Restore saved active speaker state.
    'push'      :   Save the current active speaker, and unset the active speaker.
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

    Use the arrow keys for command history and command editing.
    
    [Not Available on Windows] Use the TAB key for autocompletion of shell
    commands, SoCo-CLI actions, aliases, and speaker names.
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
        logging.info("Saving shell history")
        save_readline_history()


def _get_readline_history():
    if RL:
        logging.info("Reading shell history")
        get_readline_history()


def _restore_quotes(command):
    for index, parts in enumerate(command):
        if len(parts.split()) > 1:
            command[index] = '"' + parts + '"'
