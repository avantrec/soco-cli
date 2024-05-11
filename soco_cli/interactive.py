"""SoCo-CLI interactive mode handler."""

import logging
import subprocess
import sys

# Readline is only available on Unix
try:
    import readline

    RL = True
    UNIX = True
    WINDOWS = False
except ImportError:
    RL = False
    WINDOWS = True
    UNIX = False

from copy import deepcopy
from os import chdir
from shlex import split as shlex_split
from typing import List, Union

from soco import SoCo  # type: ignore

from soco_cli.action_processor import get_actions, list_actions
from soco_cli.aliases import AliasManager
from soco_cli.api import get_soco_object, run_command
from soco_cli.check_for_update import print_update_status
from soco_cli.cmd_parser import CLIParser
from soco_cli.keystroke_capture import get_keystroke
from soco_cli.utils import (
    RewindableList,
    docs,
    get_readline_history,
    get_speaker,
    local_speaker_list,
    save_readline_history,
    set_interactive,
    set_single_keystroke,
    set_suspend_sighandling,
    speaker_cache,
    version,
)

# Alias Manager
am = AliasManager()

# The following actions are run in a subprocess, to allow them to be terminated
# without dropping out of the interactive shell.
ACTIONS_TO_EXEC = [
    "track_follow",
    "tf",
    "track_follow_compact",
    "tfc",
    "wait_stop",
    "wait_start",
    "wait_stopped_for",
    "wsf",
    "wait_stop_not_pause",
    "wsnp",
    "wait_stopped_for_not_pause",
    "wsfnp",
    "wait_end_track",
    "play_file",
    "play_local_file",
    "play_m3u",
    "play_local_m3u",
    "play_dir",
    "play_directory",
    "play_cd",
    "if_stopped",
    "if_playing",
]


ACTIONS_TO_EXEC_NO_SPEAKER = [
    "wait",
    "wait_until",
    "wait_for",
]


LOG_SETTING = ""


