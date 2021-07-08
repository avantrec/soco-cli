"""Checks GitHub for a later version of SoCo-CLI"""

import logging
from urllib.request import urlopen

from soco_cli.__init__ import __version__
from soco_cli.utils import error_report

init_file_url = (
    "https://raw.githubusercontent.com/avantrec/soco-cli/master/soco_cli/__init__.py"
)


def get_latest_version():
    try:
        file = urlopen(init_file_url, timeout=3.0)
    except Exception as e:
        error_report(
            "Unable to get latest version information from GitHub: {}".format(e)
        )
        return False

    for line in file:
        decoded_line = line.decode("utf-8")
        if "__version__" in decoded_line:
            latest_version = (
                decoded_line.replace("__version__ = ", "")
                .replace('"', "")
                .replace("\n", "")
            )
            logging.info("Latest version is v{}".format(latest_version))
            break
    else:
        logging.info("Unable to find latest version")
        return None

    return latest_version


def print_update_status():
    latest_version = get_latest_version()
    if latest_version is not None:
        if __version__ == latest_version:
            print("SoCo-CLI is up to date")
        else:
            print("An update is available: v" + latest_version)
        return True

    return False


def update_available():
    if __version__ == get_latest_version():
        return False

    return True
