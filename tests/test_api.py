"""Tests for the thread safety of api.run_command().

run_command() captures a command's output per thread: while any command
runs, proxies replace sys.stdout and sys.stderr and send each write to the
calling thread's capture buffer. The HTTP API server runs requests on a
thread pool, so concurrent calls must not lose or mix up each other's output.
No live Sonos network is required: the speaker and the action are mocked.
"""

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from soco import SoCo  # type: ignore

import soco_cli.http_api as http_api
from soco_cli.api import _ThreadLocalStream, get_soco_object, run_command
from soco_cli.play_local_file_lists import play_file_list
from soco_cli.utils import sig_handler

THREADS = 16
ROUNDS = 5


@pytest.fixture(autouse=True)
def restore_std_streams():
    """Put stdout/stderr back even if a test leaves them redirected."""
    stdout, stderr = sys.stdout, sys.stderr
    yield
    sys.stdout, sys.stderr = stdout, stderr


def _make_speaker(name):
    speaker = MagicMock(spec=SoCo)
    speaker.player_name = name
    speaker.ip_address = "192.0.2.1"
    return speaker


def _slow_action(speaker, action, args, use_local_speaker_list=False):
    """Print a per-call token in two parts, yielding to other threads between."""
    print(args[0], end="")
    time.sleep(0.001)
    print("-done")
    return True


