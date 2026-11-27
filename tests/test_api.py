"""Tests for the thread safety of api.run_command().

run_command() captures a command's output by redirecting the process-wide
sys.stdout and sys.stderr. The HTTP API server runs requests on a thread
pool, so concurrent calls must not lose or mix up each other's output.
No live Sonos network is required: the speaker and the action are mocked.
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from soco import SoCo  # type: ignore

import soco_cli.http_api as http_api
from soco_cli.api import run_command

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
    # The 'pause' starts 0.2 s into a 2 s 'wait_stop'. If commands were
    # serialized, it would wait about 1.8 s, well over the 1 s limit, which
    # leaves room for a slow CI runner.
    speaker = _make_speaker("Kitchen")

    def actions(speaker, action, args, use_local_speaker_list=False):
        if action == "wait_stop":
            time.sleep(2)
        print("ok")
        return True

    with patch("soco_cli.http_api.get_speaker", return_value=(speaker, "")):
        with patch("soco_cli.api.process_action", side_effect=actions):
            slow = threading.Thread(
                target=http_api.command_core, args=("Kitchen", "wait_stop")
            )
            slow.start()
            time.sleep(0.2)
            start = time.monotonic()
            result = http_api.command_core("Kitchen", "pause")
            elapsed = time.monotonic() - start
            slow.join()
    assert result["result"] == "ok"
    assert elapsed < 1


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


def test_stream_attributes_come_from_real_stream():
    """Code that checks isatty(), encoding or fileno() still sees the real
    stream outside a capture."""
    speaker = _make_speaker("Kitchen")
    with open(os.devnull, "w") as real:
        sys.stdout = real
        with patch("soco_cli.api.process_action", side_effect=_slow_action):
            run_command(speaker, "test", "token")
        assert sys.stdout is not real  # The proxy is in place
        assert sys.stdout.fileno() == real.fileno()
        assert sys.stdout.encoding == real.encoding
        assert sys.stdout.isatty() == real.isatty()


def test_capture_survives_reset_of_sys_stdout():
    """Code that resets sys.stdout to sys.__stdout__ (as the signal handler
    and play_file_list() do) must not break later captures."""
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