def interactive_loop(
    speaker_name,
    log_setting,
    use_local_speaker_list=False,
    no_env=False,
    single_keystroke=False,
):
    """
    The main interactive loop for gathering and processing interactive commands.

    Args:
        speaker_name (str): The name of the speaker supplied if supplied on the command
            line.
        log_setting (str): The logging option.
        use_local_speaker_list (bool): Whether to use cached discovery.
        no_env (bool): Whether to ignore environment variables.
        single_keystroke (bool): Whether to start in single keystroke mode.
    """

    global LOG_SETTING
    LOG_SETTING = "--log=" + log_setting

    speaker = None
    saved_speaker = None
    pushed = False
    temp_active_speaker = False

    # Is the speaker name set on the command line?
    # Note: ignores SPKR set as part of the environment
    if speaker_name:
        try:
            speaker, error_msg = get_soco_object(
                speaker_name, use_local_speaker_list=use_local_speaker_list
            )
            if not speaker:
                print("Speaker '{}' not found [{}]".format(speaker_name, error_msg))
                speaker_name = None
            else:
                speaker_name = speaker.player_name
        except Exception as e:
            print("Error finding speaker '{}': {}".format(speaker_name, e))
            speaker_name = None

    print("\nEntering SoCo-CLI interactive shell.")
    if single_keystroke:
        print("Single Keystroke Mode ... 'x' to exit.\n")
        set_single_keystroke(True)
    else:
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

    root_prompt = "Sonos"

    # Input loop
    while True:
        # Catch all exceptions raised in the input loop
        try:
            if speaker_name and speaker:
                prompt = (root_prompt + " [{}] > ").format(speaker_name)
            else:
                prompt = root_prompt + " [] > "

            # Single keystroke input handling
            if single_keystroke:
                prompt = prompt.replace(">", ">>")
                print(prompt, flush=True, end="")
                command_line = get_keystroke()
                # Handle Windows CTRL-C; disable exit
                if command_line == "\x03":
                    logging.info("Windows CTRL-C received ... prevent exit")
                    print("Please use 'x' to exit >> ")
                    continue
                print(command_line)
                # Normal exit
                if command_line in ["x", "X"]:
                    logging.info("Exit from single keystroke mode")
                    single_keystroke = False
                    set_single_keystroke(False)
                    continue

            # Normal input handling
            else:
                command_line = input(prompt)
            if command_line == "":
                continue

            # Parse multiple action sequences
            cli_parser = CLIParser()
            try:
                cli_parser.parse(shlex_split(command_line))
            except ValueError as error:
                print("Error: {}".format(error))
                continue

            # Loop through action sequences
            command_sequences = RewindableList(cli_parser.get_sequences())
            logging.info("Command sequences = {}".format(command_sequences))

            # The command_sequence list can change, so we use pop_next() until the
            # list is exhausted
            while True:
                try:
                    command = command_sequences.pop_next()
                    logging.info("Current sequence = {}".format(command))
                except IndexError:
                    break

                if len(command) == 0:
                    continue

                # Is this an alias?
                if command[0] in am.alias_names():
                    ap = AliasProcessor()
                    index = command_sequences.index()
                    ap.process(command, am, command_sequences)
                    command_sequences.rewind_to(index)
                    continue

                command_lower = command[0].lower()

                # Aliases are now fully unpacked. If the command sequences
                # contain loops, execute in a subprocess unless this is just
                # setting up an alias.
                if not command_lower == "alias":
                    if _exec_loop(
                        speaker, command, command_sequences, use_local_speaker_list
                    ):
                        break

                if command_lower == "0":
                    # Unset the active speaker
                    logging.info("Unset active speaker")
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

                if command_lower in ["single-keystroke", "sk"]:
                    print("Single keystroke mode ... 'x' to exit")
                    single_keystroke = True
                    set_single_keystroke(True)
                    continue

                if command_lower == "speakers":
                    _print_speaker_list(use_local_speaker_list=use_local_speaker_list)
                    continue

                if command_lower in ["version"]:
                    print()
                    version()
                    print()
                    continue

                if command_lower in ["docs"]:
                    docs()
                    continue

                if command_lower in ["check_for_update"]:
                    print_update_status()
                    continue

                # Is the input a number in the range of speaker numbers?
                try:
                    speaker_number = int(command_lower)
                    limit = len(
                        _get_speaker_names(
                            use_local_speaker_list=use_local_speaker_list
                        )
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
                            "Error: Speaker number is out of range (0 to {})".format(
                                limit
                            )
                        )
                    continue
                except ValueError:
                    pass

                if command_lower == "rescan":
                    _rescan(use_local_speaker_list=use_local_speaker_list)
                    continue

                if command_lower == "rescan_max":
                    _rescan(
                        use_local_speaker_list=use_local_speaker_list, max_scan=True
                    )
                    continue

                if command_lower == "exec":
                    if len(command) > 1:
                        _exec(command[1:])
                    continue

                if command_lower == "cd":
                    if len(command) > 1:
                        try:
                            logging.info("Attempting to cd to: '{}'".format(command[1]))
                            chdir(command[1])
                        except Exception as e:
                            print(e)
                    continue

                if command_lower == "push":
                    if pushed is True:
                        logging.info("Active speaker already pushed ... ignored")
                        continue
                    if speaker:
                        pushed = True
                        logging.info(
                            "Pushing current active speaker: {}".format(
                                speaker.player_name
                            )
                        )
                    else:
                        pushed = False
                        logging.info("No active speaker to push")
                    saved_speaker = speaker
                    speaker_name = None
                    speaker = None
                    continue

                if command_lower == "pop":
                    if pushed is False:
                        logging.info("No active speaker state to pop ... ignored")
                        continue
                    logging.info("Popping the saved speaker state")
                    if saved_speaker:
                        speaker = saved_speaker
                        speaker_name = speaker.player_name
                        logging.info("Saved speaker = '{}'".format(speaker_name))
                        saved_speaker = None
                    elif pushed:
                        saved_speaker = None
                        speaker = None
                        speaker_name = None
                    else:
                        logging.info("No saved speaker")
                    pushed = False
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
                        print("Not permitted: cannot create alias for 'alias'")
                        break
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
                                    "Error: Speaker '{}' not found".format(
                                        new_speaker_name
                                    )
                                )
                            else:
                                logging.info(
                                    "Set new active speaker: '{}'".format(
                                        new_speaker_name
                                    )
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
                            "Treating first parameter '{}' as speaker name".format(
                                args[0]
                            )
                        )
                        name = args.pop(0)
                        if name in ACTIONS_TO_EXEC_NO_SPEAKER:
                            print(
                                "Please set an active speaker to use the '{}' action".format(
                                    name
                                )
                            )
                            continue
                        else:
                            speaker = get_speaker(name, use_local_speaker_list)
                            if not speaker:
                                print(
                                    "Error: Speaker '{}' not found; should an active"
                                    " speaker be set?".format(name)
                                )
                                continue
                        if len(args) == 0:
                            print(
                                "Error: no action or arguments supplied for speaker"
                                " '{}'".format(speaker.player_name)
                            )
                            continue

                        # Temporarily establish an active speaker
                        temp_active_speaker = True
                        speaker_name = speaker.player_name
                        logging.info(
                            "Temporarily establish active speaker: '{}'".format(
                                speaker_name
                            )
                        )
                        # Replace the command sequence without the speaker name,
                        # for processing next time round the loop
                        command_sequences.insert(command_sequences.index(), args)
                        logging.info("Reinserting command sequence: {}".format(args))
                        continue

                    action = args.pop(0).lower()
                    logging.info("Action = '{}'; args = {}".format(action, args))
                    # Commands often requiring CTRL-C to exit are run in a subprocess
                    if (
                        action in ACTIONS_TO_EXEC
                        or action in ACTIONS_TO_EXEC_NO_SPEAKER
                    ):
                        _exec_action(speaker.ip_address, action, args)
                    else:
                        exit_code, output, error_msg = run_command(
                            speaker,
                            action,
                            *args,
                            use_local_speaker_list=use_local_speaker_list,
                        )
                        if exit_code:
                            if error_msg != "":
                                print(error_msg)
                        else:
                            if output != "":
                                print(output)
                            if action == "rename":
                                speaker_name = speaker.get_speaker_info(refresh=True)[
                                    "zone_name"
                                ]
                                _set_actions_and_commands_list(
                                    use_local_speaker_list=use_local_speaker_list
                                )
                    if temp_active_speaker:
                        logging.info(
                            "Unsetting temporary active speaker: '{}'".format(
                                speaker_name
                            )
                        )
                        temp_active_speaker = False
                        speaker = None
                        speaker_name = None
                except:
                    print("Error: Invalid command")

        # Catch all exceptions in the interactive loop
        except:
            continue


