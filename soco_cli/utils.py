import datetime
import logging
import os
import pickle
import sys
from collections.abc import Sequence
from platform import python_version
from signal import SIGTERM
from time import sleep

import soco

from .__init__ import __version__
from .match_speaker_names import speaker_name_matches
from .speakers import Speakers


def event_unsubscribe(sub):
    # Insert a brief pause before event unsubscription to prevent lockups,
    # by yielding the thread
    pause_seconds = 0.2
    logging.info(
        "Unsubscribing from events ... yield by pausing for {}s".format(pause_seconds)
    )
    sleep(pause_seconds)
    sub.unsubscribe()
    logging.info("Unsubscribed")


INTERACTIVE = False
API = False


def set_interactive():
    global INTERACTIVE
    INTERACTIVE = True


def set_api():
    global API
    API = True


# Error handling
def error_and_exit(msg):
    # Print to stderr
    print("Error:", msg, file=sys.stderr)
    # Use os._exit() to avoid the catch-all 'except'
    if not (INTERACTIVE or API):
        os._exit(1)


def parameter_type_error(action, required_params):
    msg = "Action '{}' takes parameter(s): {}".format(action, required_params)
    error_and_exit(msg)


def parameter_number_error(action, parameter_number):
    msg = "Action '{}' takes {} parameter(s)".format(action, parameter_number)
    error_and_exit(msg)


# Parameter count checking
def zero_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 0:
            parameter_number_error(args[1], "no")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def one_parameter(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 1:
            parameter_number_error(args[1], "1")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def zero_or_one_parameter(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) not in [0, 1]:
            parameter_number_error(args[1], "0 or 1")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def one_or_two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) not in [1, 2]:
            parameter_number_error(args[1], "1 or 2")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 2:
            parameter_number_error(args[1], "2")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def zero_one_or_two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) > 2:
            parameter_number_error(args[1], "zero, one or two")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


def one_or_more_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) < 1:
            parameter_number_error(args[1], "1 or more")
            return False
        else:
            return f(*args, **kwargs)

    return wrapper


# Time manipulation
def seconds_until(time_str):
    # target_time = datetime.time.fromisoformat(time_str)
    target_time = create_time_from_str(time_str)
    now_time = datetime.datetime.now().time()
    delta_target = datetime.timedelta(
        hours=target_time.hour, minutes=target_time.minute, seconds=target_time.second
    )
    delta_now = datetime.timedelta(
        hours=now_time.hour, minutes=now_time.minute, seconds=now_time.second
    )
    diff = int((delta_target - delta_now).total_seconds())
    # Ensure 'past' times are treated as future times by adding 24hr
    return diff if diff > 0 else diff + 24 * 60 * 60


def create_time_from_str(time_str):
    """Process times in HH:MM(:SS) format. Return a 'time' object."""
    if ":" not in time_str:
        raise ValueError
    parts = time_str.split(":")
    if len(parts) not in [2, 3]:
        raise ValueError
    hours = int(parts[0])
    minutes = int(parts[1])
    if len(parts) == 3:
        seconds = int(parts[2])
    else:
        seconds = 0
    # Accept time strings from 00:00:00 to 23:59:59
    if 0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59:
        return datetime.time(hour=hours, minute=minutes, second=seconds)
    else:
        raise ValueError


def convert_to_seconds(time_str):
    """Convert a time string to seconds.
    time_str can be one of Nh, Nm or Ns, or of the form HH:MM:SS
    :raises ValueError
    """
    logging.info("Converting '{}' to a number of seconds".format(time_str))
    time_str = time_str.lower()
    try:
        if ":" in time_str:  # Assume form is HH:MM:SS or HH:MM
            parts = time_str.split(":")
            if len(parts) == 3:  # HH:MM:SS
                td = datetime.timedelta(
                    hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2])
                )
            else:  # HH:MM
                td = datetime.timedelta(hours=int(parts[0]), minutes=int(parts[1]))
            return td.seconds
        elif time_str.endswith("s"):  # Seconds (explicit)
            duration = float(time_str[:-1])
        elif time_str.endswith("m"):  # Minutes
            duration = float(time_str[:-1]) * 60
        elif time_str.endswith("h"):  # Hours
            duration = float(time_str[:-1]) * 60 * 60
        else:  # Seconds (default)
            duration = float(time_str)
        return duration
    except:
        raise ValueError


# Miscellaneous
def convert_true_false(true_or_false, conversion="YesOrNo"):
    if conversion == "YesOrNo":
        return "Yes" if true_or_false is True else "No"
    if conversion == "onoroff":
        return "on" if true_or_false is True else "off"


def version():
    print("soco-cli version: {}".format(__version__))
    print("soco version:     {}".format(soco.__version__))
    print("python version:   {}".format(python_version()))


def docs():
    version = "v{}".format(__version__)
    if __version__.endswith("+"):
        url = "https://github.com/avantrec/soco-cli/blob/next_version/README.md"
    else:
        url = "https://github.com/avantrec/soco-cli/blob/{}/README.md".format(version)
    print("Online documentation for {}: {}".format(version, url))


