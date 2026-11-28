"""The SoCo-CLI API.

Provides a few simple, high-level functions that allow the features of SoCo-CLI
to be used in other programs.
"""

import logging
import sys
import threading
from io import StringIO
from signal import SIGINT, signal
from typing import Any, Optional, Tuple, Union

from soco import SoCo  # type: ignore

from soco_cli.action_processor import process_action
from soco_cli.speakers import Speakers
from soco_cli.utils import (
    configure_logging,
    create_speaker_cache,
    get_speaker,
    set_api,
    set_speaker_list,
    sig_handler,
    speaker_cache,
)

# Output capture for run_command() and get_soco_object(). Commands can run
# concurrently in different threads (e.g., the HTTP API server runs requests on
# a thread pool), so capturing must not swap the process-wide sys.stdout and
# sys.stderr per command. Instead, while any thread is capturing, they are
# replaced by proxies that send each write to the calling thread's capture
# buffer, if it has one. When the last capture ends, the original streams are
# put back, so that code that runs between commands (e.g., a logging handler
# created then) sees the real streams.

# Per-thread capture buffers, shared by all proxies: '_capture.stdout' and
# '_capture.stderr' are set to a StringIO while that thread captures output.
_capture = threading.local()

# The number of captures in progress on all threads, and the lock that guards
# it and the installing and removing of the proxies
_active_captures = 0
_captures_lock = threading.Lock()


class _ThreadLocalStream:
    """Stands in for sys.stdout or sys.stderr.

    Writes go to the calling thread's capture buffer if it has one, otherwise
    to the stream that was in place when the proxy was installed. All other
    attributes (isatty(), encoding, fileno(), ...) come from the same target.
    """

    def __init__(self, name: str, stream: Any) -> None:
        self._name = name
        self._stream = stream

    def _target(self) -> Any:
        buffer = getattr(_capture, self._name, None)
        return buffer if buffer is not None else self._stream

    def write(self, text: str) -> int:
        return self._target().write(text)

    def flush(self) -> None:
        self._target().flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target(), name)


def _begin_capture() -> None:
    """Count a new capture, and install the proxies if they are not in place.
    Checked on every capture, since other code may assign to sys.stdout or
    sys.stderr while another capture is in progress."""
    global _active_captures
    with _captures_lock:
        stdout, stderr = sys.stdout, sys.stderr
        # Make both proxies before installing either, so that a failure
        # leaves both streams as they are
        if not isinstance(stdout, _ThreadLocalStream):
            stdout = _ThreadLocalStream("stdout", stdout)
        if not isinstance(stderr, _ThreadLocalStream):
            stderr = _ThreadLocalStream("stderr", stderr)
        sys.stdout, sys.stderr = stdout, stderr
        _active_captures += 1


def _end_capture() -> None:
    """Count the end of a capture. When no captures are left on any thread,
    put back the streams that the proxies replaced. A stream that other code
    has replaced in the meantime is left as it is."""
    global _active_captures
    with _captures_lock:
        _active_captures -= 1
        if _active_captures == 0:
            # Read each stream once: other code may assign to it at any time
            stdout, stderr = sys.stdout, sys.stderr
            if isinstance(stdout, _ThreadLocalStream):
                sys.stdout = stdout._stream
            if isinstance(stderr, _ThreadLocalStream):
                sys.stderr = stderr._stream


def _end_thread_capture(stdout: bool = True, stderr: bool = True) -> None:
    """Stop capturing output on the calling thread only. Its writes then go to
    the original streams. Captures on other threads continue. Use this
    instead of assigning sys.__stdout__ to sys.stdout, which would end the
    captures on all threads."""
    if stdout:
        _capture.stdout = None
    if stderr:
        _capture.stderr = None


