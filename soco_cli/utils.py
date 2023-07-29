"""Common utilities used across multiple modules."""

import datetime
import logging
import os
import pickle
import signal

try:
    import readline
except ImportError:
    pass
import sys
from collections.abc import Sequence
from platform import python_version
from time import sleep

import soco  # type: ignore

from soco_cli.__init__ import __version__  # type: ignore
from soco_cli.match_speaker_names import speaker_name_matches
from soco_cli.speakers import Speakers


def event_unsubscribe(sub):
    """Unsubscribe from events, with a try/catch wrapper, and a pause
    introduced to yield the thread."""

    logging.info("Unsubscribing '{}'".format(sub))
    try:
        sleep(0.2)
        sub.unsubscribe()
    except Exception as e:
        logging.info("Failed to unsubscribe: {}".format(e))
    logging.info("Unsubscribed")


INTERACTIVE = False
API = False
SINGLE_KEYSTROKE = False


def set_interactive():
    global INTERACTIVE
    INTERACTIVE = True


def set_api():
    global API
    API = True


def set_single_keystroke(sk):
    global SINGLE_KEYSTROKE
    SINGLE_KEYSTROKE = sk


# Error handling
def error_report(msg):
    # Print to stderr
    print("Error:", msg, file=sys.stderr, flush=True)
    # Use os._exit() to avoid the catch-all 'except'
    if not (INTERACTIVE or API):
        logging.info("Exiting program using os._exit(1)")
        os._exit(1)


def parameter_type_error(action, required_params):
    msg = "Action '{}' takes parameter(s): {}".format(action, required_params)
    error_report(msg)


def parameter_number_error(action, parameter_number):
    msg = "Action '{}' takes {} parameter(s)".format(action, parameter_number)
    error_report(msg)


# Parameter count checking
def zero_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 0:
            parameter_number_error(args[1], "no")
            return False

        return f(*args, **kwargs)

    return wrapper


def one_parameter(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 1:
            parameter_number_error(args[1], "1")
            return False
        return f(*args, **kwargs)

    return wrapper


def zero_or_one_parameter(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) not in [0, 1]:
            parameter_number_error(args[1], "0 or 1")
            return False
        return f(*args, **kwargs)

    return wrapper


def one_or_two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) not in [1, 2]:
            parameter_number_error(args[1], "1 or 2")
            return False
        return f(*args, **kwargs)

    return wrapper


def two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) != 2:
            parameter_number_error(args[1], "2")
            return False
        return f(*args, **kwargs)

    return wrapper


def zero_one_or_two_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) > 2:
            parameter_number_error(args[1], "zero, one or two")
            return False
        return f(*args, **kwargs)

    return wrapper


def one_or_more_parameters(f):
    def wrapper(*args, **kwargs):
        if len(args[2]) < 1:
            parameter_number_error(args[1], "1 or more")
            return False
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

        if time_str.endswith("s"):  # Seconds (explicit)
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
    return None


def version():
    print("soco-cli version:   {}".format(__version__), flush=True)
    print("soco version:       {}".format(soco.__version__), flush=True)
    print("python version:     {}".format(python_version()), flush=True)
    print("command path:       {}".format(sys.argv[0]), flush=True)


def docs():
    version = "v{}".format(__version__)
    if __version__.endswith("+"):
        url = "https://github.com/avantrec/soco-cli/blob/next_version/README.md"
    else:
        url = "https://github.com/avantrec/soco-cli/blob/{}/README.md".format(version)
    print("Online documentation for {}: {}".format(version, url), flush=True)


def logo():
    version = "v{}".format(__version__)
    if __version__.endswith("+"):
        url = "https://raw.githubusercontent.com/avantrec/soco-cli/next_version/assets/soco-cli-logo-01-large.png"
    else:
        url = "https://raw.githubusercontent.com/avantrec/soco-cli/{}/assets/soco-cli-logo-01-large.png".format(
            version
        )
    print("SoCo-CLI Logo: {}".format(url), flush=True)


# Suspend signal handling processing for 'exec' in interactive shell
suspend_sighandling = False


def set_suspend_sighandling(suspend=True):
    global suspend_sighandling
    logging.info("Setting 'suspend_sighandling' to '{}'".format(suspend))
    suspend_sighandling = suspend


# Stop a stream if playing a local file
speaker_playing_local_file = None