def logo():
    version = "v{}".format(__version__)
    if __version__.endswith("+"):
        url = "https://raw.githubusercontent.com/avantrec/soco-cli/next_version/assets/soco-cli-logo-01-large.png"
    else:
        url = "https://raw.githubusercontent.com/avantrec/soco-cli/{}/assets/soco-cli-logo-01-large.png".format(
            version
        )
    print("SoCo-CLI Logo: {}".format(url))


# ToDo: Remove with SIGTERM fix
use_sigterm = False

# Stop a stream if playing a local file
speaker_playing_local_file = None


def set_sigterm(sigterm):
    global use_sigterm
    use_sigterm = sigterm


def set_speaker_playing_local_file(speaker):
    global speaker_playing_local_file
    speaker_playing_local_file = speaker


def sig_handler(signal_received, frame):
    # Exit silently without stack dump
    logging.info("Caught signal, exiting.")
    print(" CTRL-C ... exiting.")

    if speaker_playing_local_file:
        logging.info(
            "Speaker '{}': 'play_file' active ... stopping".format(
                speaker_playing_local_file.player_name
            )
        )
        speaker_playing_local_file.stop()

    # ToDo: Temporary for now; hard kill required to get out of 'wait_for_stopped'
    if use_sigterm:
        os.kill(os.getpid(), SIGTERM)
    else:
        exit(0)


