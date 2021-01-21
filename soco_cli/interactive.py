""" SoCo-CLI interactive mode handler """

import logging
import readline

from .utils import error_and_exit, get_speaker, set_interactive

from shlex import split as shlex_split

from .action_processor import process_action


def interactive_loop(speaker_name, use_local_speaker_list=False, no_env=False):

    # Is the speaker name set on the command line?
    # Note: ignores speaker set as part of the environment
    speaker = None
    if speaker_name:
        speaker = get_speaker(speaker_name, use_local_speaker_list)
        if not speaker:
            error_and_exit("Speaker '{}' not found".format(speaker_name))

    print("Entering SoCo-CLI interactive mode")

    # readline.parse_and_bind('tab: complete')
    # readline.set_completer(_completer)
    # readline.set_completer_delims(' ')

    set_interactive()
    while True:
        if speaker_name and speaker:
            command = input(
                "Enter sonos action (0 to exit) [{}] > ".format(speaker.player_name)
            )
        else:
            command = input("Enter sonos action (0 to exit) [] > ")
        if command == "0" or command.lower().startswith("exit"):
            logging.info("Exiting interactive mode")
            return True

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