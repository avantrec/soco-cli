"""Implements an HTTP API server for SoCo-CLI commands."""

from sys import version_info

if version_info.major == 3 and version_info.minor < 6:
    print("HTTP API Server requires Python 3.6 or above")
    exit(1)

import argparse

import uvicorn
from fastapi import FastAPI

from soco_cli.__init__ import __version__ as version
from soco_cli.api import get_all_speaker_names
from soco_cli.api import get_soco_object as get_speaker
from soco_cli.api import rescan_speakers
from soco_cli.api import run_command as sc_run
from soco_cli.utils import version as print_version

sc_app = FastAPI()

# Globals
USE_LOCAL = False
PORT = 8000
INFO = "SoCo-CLI HTTP API Server v" + version
PREFIX = "SoCo-CLI: "


def command_core(speaker, action, *args, use_local=False):
    device, error_msg = get_speaker(speaker, use_local_speaker_list=use_local)
    if device:
        speaker = device.player_name
        exit_code, result, error_msg = sc_run(
            device, action, *args, use_local_speaker_list=use_local
        )
    else:
        exit_code = 1
        result = ""

    # Quote speaker names & arguments containing spaces, for neatness
    if " " in speaker:
        quoted_speaker = '"' + speaker + '"'
    else:
        quoted_speaker = speaker
    new_args = []
    for i in range(len(args)):
        if " " in args[i]:
            new_args.append('"' + args[i] + '"')
        else:
            new_args.append(args[i])

    # Print the equivalent 'sonos' command and exit code
    if len(new_args) != 0:
        arguments = " ".join(new_args).rstrip()
        print(
            PREFIX
            + "Command = 'sonos {} {} {}', ".format(quoted_speaker, action, arguments),
            end="",
        )
    else:
        print(
            PREFIX + "Command = 'sonos {} {}', ".format(quoted_speaker, action), end=""
        )
    if exit_code == 0:
        print("exit code = {}".format(exit_code))
    else:
        print("exit code = {} [{}]".format(exit_code, error_msg))

    return {
        "speaker": speaker,
        "action": action,
        "args": args,
        "exit_code": exit_code,
        "result": result,
        "error_msg": error_msg,
    }


@sc_app.get("/")
async def root():
    return {"info": INFO}


@sc_app.get("/rediscover")
async def rediscover():
    rescan_speakers(timeout=2.0)
    speakers = get_all_speaker_names()
    print(PREFIX + "Speakers (re)discovered: {}".format(speakers))
    return {"speakers_discovered": speakers}


@sc_app.get("/{speaker}/{action}")
async def action_0(speaker: str, action: str):
    return command_core(speaker, action, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}")
async def action_1(speaker: str, action: str, arg_1: str):
    return command_core(speaker, action, arg_1, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}/{arg_2}")
async def action_2(speaker: str, action: str, arg_1: str, arg_2: str):
    return command_core(speaker, action, arg_1, arg_2, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}/{arg_2}/{arg_3}")
async def action_3(speaker: str, action: str, arg_1: str, arg_2: str, arg_3: str):
    return command_core(speaker, action, arg_1, arg_2, arg_3, use_local=USE_LOCAL)


def args_processor():
    parser = argparse.ArgumentParser(
        prog="sonos-http-api-server",
        usage="%(prog)s",
        description=INFO,
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="The port on which to listen",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        default=False,
        help="Print the SoCo-CLI and SoCo versions, and exit",
    )

    args = parser.parse_args()

    if args.version:
        print_version()
        exit(0)

    global PORT
    if args.port is not None:
        PORT = args.port


def main():
    args_processor()
    print(PREFIX + "Starting " + INFO)

    try:
        # Pre-load speaker cache
        print(PREFIX + "Finding speakers ... ", end="", flush=True)
        try:
            # This forces speaker discovery
            # For some reason, using 'get_all_speakers()' provokes Uvicorn errors
            get_speaker("")
            print(get_all_speaker_names())
        except:
            print("discovery failed, will retry on first request")

        # Start the server
        uvicorn.run(sc_app, host="0.0.0.0", use_colors=False, port=PORT)
        print(PREFIX + INFO + " stopped")
        exit(0)

    except Exception as error:
        print("Error: {}".format(error))
        exit(1)


if __name__ == "__main__":
    main()
