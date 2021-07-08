"""Process the speaker-independent 'wait' actions."""

import logging
import time

from soco_cli.utils import convert_to_seconds, error_report, seconds_until


def process_wait(sequence):
    if sequence[0] in ["wait", "wait_for"]:
        duration = 0
        if len(sequence) != 2:
            error_report(
                "Action 'wait' requires 1 parameter (check spaces around the ':' separator?)"
            )
            return
        action = sequence[1].lower()
        try:
            duration = convert_to_seconds(action)
        except ValueError:
            error_report(
                "Action 'wait' requires positive number of hours, seconds or minutes + 'h/m/s', or HH:MM(:SS)"
            )
        logging.info("Waiting for {}s".format(duration))
        time.sleep(duration)

    # Special case: the 'wait_until' action
    elif sequence[0] in ["wait_until"]:
        if len(sequence) != 2:
            error_report(
                "'wait_until' requires 1 parameter (check spaces around the ':' separator?)"
            )
            return
        try:
            action = sequence[1].lower()
            duration = seconds_until(action)
            logging.info("Waiting for {}s".format(duration))
            time.sleep(duration)
        except ValueError:
            error_report(
                "'wait_until' requires parameter: time in 24hr HH:MM(:SS) format"
            )
