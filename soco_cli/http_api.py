"""Implements an HTTP API for SoCo-CLI commands."""

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
from soco_cli.api import rediscover_speakers, rescan_speakers
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

    if exit_code == 0:
        print(PREFIX + "Exit code = {}".format(exit_code))
    else:
        print(PREFIX + "Exit code = {} [{}]".format(exit_code, error_msg))

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
    rescan_speakers(timeout=5.0)
    return {"Speakers discovered": get_all_speaker_names()}


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
        prog="sonos-http-api",
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
    parser.add_argument(
        "--use-local-speaker-list",
        "-l",
        action="store_true",
        default=False,
        help="Use the local speaker list instead of SoCo discovery",
    )

    args = parser.parse_args()

    if args.version:
        print_version()
        exit(0)

    global PORT
    if args.port is not None:
        PORT = args.port

    global USE_LOCAL
    if args.use_local_speaker_list is not None:
        USE_LOCAL = args.use_local_speaker_list


def main():
    args_processor()
    try:
        print("Starting " + INFO)
        uvicorn.run(sc_app, host="0.0.0.0", use_colors=False, port=PORT)
        print(INFO + " stopped")
        exit(0)
    except Exception as error:
        print("Error: {}".format(error))
        exit(1)


if __name__ == "__main__":
    main()