SHELL_COMMANDS = [
    "actions",
    "alias ",
    "cd",
    "check_for_update",
    "docs",
    "exec",
    "exit",
    "help",
    "pop",
    "push",
    "rescan",
    "rescan_max",
    "set ",
    "single-keystroke",
    "sk",
    "speakers",
    "version",
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
    list_actions(
        include_loop_actions=True,
        include_wait_actions=True,
        include_track_follow_actions=True,
    )
    print()


ACTIONS_LIST = []


def _set_actions_and_commands_list(use_local_speaker_list=False):
    logging.info("Rebuilding commands/action list")
    global ACTIONS_LIST
    ACTIONS_LIST = (
        [
            action + " "
            for action in get_actions(
                include_loop_actions=True,
                include_wait_actions=True,
                include_track_follow_actions=True,
            )
            + _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
        ]
        + SHELL_COMMANDS
        + am.alias_names()
    )


def _get_actions_and_commands():
    return ACTIONS_LIST


def _interactive_help():
    print(HELP_TEXT)


HELP_TEXT = """
This is SoCo-CLI interactive mode. Interactive commands are as follows:

    '1', ...     :  Set the active speaker. Use the numbers shown by the
                    'speakers' command. E.g., to set to speaker number 4
                    in the list, just type '4'.
                    '0' will unset the active speaker.
    'actions'    :  Show the complete list of SoCo-CLI actions.
    'alias'      :  Add an alias: alias <alias_name> <actions>
                    Remove an alias: alias <alias_name>
                    Update an alias by creating a new alias with the same name.
                    Using 'alias' without parameters shows the current list of
                    aliases.
                    Aliases override existing actions and can contain
                    sequences of actions.
    'cd'         :  Change the working directory of the shell, e.g. 'cd ..'.
                    Note that on Windows, backslashes must be doubled, e.g.:
                    'cd C:\\'
    'check_for_update' : Check whether an update is available
    'docs'       :  Print a link to the online documentation.
    'exec'       :  Run a shell command, e.g.: 'exec ls -l'.
    'exit'       :  Exit the shell.
    'help'       :  Show this help message (available shell commands).
    'pop'        :  Restore saved active speaker state.
    'push'       :  Save the current active speaker, and unset the active
                    speaker.
    'rescan'     :  If your speaker doesn't appear in the 'speakers' list,
                    use this to perform a more comprehensive scan.
    'rescan_max' :  Try this if you're having having trouble finding all your
                    speakers.
    'set <spkr>' :  Set the active speaker using its name.
                    Use quotes when needed for the speaker name, e.g.,
                    'set "Front Reception"'. Unambiguous, partial,
                    case-insensitive matches are supported, e.g., 'set front'.
                    To unset the active speaker, omit the speaker name,
                    or just enter '0'.
    'sk'         :  Enters 'single keystroke' mode. (Also 'single-keystroke'.)
    'speakers'   :  List the names of all available speakers.
    'version'    :  Print the versions of SoCo-CLI, SoCo, and Python in use.
    
    The action syntax is the same as when using 'sonos' from the command line.
    If a speaker has been set in the shell, omit the speaker name from the
    action.

    Use the arrow keys for command history and command editing.
    
    [Not Available on Windows] Use the TAB key for autocompletion of shell
    commands, SoCo-CLI actions, aliases, and speaker names.
"""


def _get_speaker_names(use_local_speaker_list=False):
    if use_local_speaker_list:
        names = local_speaker_list().get_all_speaker_names()
    else:
        try:
            names = speaker_cache().get_all_speaker_names()
        except Exception as e:
            print(
                "Speaker listing failed: please check your network connection [{}]".format(
                    e
                )
            )
            names = []
    return names


def _print_speaker_list(use_local_speaker_list=False):
    print()
    names = _get_speaker_names(use_local_speaker_list=use_local_speaker_list)
    if len(names) > 0:
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


class AliasProcessor:
    # The arg substitution names %1, ..., %9
    _arg_names = tuple("%" + str(x) for x in range(1, 10))

    def __init__(self):
        self._used_aliases = []
        self._recurse_level = 0
        self._command_count = 0
        self._index = 0
        self._command_list = []

    def process(self, command, am, command_list):
        self._recurse_level += 1
        alias_name = command[0]
        alias_parms = command[1:]
        self._command_list = command_list
        seq_number = len(command_list)

        logging.info(
            "Alias unpacking: recursion level {}, sequence number {}".format(
                self._recurse_level, seq_number + 1
            )
        )

        # Detect loops
        for used_alias in self._used_aliases:
            if used_alias[0] != self._recurse_level:
                if used_alias[1] == seq_number and used_alias[2] == alias_name:
                    # Alias name reused at different recursion levels but within
                    # the unpacking of the same sequence signifies a loop.
                    print("Error: Alias loop detected ... stopping")
                    self._remove_added_commands()
                    return False
        self._used_aliases.append((self._recurse_level, seq_number, alias_name))

        alias_actions = am.action(alias_name)
        try:
            action_elements = shlex_split(alias_actions)
        except ValueError as error:
            print("Error: {}".format(error))
            return False

        cli_parser = CLIParser()
        cli_parser.parse(action_elements)
        sequences = cli_parser.get_sequences()

        logging.info("Unpacking the alias '{}' -> '{}'".format(alias_name, sequences))

        index = command_list.index()
        for sequence in sequences:
            alias_parms_local = alias_parms.copy()
            # Positional argument substitution: %1, %2, etc.
            alias_parms_used = []
            for i, item in enumerate(sequence):
                if item in self._arg_names:
                    parm_index = int(item[1]) - 1
                    try:
                        sequence[i] = alias_parms_local[parm_index]
                        logging.info(
                            "Substituting '{}' for arg. {}".format(
                                alias_parms_local[parm_index], item
                            )
                        )
                        # This allows reuse of the same parameter
                        alias_parms_used.append(parm_index)
                    except IndexError:
                        logging.info("No value found for arg. {}".format(item))
                        sequence[i] = None

            # Remove unsatisfied arguments and substituted parameters
            sequence = [x for x in sequence if x is not None]
            alias_parms_local = [
                y for x, y in enumerate(alias_parms_local) if not x in alias_parms_used
            ]

            # Recurse if the sequence is itself an alias
            try:
                if sequence[0] in am.alias_names():
                    logging.info(
                        "Recursively unpacking the alias '{}'".format(sequence[0])
                    )
                    logging.info("Unpacking: '{}'".format(sequence + alias_parms_local))
                    if self.process(sequence + alias_parms_local, am, command_list):
                        index = command_list.index()
                    else:
                        return False

                # Not an alias, so insert the sequence in the command list
                # at the correct index, and increment the index
                else:
                    logging.info(
                        "Inserting new sequence {} at {}".format(sequence, index)
                    )
                    command_list.insert(index, sequence)
                    index += 1
                    self._command_count += 1
                    self._index = index
                    logging.info("Current command list = {}".format(command_list))
            except IndexError:
                logging.info("Empty sequence ... returning")
                return False

        self._recurse_level -= 1

        return True

    def _remove_added_commands(self):
        for _ in range(self._command_count):
            cmd = self._command_list.pop_next()
            logging.info("Removing command {}".format(cmd))


def _rescan(use_local_speaker_list=False, max_scan=False):
    try:
        if use_local_speaker_list:
            print("Using cached speaker list: no rescan performed")
        elif max_scan:
            logging.info("Full network rescan at max strength (timeout = 10.0s)")
            speaker_cache().scan(reset=True, scan_timeout_override=10.0)
            _print_speaker_list(use_local_speaker_list=use_local_speaker_list)
        else:
            logging.info("Full network rescan")
            speaker_cache().scan(reset=True)
            _print_speaker_list(use_local_speaker_list=use_local_speaker_list)
        _set_actions_and_commands_list(use_local_speaker_list=use_local_speaker_list)
    except Exception as e:
        print("Rescan failed: please check your network connection [{}]".format(e))


def _exec(command_args: List[str]) -> None:
    """Runs a command as a subprocess, in its own shell.

    Args:
        command_args (list): The command to execute.
    """

    # Check for spaces within any of the command line args,
    # and quote if required
    for index, cl_arg in enumerate(command_args):
        if " " in cl_arg:
            command_args[index] = '"' + command_args[index] + '"'

    # Convert command list to a unified command line
    command_line = " ".join(command_args)

    set_suspend_sighandling(suspend=True)
    try:
        logging.info("Running command: '{}'".format(command_line))
        subprocess.run(command_line, shell=True)
    except Exception as e:
        print(e)
    set_suspend_sighandling(suspend=False)


CTRL_C_MSG_ISSUED = False


def _exec_action(speaker_ip: str, action: str, args: List[str]) -> None:
    # Commands to run in a subprocess, to allow CTRL-C
    # to exit the subprocess only, and not the shell.

    if action in ACTIONS_TO_EXEC_NO_SPEAKER:
        command_line = [sys.argv[0], action, *args]
    else:
        command_line = [sys.argv[0], speaker_ip, action, *args]

    # Pass through logging option
    command_line.insert(1, LOG_SETTING)

    global CTRL_C_MSG_ISSUED
    if CTRL_C_MSG_ISSUED is False:
        print("(Use CTRL-C to return to the Sonos shell prompt.)")
        CTRL_C_MSG_ISSUED = True

    _exec(command_line)


def _exec_command_line(command_line: str) -> None:
    """Runs a sonos command line as a subprocess, in its own shell.

    Args:
        command_line (str): The command line to execute.
    """

    set_suspend_sighandling(suspend=True)
    try:
        logging.info("Running command: '{}'".format(command_line))
        subprocess.run(command_line, shell=True)
    except Exception as e:
        print(e)
    set_suspend_sighandling(suspend=False)


def _loop_in_command_sequences(command_sequences: RewindableList) -> bool:
    """Is there a loop statement in any of the command sequences?"""
    for sequence in command_sequences:
        if any(
            loop_action in sequence
            for loop_action in ["loop", "loop_until", "loop_for"]
        ):
            logging.info("'loop' action found in command sequences")
            return True
    return False


def _exec_loop(
    speaker: Union[SoCo, None],
    current_command: list,
    remaining_sequences: RewindableList,
    use_local: bool,
) -> bool:
    """If there's a loop statement, run the actions in a subprocess.

    Args:
        speaker (SoCo, None): The speaker to which the command is targeted, or
            None if the speaker is in the command line.
        current_command (list): The current command sequence
        remaining_sequences (RewindableList): The remaining list of command sequences
        use_local (bool): use the local speaker list.

    Returns:
        bool: True if there's a loop statement, False otherwise.
    """

    # Reassemble the complete command sequence list
    command_sequences = deepcopy(remaining_sequences)
    command_sequences.insert(0, current_command)

    if _loop_in_command_sequences(command_sequences):
        command_line = ""
        first = True
        while True:
            try:
                sequence = command_sequences.pop_next()
                if not first:
                    command_line += " : "
                command_line += " ".join(sequence)
                if first:
                    first = False
            except IndexError:
                break

        global LOG_SETTING
        sonos_command = "sonos " + LOG_SETTING + " "
        if speaker is not None:
            # This is a way of using the required speaker for each
            # invocation in the list of commands, using the SPKR env. variable.
            if UNIX:
                command_line = (
                    "export SPKR="
                    + speaker.ip_address
                    + " && "
                    + sonos_command
                    + command_line
                )
            elif WINDOWS:
                command_line = (
                    'set "SPKR='
                    + speaker.ip_address
                    + '" && '
                    + sonos_command
                    + command_line
                )
        else:
            if use_local:
                sonos_command = sonos_command + "-l "
            command_line = sonos_command + command_line
        logging.info("'loop' statement found, command line = '{}'".format(command_line))
        _exec_command_line(command_line)
        return True

    return False