def set_speaker_playing_local_file(speaker):
    global speaker_playing_local_file
    if speaker:
        logging.info(
            "Setting speaker playing local file to '{}'".format(speaker.player_name)
        )
    else:
        logging.info("No speaker playing local file")
    speaker_playing_local_file = speaker


def sig_handler(signal_received, frame):
    logging.info("Caught signal: {}".format(signal_received))

    if suspend_sighandling:
        logging.info("Signal handling suspended ... ignoring")
        return

    # Restore stdout and stderr ... these have been redirected if
    # api.run_command() was used
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    # Prevent SIGINT (CTRL-C) exit: untidy exit from readline can leave
    # some terminals in a broken state
    if signal_received == signal.SIGINT:
        if SINGLE_KEYSTROKE:
            logging.info("SINGLE_KEYSTROKE set ... preventing exit")
            print("\nPlease use 'x' to exit >> ", end="", flush=True)
            return

        if INTERACTIVE:
            logging.info("INTERACTIVE set ... preventing exit")
            print("\nPlease use 'exit' to terminate the shell > ", end="", flush=True)
            if os.name == "nt":
                print(flush=True)
            return

    # Allow SIGTERM termination, but issue warning if interactive
    if signal_received == signal.SIGTERM and INTERACTIVE:
        print("\nSoCo-CLI process terminating ...", flush=True)
        print(
            "This can leave some terminals in a misconfigured state.",
            flush=True,
        )

    if speaker_playing_local_file:
        logging.info(
            "Speaker '{}': 'play_file' active ... stopping".format(
                speaker_playing_local_file.player_name
            )
        )
        speaker_playing_local_file.stop()

    logging.info("Unsubscribing from event notifications")
    unsub_all_remembered_event_subs()

    logging.info("Exiting program using 'os._exit(0)'")
    print("", flush=True)
    os._exit(0)


class RewindableList(Sequence):
    """This is a just-enough-implementation class to provide a list
    that can be rewound during iteration.
    """

    def __init__(self, items=[]):
        self._items = items
        self._index = 0

    def __iter__(self):
        self.rewind()
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
        raise StopIteration

    def rewind(self):
        self._index = 0

    def rewind_to(self, index):
        if len(self._items) == 0 and index == 0:
            self._index = 0
        elif 0 <= index < len(self._items):
            self._index = index
        else:
            raise IndexError

    def __str__(self):
        return str(self._items)

    def index(self):
        return self._index

    def insert(self, index, element):
        self._items.insert(index, element)
        if index <= self._index:
            self._index += 1

    def pop_next(self):
        item = self._items.pop(0)
        if self._index != 0:
            self._index -= 1
        return item


# Set up logging
def configure_logging(log_level: str) -> None:
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
            error_report(
                "--log takes one of: NONE, DEBUG, INFO, WARN(ING), ERROR, CRITICAL"
            )


# Local speaker list operations
speaker_list = None


def set_speaker_list(s):
    global speaker_list
    speaker_list = s