def _run_concurrently(target):
    """Run target(i) on THREADS threads that start together; return results."""
    barrier = threading.Barrier(THREADS)
    results = [None] * THREADS

    def worker(i):
        barrier.wait()
        results[i] = target(i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_run_command_outputs_are_isolated():
    speaker = _make_speaker("Kitchen")
    with patch("soco_cli.api.process_action", side_effect=_slow_action):
        for _ in range(ROUNDS):
            results = _run_concurrently(
                lambda i: run_command(speaker, "test", "token{}".format(i))
            )
            for i, result in enumerate(results):
                assert result == (0, "token{}-done".format(i), "")


def test_concurrent_http_commands_get_their_own_results():
    """command_core() also prints a log line per request; that line must not
    land in another request's captured result."""
    speaker = _make_speaker("Kitchen")
    with patch("soco_cli.http_api.get_speaker", return_value=(speaker, "")):
        with patch("soco_cli.api.process_action", side_effect=_slow_action):
            for _ in range(ROUNDS):
                results = _run_concurrently(
                    lambda i: http_api.command_core(
                        "Kitchen", "test", "token{}".format(i)
                    )
                )
                for i, result in enumerate(results):
                    assert result["exit_code"] == 0
                    assert result["result"] == "token{}-done".format(i)


def test_fast_command_is_not_held_up_by_slow_command():
    """A long-running action (e.g., wait_stop) must not block other requests,
    such as the 'pause' that would end it."""
    speaker = _make_speaker("Kitchen")
    entered = threading.Event()
    release = threading.Event()
    fast_result = []

    def actions(speaker, action, args, use_local_speaker_list=False):
        if action == "wait_stop":
            entered.set()
            release.wait(10)
        print("ok")
        return True

    with patch("soco_cli.http_api.get_speaker", return_value=(speaker, "")):
        with patch("soco_cli.api.process_action", side_effect=actions):
            slow = threading.Thread(
                target=http_api.command_core, args=("Kitchen", "wait_stop")
            )
            fast = threading.Thread(
                target=lambda: fast_result.append(
                    http_api.command_core("Kitchen", "pause")
                )
            )
            slow.start()
            try:
                assert entered.wait(5)
                # The 'pause' must finish while 'wait_stop' is still held
                fast.start()
                fast.join(5)
                assert not fast.is_alive(), "'pause' was held up by 'wait_stop'"
                assert slow.is_alive()
            finally:
                release.set()
                slow.join(10)
                if fast.is_alive():
                    fast.join(10)
    assert fast_result[0]["result"] == "ok"


def test_concurrent_http_lookups_and_actions_keep_their_own_stderr():
    """Requests that overlap in the speaker lookup (get_soco_object()) and in
    the action each get back only their own stderr diagnostics. Discovery is
    mocked below get_soco_object(): half of the lookups fail with a message
    on stderr, the other half find a speaker whose action writes to both
    streams."""

    class Cache:
        def find(self, name):
            print("lookup-" + name, end="", file=sys.stderr)
            time.sleep(0.001)
            print("-done", file=sys.stderr)
            return _make_speaker(name) if name.startswith("found") else None

        def find_indirect(self, name):
            return None

        def discover(self):
            pass

        def scan(self):
            pass

    def action(speaker, action, args, use_local_speaker_list=False):
        name = speaker.player_name
        print("out-" + name, end="")
        print("err-" + name, end="", file=sys.stderr)
        time.sleep(0.001)
        print("-done")
        print("-done", file=sys.stderr)
        return True

    def request(i):
        name = "found{}".format(i) if i % 2 else "missing{}".format(i)
        return name, http_api.command_core(name, "test")

    with patch("soco_cli.utils.SPKR_CACHE", Cache()):
        with patch("soco_cli.api.process_action", side_effect=action):
            for _ in range(ROUNDS):
                for name, result in _run_concurrently(request):
                    if name.startswith("found"):
                        assert result["exit_code"] == 0
                        assert result["result"] == "out-{}-done".format(name)
                        assert result["error_msg"] == "err-{}-done".format(name)
                    else:
                        # The lookup tries the cache three times
                        assert result["exit_code"] == 1
                        lines = result["error_msg"].splitlines()
                        assert lines == ["lookup-{}-done".format(name)] * 3


def test_command_log_line_is_one_write():
    """command_core() writes its log line, newline included, in one write()
    call, so lines from concurrent requests can't run together."""
    writes = []

    class Recorder:
        def write(self, text):
            writes.append(text)
            return len(text)

        def flush(self):
            pass

    speaker = _make_speaker("Kitchen")
    with patch("soco_cli.http_api.get_speaker", return_value=(speaker, "")):
        with patch("soco_cli.http_api.sc_run", return_value=(0, "20", "")):
            sys.stdout = Recorder()
            http_api.command_core("Kitchen", "volume")
    assert writes == [
        http_api.PREFIX + "Command = 'sonos Kitchen volume', exit code = 0\n"
    ]


def test_run_command_restores_previous_streams(capsys):
    """After a command, output goes to the streams in place before it."""
    speaker = _make_speaker("Kitchen")
    with patch("soco_cli.api.process_action", side_effect=_slow_action):
        run_command(speaker, "test", "token")
    print("after-out")
    print("after-err", file=sys.stderr)
    captured = capsys.readouterr()
    assert captured.out == "after-out\n"
    assert captured.err == "after-err\n"


def test_output_after_command_reaches_file_descriptors(capfd):
    speaker = _make_speaker("Kitchen")
    with patch("soco_cli.api.process_action", side_effect=_slow_action):
        assert run_command(speaker, "test", "token") == (0, "token-done", "")
    print("after-out")
    assert capfd.readouterr().out == "after-out\n"


def test_original_streams_are_put_back_after_command():
    speaker = _make_speaker("Kitchen")
    stdout, stderr = sys.stdout, sys.stderr

    def fail(speaker, action, args, use_local_speaker_list=False):
        raise RuntimeError("failed")

    with patch("soco_cli.api.process_action", side_effect=_slow_action):
        run_command(speaker, "test", "token")
    assert (sys.stdout, sys.stderr) == (stdout, stderr)
    with patch("soco_cli.api.process_action", side_effect=fail):
        assert run_command(speaker, "test") == (1, "", "Error: failed")
    assert (sys.stdout, sys.stderr) == (stdout, stderr)
    with patch("soco_cli.api.get_speaker", side_effect=RuntimeError("failed")):
        with pytest.raises(RuntimeError):
            get_soco_object("Kitchen")
    assert (sys.stdout, sys.stderr) == (stdout, stderr)


def test_failure_before_capture_leaves_no_proxies():
    """If setting up a capture fails, a later command still puts the original
    streams back."""
    speaker = _make_speaker("Kitchen")
    stdout, stderr = sys.stdout, sys.stderr
    with patch("soco_cli.api.StringIO", side_effect=MemoryError):
        with pytest.raises(MemoryError):
            run_command(speaker, "test")
        with pytest.raises(MemoryError):
            get_soco_object("Kitchen")
    with patch("soco_cli.api.process_action", side_effect=_slow_action):
        assert run_command(speaker, "test", "token") == (0, "token-done", "")
    assert (sys.stdout, sys.stderr) == (stdout, stderr)


def test_failure_to_make_proxy_leaves_streams_in_place():
    """If making the stderr proxy fails, the stdout proxy isn't installed
    either."""
    speaker = _make_speaker("Kitchen")
    stdout, stderr = sys.stdout, sys.stderr
    make_proxy = _ThreadLocalStream.__init__

    def fail_for_stderr(self, name, stream):
        if name == "stderr":
            raise MemoryError
        make_proxy(self, name, stream)

    with patch.object(_ThreadLocalStream, "__init__", fail_for_stderr):
        with pytest.raises(MemoryError):
            run_command(speaker, "test")
    assert (sys.stdout, sys.stderr) == (stdout, stderr)


def test_stream_replaced_during_command_is_kept():
    """If code replaces sys.stdout while a command runs, the replacement stays
    in place after the command."""
    speaker = _make_speaker("Kitchen")
    replacement = StringIO()

    def replace(speaker, action, args, use_local_speaker_list=False):
        sys.stdout = replacement
        return True

    with patch("soco_cli.api.process_action", side_effect=replace):
        run_command(speaker, "test")
    assert sys.stdout is replacement


def test_proxies_stay_while_another_thread_captures():
    """The proxies are put back only when the last capture on any thread ends.
    Meanwhile, code that checks isatty(), encoding or fileno() on a thread
    that is not capturing still sees the real stream."""
    with open(os.devnull, "w") as real:
        sys.stdout = real
        during = {}

        def check():
            during["proxy"] = sys.stdout is not real
            during["attributes"] = (
                sys.stdout.fileno(),
                sys.stdout.encoding,
                sys.stdout.isatty(),
            )

        assert _capture_across(check) == (0, "before-after", "")
        assert during["proxy"]
        assert during["attributes"] == (real.fileno(), real.encoding, real.isatty())
        assert sys.stdout is real


def test_capture_survives_reset_of_sys_stdout():
    """Code that resets sys.stdout to sys.__stdout__ must not break later
    captures."""
    speaker = _make_speaker("Kitchen")
    with patch("soco_cli.api.process_action", side_effect=_slow_action):
        run_command(speaker, "test", "token")
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        assert run_command(speaker, "test", "again") == (0, "again-done", "")


def test_nested_capture_restores_outer_capture():
    speaker = _make_speaker("Kitchen")

    def outer(speaker, action, args, use_local_speaker_list=False):
        print("before")
        if action == "outer":
            assert run_command(speaker, "inner") == (0, "inner", "")
        print("after")
        return True

    def action(speaker, action, args, use_local_speaker_list=False):
        if action == "inner":
            print("inner")
            return True
        return outer(speaker, action, args)

    with patch("soco_cli.api.process_action", side_effect=action):
        assert run_command(speaker, "outer") == (0, "\nbefore\nafter\n", "")


def _capture_across(reset):
    """Run a command on another thread that prints, waits while reset() runs
    on this thread, then prints the rest of its line. Return the command's
    result."""
    speaker = _make_speaker("Kitchen")
    started = threading.Event()
    resumed = threading.Event()
    result = []

    def action(speaker, action, args, use_local_speaker_list=False):
        print("before", end="")
        started.set()
        resumed.wait(5)
        print("-after")
        return True

    with patch("soco_cli.api.process_action", side_effect=action):
        thread = threading.Thread(
            target=lambda: result.append(run_command(speaker, "test"))
        )
        thread.start()
        assert started.wait(5)
        reset()
        resumed.set()
        thread.join()
    return result[0]


def test_signal_handler_does_not_end_capture_on_other_threads(capfd):
    """The signal handler ends only its own thread's capture. Its message
    still reaches the console."""

    def handle_sigint():
        # INTERACTIVE makes the handler print a message and return, not exit
        with patch("soco_cli.utils.INTERACTIVE", True):
            sig_handler(signal.SIGINT, None)

    assert _capture_across(handle_sigint) == (0, "before-after", "")
    assert "Please use 'exit'" in capfd.readouterr().out


def test_play_file_list_does_not_end_capture_on_other_threads():
    """play_file_list() ends only its own thread's capture."""
    speaker = _make_speaker("Kitchen")

    def play_with_options():
        play_file_list(speaker, [], "p")

    assert _capture_across(play_with_options) == (0, "before-after", "")


def test_play_file_list_progress_goes_to_console(tmp_path, capfd):
    """When run as a command, play_file_list() with options still prints its
    progress on the console, not into the command's result."""
    speaker = _make_speaker("Kitchen")
    track = tmp_path / "track.mp3"
    track.write_bytes(b"")

    def action(speaker, action, args, use_local_speaker_list=False):
        print("before")
        play_file_list(speaker, [str(track)], "p")
        return True

    with patch("soco_cli.api.process_action", side_effect=action):
        with patch("soco_cli.play_local_file_lists.play_local_file"):
            assert run_command(speaker, "test") == (0, "before", "")
    sys.__stdout__.flush()  # In case the output went to sys.__stdout__
    assert "Playing 1 of 1: {}".format(track) in capfd.readouterr().out


def test_log_handler_created_between_commands_keeps_its_stream():
    """A logging handler created between commands writes to the real stderr.
    Records logged during a later command go to it, not into the command's
    error_msg."""
    speaker = _make_speaker("Kitchen")
    logger = logging.getLogger("soco_cli.test_api")

    def warn(speaker, action, args, use_local_speaker_list=False):
        logger.warning("diagnostic")
        print("ok")
        return True

    sink = StringIO()
    sys.stderr = sink
    with patch("soco_cli.api.process_action", side_effect=warn):
        run_command(speaker, "first")
        handler = logging.StreamHandler()  # Binds to the current sys.stderr
        logger.addHandler(handler)
        try:
            assert run_command(speaker, "second") == (0, "ok", "")
        finally:
            logger.removeHandler(handler)
    assert sink.getvalue() == "diagnostic\n"


# Run in a fresh interpreter, because pytest attaches its own handlers to the
# root logger, and then logging never creates a default handler
_DEFAULT_LOG_HANDLER_SCRIPT = """
import logging
from unittest.mock import MagicMock, patch
from soco import SoCo
from soco_cli.api import run_command

speaker = MagicMock(spec=SoCo)
speaker.player_name = "Kitchen"

def action(speaker, action, args, use_local_speaker_list=False):
    print("ok")
    if action == "warn":
        logging.warning("diagnostic")
    return True

with patch("soco_cli.api.process_action", side_effect=action):
    run_command(speaker, "first")
    print(repr(run_command(speaker, "warn")))
"""


def test_default_log_handler_is_not_bound_to_capture():
    """If logging is not configured, the first command creates the root log
    handler. It must write to the real stderr, so that records logged during
    later commands don't end up in their error_msg."""
    completed = subprocess.run(
        [sys.executable, "-c", _DEFAULT_LOG_HANDLER_SCRIPT],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == repr((0, "ok", ""))
    assert "WARNING:root:diagnostic" in completed.stderr