def run_command(
    speaker_name: Union[str, SoCo],
    action: str,
    *args: str,  # Means that all args are strings
    use_local_speaker_list: bool = False,
    redirect_io: bool = True,
) -> Tuple[int, str, str]:
    """Use SoCo-CLI to run a sonos command.

    The exit code, output string and error message string are returned as a
    three-tuple. If the exit code is non-zero, the error message will be
    populated and the output string will always be an empty string.

    All exceptions are caught when this function is run. Exception details
    will be returned in the error message string.

    Args:
        speaker_name (str or SoCo): The name of the speaker, or its IP address.
            Alternatively, a 'SoCo' object can be supplied.
        action (str): The name of the SoCo-CLI action to perform.
        *args (list[str]): The set of arguments that accompany the action.
        use_local_speaker_list (bool, optional): Whether to use the local
            speaker cache.
        redirect_io (bool, optional): Whether to redirect stdout and stderr
            to capture their output for inclusion in the return value. If
            False, messages will be emitted directly to stdout & stderr
            during execution of the command, and this content will not be
            included in the return tuple.

    Returns:
        (int, str, str): a three-tuple of exit_code, output_string and
        error_msg. If redirect_io is false, output_string will be empty.

    Note:
        To capture output per thread, a call with redirect_io=True (the
        default) replaces sys.stdout and sys.stderr with proxy objects while
        it runs. When no command is capturing output on any thread, the
        streams that the proxies replaced are put back. While the proxies are
        in place, writes from threads that are not capturing output still go
        to the original streams, which may be a caller's own redirection.

        Code that runs on another thread during a command sees the proxies:

        - A check of 'sys.stdout is sys.__stdout__', or of the type of
          sys.stdout or sys.stderr, sees the proxy.
        - A logging handler created at that time keeps the proxy as its
          stream after the command ends. Records that it handles on a thread
          that is capturing output, during a later command, go into that
          command's output or error_msg.
        - Code that assigns to sys.stdout or sys.stderr (e.g.,
          contextlib.redirect_stdout(), which is not thread-safe) can send
          the rest of the command's output outside its result. If it puts
          back a proxy after the command has ended, the proxy stays in place
          until the next command ends.
    """

    # Prevent errors from causing exit
    set_api()

    if not redirect_io:
        return_tuple = _run_command(speaker_name, action, args, use_local_speaker_list)
    else:
        # Capture this thread's stdout and stderr for the duration of this
        # command
        saved_stdout = getattr(_capture, "stdout", None)
        saved_stderr = getattr(_capture, "stderr", None)
        output = StringIO()
        error = StringIO()
        _begin_capture()
        try:
            _capture.stdout, _capture.stderr = output, error
            return_tuple = _run_command(
                speaker_name, action, args, use_local_speaker_list, output, error
            )
        finally:
            # Restore any capture that was already in progress on this thread
            _capture.stdout, _capture.stderr = saved_stdout, saved_stderr
            _end_capture()

    # Log after the capture has ended. If logging is not configured yet, this
    # call creates the root handler. Unless a command is running on another
    # thread, the real stderr is in place, so the handler doesn't bind to a
    # capture proxy.
    logging.info("Return value: {}".format(return_tuple))

    return return_tuple


def _run_command(
    speaker_name: Union[str, SoCo],
    action: str,
    args: Tuple[str, ...],
    use_local_speaker_list: bool,
    output: Optional[StringIO] = None,
    error: Optional[StringIO] = None,
) -> Tuple[int, str, str]:
    """Internal helper for run_command(): runs the command, with stdout and
    stderr already redirected to 'output' and 'error' if these are supplied."""

    speaker = None
    exception_error = None

    # Can pass a SoCo object instead of the speaker name
    if isinstance(speaker_name, SoCo):
        speaker = speaker_name

    elif isinstance(speaker_name, str):
        try:
            speaker = _get_soco_object(
                speaker_name, use_local_speaker_list=use_local_speaker_list
            )
        except Exception as e:
            logging.info("Exception: {}".format(e))
            exception_error = e

    if speaker:
        action_return = False
        try:
            action_return = process_action(
                speaker, action, args, use_local_speaker_list=use_local_speaker_list
            )
        except Exception as e:
            logging.info("Exception: {}".format(e))
            exception_error = e

        if output is not None and error is not None:
            output_msg = output.getvalue().rstrip()
            error_out = error.getvalue().rstrip()
        else:
            output_msg = ""
            error_out = ""

        if output_msg != "":
            lines = output_msg.splitlines()
            if len(lines) > 1 and lines[0] != "":
                output_msg = "\n" + output_msg
            if len(lines) > 1 and output_msg[len(lines) - 1] != "":
                output_msg = output_msg + "\n"

        if exception_error:
            if error_out:
                error_out = error_out + "\nError: " + str(exception_error)
            else:
                error_out = "Error: " + str(exception_error)

        if action_return is False:
            if error_out == "":
                hint = " ... missing spaces around ':'?" if ":" in action else ""
                error_out = "Error: Action '{}' not recognised{}".format(action, hint)
            return_tuple = (1, output_msg, error_out)
        else:
            return_tuple = (0, output_msg, error_out)
    else:
        return_tuple = (
            1,
            "",
            "Speaker '{}' not found: {}".format(speaker_name, exception_error),
        )

    return return_tuple