class SpeakerCache:
    def __init__(self, max_threads=256, scan_timeout=0.1, min_netmask=24):
        # _cache contains (soco_instance, speaker_name) tuples
        self._cache = set()
        self._scan_done = False
        self._discovery_done = False
        self._max_threads = max_threads
        self._scan_timeout = scan_timeout
        self._min_netmask = min_netmask

    @property
    def exists(self):
        return bool(self._cache)

    def cache_speakers(self, speakers):
        logging.info("Adding speakers to cache: {}".format(speakers))
        for speaker in speakers:
            self._cache.add((speaker, speaker.player_name))

    def discover(self, reset=False):
        if not self._discovery_done or reset:
            # Clear the current cache
            self._cache = set()
            speakers = soco.discovery.discover(
                allow_network_scan=True,
                max_threads=self._max_threads,
                scan_timeout=self._scan_timeout,
                min_netmask=self._min_netmask,
            )
            if speakers:
                self.cache_speakers(speakers)
            else:
                logging.info("No speakers found to cache")
            self._discovery_done = True

    def scan(self, reset=False, scan_timeout_override=None):
        if not self._scan_done or reset:
            # Clear the current cache
            self._cache = set()
            scan_timeout = (
                scan_timeout_override if scan_timeout_override else self._scan_timeout
            )
            logging.info(
                "Performing full discovery scan with timeout = {}s".format(scan_timeout)
            )
            speakers = soco.discovery.scan_network(
                multi_household=True,
                max_threads=self._max_threads,
                scan_timeout=scan_timeout,
                min_netmask=self._min_netmask,
            )
            if speakers:
                self.cache_speakers(speakers)
                self._scan_done = True
            else:
                logging.info("No speakers found to cache")
        else:
            logging.info("Full discovery scan already done, and reset not requested")

    def add(self, speaker):
        logging.info("Adding speaker to cache")
        self._cache.add((speaker, speaker.player_name))

    def find_indirect(self, name):
        speakers_found = set()
        speakers_found_names = set()
        for cached, _ in self._cache:
            for speaker in cached.visible_zones:
                match, exact = speaker_name_matches(name, speaker.player_name)
                if match and exact:
                    return speaker
                if match and not exact:
                    speakers_found.add(speaker)
                    speakers_found_names.add(speaker.player_name)

        if len(speakers_found) == 1:
            return speakers_found.pop()

        if len(speakers_found) > 1:
            error_report("'{}' is ambiguous: {}".format(name, speakers_found_names))

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

        if len(speakers_found) > 1:
            error_report(
                "Speaker name '{}' is ambiguous within {}".format(
                    name, speakers_found_names
                )
            )

        return None

    def get_all_speakers(self, use_scan=False):
        if use_scan:
            self.scan()
        else:
            self.discover()
        return self._cache

    def get_all_speaker_names(self, use_scan=False):
        if use_scan:
            self.scan()
        else:
            self.discover()
        names = [speaker[1] for speaker in self._cache]
        names.sort()
        return names

    def rename_speaker(self, old_name, new_name):
        for speaker in self._cache:
            if speaker[1] == old_name:
                logging.info("Updating speaker cache with new name")
                self._cache.remove(speaker)
                self._cache.add((speaker[0], new_name))
                return True
        logging.info("Speaker with name '{}' not found".format(old_name))
        return False


SPKR_CACHE = None


# Single instance of the speaker cache
def create_speaker_cache(max_threads=256, scan_timeout=1.0, min_netmask=24):
    global SPKR_CACHE
    SPKR_CACHE = SpeakerCache(
        max_threads=max_threads, scan_timeout=scan_timeout, min_netmask=min_netmask
    )


def speaker_cache():
    """Return the global speaker cache object"""
    return SPKR_CACHE


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
    # Try various lookup methods in order of expense,
    # and cache results where possible
    speaker = None
    if not speaker:
        logging.info("Trying direct cache lookup")
        speaker = SPKR_CACHE.find(name)
    if not speaker:
        logging.info("Trying indirect cache lookup")
        speaker = SPKR_CACHE.find_indirect(name)
    if not speaker:
        logging.info("Trying standard discovery with network scan fallback")
        SPKR_CACHE.discover()
        speaker = SPKR_CACHE.find(name)
    if not speaker:
        logging.info("Trying network scan discovery")
        SPKR_CACHE.scan()
        speaker = SPKR_CACHE.find(name)
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


