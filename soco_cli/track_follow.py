import logging
import re

from datetime import datetime, timezone
from time import sleep
from soco_cli.api import run_command


def track_follow(
    speaker, use_local_speaker_list=False, break_on_pause=True, compact=False
):
    """Print out the 'track' details each time the track changes.

    Args:
        speaker (SoCo): The speaker to follow.
        use_local_speaker_list (bool, optional): Use cached discovery.
        break_on_pause (bool, optional): Whether to return control if the
            speaker enters the paused or stopped playback states.

    This function operates as if 'outside' the main program logic, because
    it needs to output intermediate results as it executes. Hence, the
    'run_command()' API call is used.
    """

    def timestamp(short=False):
        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        if not short:
            return datetime.now(tz=local_tz).strftime("%H:%M:%S (%Z) %d-%b-%Y")
        else:
            return datetime.now(tz=local_tz).strftime("%H:%M")

    counter = 1
    print(flush=True)
    while True:
        # If stopped, wait for the speaker to start playback
        _, state, _ = run_command(
            speaker, "state", use_local_speaker_list=use_local_speaker_list
        )
        if state in [
            "STOPPED",
            "PAUSED_PLAYBACK",
        ]:
            if not compact:
                print(
                    " [{}] Playback is stopped or paused at {}\n".format(
                        speaker.player_name, timestamp()
                    ),
                    flush=True,
                )
            else:
                print(
                    "{:5d}: [{}] Playback is stopped or paused".format(
                        counter, timestamp(short=True)
                    )
                )
                counter += 1
            if break_on_pause:
                logging.info("Playback is paused/stopped; returning")
                break
            logging.info("Playback is paused/stopped; waiting for start")
            run_command(
                speaker, "wait_start", use_local_speaker_list=use_local_speaker_list
            )
            logging.info("Speaker has started playback")

        # Print the track info
        exit_code, output, error_msg = run_command(
            speaker, "track", use_local_speaker_list=use_local_speaker_list
        )
        if exit_code == 0:
            # Manipulate output
            if "Using Line In" in output:
                line_in = True
                output = "   Playing from Line In\n"
            else:
                line_in = False
                output = output.split("\n ", 1)[1]
            if not compact:
                # Remove some of the line entries
                output = re.sub(".*Playback.*\\n", "", output)
                # output = re.sub(".*Elapsed.*\\n", "", output)
                output = re.sub(".*URI.*\\n", "", output)
                output = re.sub(".*Uri.*\\n", "", output)
                # Prefix speaker name and timestamp
                output = (
                    " [{}] Playing at ".format(speaker.player_name)
                    + timestamp()
                    + ":\n"
                    + output
                )
            else:  # Compact (one line) output
                if line_in:
                    output = "{:5d}: [{}] Playing from Line In".format(
                        counter, timestamp(short=True)
                    )
                else:
                    # Ordering of keys determines output order
                    keys = [
                        "Channel:",
                        "Radio Show:",
                        "Artist:",
                        "Creator(s):",
                        "Book Title:",
                        "Chapter:",
                        "Album:",
                        "Podcast:",
                        "Title:",
                        "Release Date:",
                        "Narrator(s):",
                    ]
                    elements = {}
                    for line in output.splitlines():
                        for key in keys:
                            if key in line:
                                elements[key] = line.replace(key, "").lstrip()
                    output = "{:5d}: [{}] ".format(counter, timestamp(short=True))

                    # Prune fields for audio books
                    if "Book Title:" in elements:
                        elements.pop("Title:", None)
                        elements.pop("Narrator(s):", None)
                    first = True
                    for key in keys:
                        value = elements.pop(key, None)
                        if value:
                            if not first:
                                output = output + "| "
                            else:
                                first = False
                            output = output + key + " " + value + " "

            print(output, flush=True)
        else:
            error_out = "{:5d}: [{}] {}".format(
                counter, timestamp(short=True), error_msg
            )
            print(error_out, flush=True)

        logging.info("Waiting for end of track")
        run_command(
            speaker, "wait_end_track", use_local_speaker_list=use_local_speaker_list
        )

        logging.info("Waiting 1.5s for playback to stabilise")
        sleep(1.5)
        counter += 1