class RewindableList(Sequence):
    """This is a just-enough-implementation class to provide a list
    that can be rewound during iteration.
    """

    def __init__(self, items):
        self._items = items
        self._index = 0

    def __iter__(self):
        return self

    def __getitem__(self, item):
        return self._items[item]

    def __len__(self):
        return len(self._items)

    def __next__(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        else:
            raise StopIteration

    def rewind(self):
        self._index = 0

    def rewind_to(self, index):
        if 0 <= index < len(self._items):
            self._index = index
        else:
            raise IndexError


# Set up logging
def configure_logging(log_level):
    log_level = log_level.lower()
    if log_level == "none":
        # Disables all logging (i.e., CRITICAL and below)
        logging.disable(logging.CRITICAL)
    else:
        log_format = (
            "%(asctime)s %(filename)s:%(lineno)s - %(funcName)s() - %(message)s"
        )
        if log_level == "debug":
            logging.basicConfig(format=log_format, level=logging.DEBUG)
        elif log_level == "info":
            logging.basicConfig(format=log_format, level=logging.INFO)
        elif log_level in ["warn", "warning"]:
            logging.basicConfig(format=log_format, level=logging.WARNING)
        elif log_level == "error":
            logging.basicConfig(format=log_format, level=logging.ERROR)
        elif log_level == "critical":
            logging.basicConfig(format=log_format, level=logging.CRITICAL)
        else:
            error_and_exit(
                "--log takes one of: NONE, DEBUG, INFO, WARN(ING), ERROR, CRITICAL"
            )


# Local speaker list operations
speaker_list = None


def set_speaker_list(s):
    global speaker_list
    speaker_list = s


SCAN_TIMEOUT = 0.1


class SpeakerCache:
    def __init__(self):
        # _cache contains (soco_instance, speaker_name) tuples
        self._cache = set()
        self._discovery_done = False

    @property
    def exists(self):
        return True if self._cache else False

    def cache_speakers(self, speakers):
        logging.info("Adding speakers to cache: {}".format(speakers))
        for speaker in speakers:
            self._cache.add((speaker, speaker.player_name))

    def discover(self):
        speakers = soco.discovery.discover(
            allow_network_scan=True, scan_timeout=SCAN_TIMEOUT
        )
        if speakers:
            self.cache_speakers(speakers)
        else:
            logging.info("No speakers found to cache")
        return None

    def scan(self, reset=False):
        if not self._discovery_done or reset:
            logging.info("Performing full discovery scan")
            speakers = soco.discovery.scan_network(
                multi_household=True, scan_timeout=SCAN_TIMEOUT
            )
            if speakers:
                self.cache_speakers(speakers)
                self._discovery_done = True
            else:
                logging.info("No speakers found to cache")
        else:
            logging.info("Full discovery scan already done, and reset not requested")
        return None

    def add(self, speaker):
        logging.info("Adding speaker to cache")
        self._cache.add((speaker, speaker.player_name))

    def find_indirect(self, name):
        speakers_found = set()
        speakers_found_names = set()
        for cached, cached_name in self._cache:
            for speaker in cached.visible_zones:
                match, exact = speaker_name_matches(name, speaker.player_name)
                if match and exact:
                    return speaker
                if match and not exact:
                    speakers_found.add(speaker)
                    speakers_found_names.add(speaker.player_name)

        if len(speakers_found) == 1:
            return speakers_found.pop()

        elif len(speakers_found) > 1:
            error_and_exit("'{}' is ambiguous: {}".format(name, speakers_found_names))
            return None

        else:
            return None

    def find(self, name):
        speakers_found = set()
        speakers_found_names = set()
        for speaker, speaker_name in self._cache:
            match, exact = speaker_name_matches(name, speaker_name)
            if match and exact:
                return speaker
            if match and not exact:
                speakers_found.add(speaker)
                speakers_found_names.add(speaker_name)

        if len(speakers_found) == 1:
            return speakers_found.pop()

        elif len(speakers_found) > 1:
            error_and_exit(
                "Speaker name '{}' is ambiguous within {}".format(
                    name, speakers_found_names
                )
            )
            return None

        else:
            return None

    def get_all_speakers(self):
        self.scan()
        return self._cache

    def get_all_speaker_names(self):
        self.scan()
        names = [speaker[1] for speaker in self._cache]
        names.sort()
        return names


# Single instance of the speaker cache
cache = SpeakerCache()


def speaker_cache():
    """Return the global speaker cache object"""
    return cache


def local_speaker_list():
    """Return the global speaker list object"""
    return speaker_list


def get_speaker(name, local=False):
    # Use an IP address
    # (Allow the use of an IP address even if 'local' is specified)
    if Speakers.is_ipv4_address(name):
        logging.info("Using IP address instead of speaker name")
        return soco.SoCo(name)

    # Use the local speaker list
    if local:
        logging.info("Using local speaker list")
        return speaker_list.find(name)

    # Use discovery
    else:
        # Try various lookup methods in order of expense,
        # and cache results where possible
        speaker = None
        if not speaker:
            logging.info("Trying direct cache lookup")
            speaker = cache.find(name)
        if not speaker:
            logging.info("Trying indirect cache lookup")
            speaker = cache.find_indirect(name)
        if not speaker:
            logging.info("Trying standard discovery with network scan fallback")
            cache.discover()
            speaker = cache.find(name)
        if not speaker:
            logging.info("Trying network scan discovery")
            cache.scan()
            speaker = cache.find(name)
        if speaker:
            logging.info("Successful speaker discovery")
        else:
            logging.info("Failed to discover speaker")
        return speaker


def get_right_hand_speaker(left_hand_speaker):
    # Get the right-hand speaker of a stereo pair when the
    # left-hand speaker is supplied
    if not left_hand_speaker.is_visible:
        # If not visible, this is not a left-hand speaker
        logging.info("Speaker is visible: not a left-hand speaker")
        return None
    else:
        # Find the speaker which is not visible, for which the
        # left-hand speaker is the coordinator, and not a Sub
        for rh_speaker in left_hand_speaker.all_zones:
            if (
                rh_speaker.group.coordinator.ip_address == left_hand_speaker.ip_address
                and not rh_speaker.is_visible
                and "sub" not in rh_speaker.get_speaker_info()["model_name"].lower()
            ):
                logging.info(
                    "Found right-hand speaker: {} / {}".format(
                        rh_speaker.player_name, rh_speaker.ip_address
                    )
                )
                return rh_speaker
        logging.info("Right-hand speaker not found")
        return None


def rename_speaker_in_cache(old_name, new_name):
    return speaker_list.rename(old_name, new_name)


# Argument processing
def configure_common_args(parser):
    """Set up the optional arguments common across the command line programs"""
    parser.add_argument(
        "--network-discovery-threads",
        "-t",
        type=int,
        default=256,
        help="Maximum number of threads for Sonos network discovery",
    )
    parser.add_argument(
        "--network-discovery-timeout",
        "-n",
        type=float,
        default=1.0,
        help="Network timeout for Sonos device scan (seconds)",
    )
    parser.add_argument(
        "--min_netmask",
        "-m",
        type=int,
        default=24,
        help="Minimum netmask for Sonos device scan (integer 0-32)",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        default=False,
        help="Print the soco-cli and SoCo versions and exit",
    )
    parser.add_argument(
        "--log",
        type=str,
        default="NONE",
        help="Set the logging level: 'NONE' (default) |'CRITICAL' | 'ERROR' | 'WARN'| 'INFO' | 'DEBUG'",
    )
    parser.add_argument(
        "--docs",
        action="store_true",
        default=False,
        help="Print the URL to the online documentation",
    )
    parser.add_argument(
        "--logo",
        action="store_true",
        default=False,
        help="Print the URL to the SoCo-CLI logo",
    )


def check_args(args):
    """Check values of parameters. Returns None, or an error message."""
    message = ""
    if not 0 <= args.min_netmask <= 32:
        message = (
            message + "\n    Option 'min_netmask' must be an integer between 0 and 32"
        )
    if not 0.0 <= args.network_discovery_timeout <= 60.0:
        message = message + "\n    Option 'network_timeout' must be between 0.0 and 60s"
    if not 1 <= args.network_discovery_threads <= 32000:
        message = message + "\n    Option 'threads' must be between 1 and 32000"
    if message == "":
        return None
    else:
        return message


path = os.path.expanduser("~") + "/.soco-cli/"
filename = "saved_search.pickle"
pathname = path + filename


def save_search(result):
    if not os.path.exists(path):
        os.mkdir(path)
    with open(pathname, "wb") as f:
        pickle.dump(result, f)
    logging.info("Saved search results at {}".format(pathname))
    return True


def read_search():
    if os.path.exists(pathname):
        logging.info("Loading search results from {}".format(pathname))
        try:
            with open(pathname, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logging.info("Failed to load search results: %s", e)
            pass
    return None