def rename_speaker_in_cache(old_name, new_name, use_local_speaker_list=True):
    if use_local_speaker_list:
        return speaker_list.rename(old_name, new_name)
    return SPKR_CACHE.rename_speaker(old_name, new_name)


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
        help="Print the SoCo-CLI and SoCo versions and exit",
    )
    parser.add_argument(
        "--log",
        type=str,
        default="NONE",
        help=(
            "Set the logging level: 'NONE' (default) |'CRITICAL' | 'ERROR' | 'WARN'|"
            " 'INFO' | 'DEBUG'"
        ),
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
    parser.add_argument(
        "--check_for_update",
        action="store_true",
        default=False,
        help="Check for a more recent version of SoCo-CLI",
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
    return None


filename = "queue_insertion_position.pickle"
queue_pathname = path + filename


def save_queue_insertion_position(queue_position: int):
    if not os.path.exists(path):
        os.mkdir(path)
    with open(queue_pathname, "wb") as f:
        pickle.dump(queue_position, f)
    logging.info("Saved queue position at {}".format(queue_pathname))
    return True


def get_queue_insertion_position() -> int:
    if os.path.exists(queue_pathname):
        logging.info("Loading queue_position from {}".format(queue_pathname))
        try:
            with open(queue_pathname, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logging.info("Failed to load queue_position: %s", e)
            raise e
    else:
        logging.info("No saved queue_position")
        raise FileNotFoundError


# Interactive shell history file
SOCO_CLI_DIR = os.path.join(os.path.expanduser("~"), ".soco-cli")
HIST_FILE = os.path.join(SOCO_CLI_DIR, "shell-history.txt")
HIST_LEN = 50


def save_readline_history():
    if not _confirm_soco_cli_dir():
        return
    logging.info("Saving shell history file: {}".format(HIST_FILE))
    try:
        readline.write_history_file(HIST_FILE)
    except Exception as e:
        logging.info("Error saving shell history file: {}".format(e))


def get_readline_history():
    if not os.path.exists(HIST_FILE):
        logging.info("No shell history file found: {}".format(HIST_FILE))
        return

    logging.info("Reading shell history file: {}".format(HIST_FILE))
    try:
        readline.read_history_file(HIST_FILE)
        readline.set_history_length(HIST_LEN)
    except Exception as e:
        logging.info("Error reading shell history file: {}".format(e))


def pretty_print_values(items, indent=2, separator=":", spacing=3, sort_by_key=False):
    """Print a list of keys and values.

    Args:
        items (dict): The keys and values to print.
        indent (int): Number of spaces to use as initial indentation.
        separator (str): The separator character(s) between the key and value.
        spacing (int): The minimum gap between the separator and
            the value.
        sort_by_key (bool): Whether to sort by item key.

    Example:
        One:     First
        Two:     Second
        Three:   Third
    """
    if len(items) == 0:
        return
    longest = max(len(key) for key in items)
    prefix = " " * indent
    key_vals = items.items()
    if sort_by_key:
        key_vals = sorted(key_vals)
    for key, value in key_vals:
        spacer = " " * (spacing + longest - len(key))
        print("{}{}{}{}{}".format(prefix, key, separator, spacer, value))


def playback_state(state):
    """Generate user-friendly playback states.

    Args:
        state (str): The Sonos-supplied state string.

    Returns:
        str: A user-friendly playback state description.
    """
    playback_mapping = {
        "STOPPED": "stopped",
        "PAUSED_PLAYBACK": "paused",
        "PLAYING": "in progress",
        "TRANSITIONING": "in a transitioning state",
    }
    try:
        return playback_mapping[state]
    except KeyError:
        return "unknown"


# Ensure that event subscriptions are cleared on CTRL-C
SUBS_LIST = set()


def _confirm_soco_cli_dir() -> bool:
    if not os.path.exists(SOCO_CLI_DIR):
        logging.info("Creating directory '{}'".format(SOCO_CLI_DIR))
        try:
            os.mkdir(SOCO_CLI_DIR)
            return True
        except:
            error_report("Failed to create directory '{}'".format(SOCO_CLI_DIR))
            return False


def remember_event_sub(sub):
    global SUBS_LIST
    logging.info("Adding event subscription record: '{}'".format(sub))
    SUBS_LIST.add(sub)


def forget_event_sub(sub):
    global SUBS_LIST
    try:
        logging.info("Removing event subscription record: '{}'".format(sub))
        SUBS_LIST.remove(sub)
    except KeyError:
        pass


def unsub_all_remembered_event_subs():
    global SUBS_LIST
    for sub in SUBS_LIST:
        try:
            event_unsubscribe(sub)
        except:
            break
    SUBS_LIST.clear()


def create_list_of_items_from_range(range_definition: str, upper_limit: int):
    """
    Take a range string and generate a set of items defined by the
    range.
    """
    if "all" in range_definition.lower():
        return [item for item in range(1, upper_limit + 1)]
    items_set = set()
    for range_element in range_definition.split(","):
        # Check for a range ('x-y') instead of a single integer
        if "-" in range_element:
            rng = range_element.split("-")
            if len(rng) != 2:
                raise IndexError(
                    "Invalid range specification '{}'".format(range_element)
                )
            index_1 = int(rng[0])
            index_2 = int(rng[1])
            if index_1 > index_2:  # Reverse the indices
                index_2, index_1 = index_1, index_2
            if not (0 < index_1 <= upper_limit and index_1 <= index_2 <= upper_limit):
                raise IndexError("Item(s) out of range in '{}'".format(range_element))
            for i in range(index_1, index_2 + 1):
                items_set.add(i)
        else:
            index = int(range_element)
            if not 0 < index <= upper_limit:
                raise IndexError("Item out of range '{}'".format(range_element))
            items_set.add(index)
    return sorted(list(items_set))