def set_log_level(log_level: str = "None") -> None:
    """Convenience function to set up logging.

    Args:
        log_level (str): Can be one of None, Critical, Error, Warn, Info, Debug.
    """
    configure_logging(log_level)


def handle_sigint() -> None:
    """Convenience function to set up a graceful CTRL-C (sigint) handler."""
    signal(SIGINT, sig_handler)


def rescan_speakers(timeout: float = None) -> None:
    """Run full network scan to find speakers."""
    _check_for_speaker_cache()
    speaker_cache().scan(reset=True, scan_timeout_override=timeout)


def rediscover_speakers() -> None:
    """Run normal SoCo discovery to discover speakers."""
    _check_for_speaker_cache()
    speaker_cache().discover(reset=True)


def get_all_speakers(use_scan: bool = False) -> list:
    """Return all SoCo instances."""
    _check_for_speaker_cache()
    return [s[0] for s in speaker_cache().get_all_speakers(use_scan=use_scan)]


def get_all_speaker_names(use_scan: bool = False) -> list:
    """Return all speaker names."""
    _check_for_speaker_cache()
    return speaker_cache().get_all_speaker_names(use_scan=use_scan)


def get_soco_object(
    speaker_name: str, use_local_speaker_list: bool = False
) -> Tuple[Union[SoCo, None], str]:
    """Uses the full set of soco_cli strategies to find a speaker.

    Args:
        speaker_name (str): The name of the speaker to find.
        use_local_speaker_list (bool, optional): Whether to use the local
            speaker cache.

    Returns:
        (SoCo, str): Tuple of SoCo object, or None if no speaker is found,
        and an error message.

    Note:
        As with run_command(), sys.stdout and sys.stderr are replaced with
        proxy objects while the call runs. See the note on run_command().
    """
    set_api()

    saved_stderr = getattr(_capture, "stderr", None)
    error = StringIO()
    _begin_capture()
    try:
        _capture.stderr = error
        speaker = _get_soco_object(speaker_name, use_local_speaker_list)
    finally:
        _capture.stderr = saved_stderr
        _end_capture()

    error_msg = error.getvalue().rstrip()
    if not speaker and error_msg == "":
        error_msg = "Speaker not found"

    return speaker, error_msg


def _get_soco_object(speaker_name: str, use_local_speaker_list: bool = False) -> SoCo:
    """Internal helper version that doesn't redirect stderr."""

    if use_local_speaker_list:
        _setup_local_speaker_list()

    _check_for_speaker_cache()

    return get_speaker(speaker_name, use_local_speaker_list)


def _check_for_speaker_cache() -> None:
    if not speaker_cache():
        create_speaker_cache(max_threads=256, scan_timeout=1.0, min_netmask=24)


# For local speaker list operations
speaker_list_set = False


def _setup_local_speaker_list() -> None:
    global speaker_list_set
    if not speaker_list_set:
        speaker_list = Speakers()
        if not speaker_list.load():
            logging.info("Start speaker discovery")
            speaker_list.discover()
            speaker_list.save()
        set_speaker_list(speaker_list)
    speaker_list_set = True
