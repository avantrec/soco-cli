"""Implements an HTTP API server for SoCo-CLI commands."""

from sys import version_info

if version_info.major == 3 and version_info.minor < 6:
    print("HTTP API Server requires Python 3.6 or above")
    exit(1)

import argparse
import shlex
from os.path import abspath
from subprocess import check_output
from typing import Dict

import uvicorn  # type: ignore
from fastapi import FastAPI

from soco_cli.__init__ import __version__ as version  # type: ignore
from soco_cli.api import get_all_speaker_names
from soco_cli.api import get_soco_object as get_speaker
from soco_cli.api import rescan_speakers
from soco_cli.api import run_command as sc_run
from soco_cli.utils import version as print_version

# Globals
USE_LOCAL = False
PORT = 8000
INFO = "SoCo-CLI HTTP API Server v" + version
PREFIX = "SoCo-CLI: "
MACROS: Dict[str, str] = {}
MACRO_FILE = ""


sc_app = FastAPI()


def command_core(
    speaker: str, action: str, *args: str, use_local: bool = False
) -> Dict:
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
def root() -> Dict:
    return {"info": INFO}


@sc_app.get("/rediscover")
def rediscover() -> Dict:
    rescan_speakers(timeout=2.0)
    speakers = get_all_speaker_names()
    print(PREFIX + "Speakers (re)discovered: {}".format(speakers))
    return {"speakers_discovered": speakers}


@sc_app.get("/speakers")
def speakers() -> Dict:
    speakers = get_all_speaker_names()
    print(PREFIX + "Speakers: {}".format(speakers))
    return {"speakers": speakers}


@sc_app.get("/macros")
def macros() -> Dict:
    return MACROS


@sc_app.get("/macro/{macro_name}")
def run_commands(macro_name: str) -> Dict:
    result = _process_macro(macro_name)
    return {"result": result}


@sc_app.get("/{speaker}/{action}")
def action_0(speaker: str, action: str) -> Dict:
    return command_core(speaker, action, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}")
def action_1(speaker: str, action: str, arg_1: str) -> Dict:
    return command_core(speaker, action, arg_1, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}/{arg_2}")
def action_2(speaker: str, action: str, arg_1: str, arg_2: str) -> Dict:
    return command_core(speaker, action, arg_1, arg_2, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}/{arg_2}/{arg_3}")
def action_3(speaker: str, action: str, arg_1: str, arg_2: str, arg_3: str) -> Dict:
    return command_core(speaker, action, arg_1, arg_2, arg_3, use_local=USE_LOCAL)


def args_processor() -> None:
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

    parser.add_argument(
        "--macros",
        "-m",
        type=str,
        default="macros.txt",
        help="The file containing the local macros",
    )

    args = parser.parse_args()

    if args.version:
        print_version()
        exit(0)

    global PORT
    if args.port is not None:
        PORT = args.port

    global MACRO_FILE
    MACRO_FILE = abspath(args.macros)


def main() -> None:
    args_processor()
    print(PREFIX + "Starting " + INFO)

    # Load local macros
    global MACROS
    _load_macros(MACROS, filename=MACRO_FILE)

    try:
        # Pre-load speaker cache
        print(PREFIX + "Finding speakers ... ", end="", flush=True)
        try:
            # This forces speaker discovery
            # For some reason, using 'get_all_speakers()' generates Uvicorn errors
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


def _process_macro(macro_name: str) -> str:
    # Look up the macro
    try:
        macro = _lookup_macro(macro_name)
    except KeyError:
        print(PREFIX + "macro '{}' not found".format(macro_name))
        return "Error: macro '{}' not found".format(macro_name)

    # Substitute speaker names for IP addresses, for efficiency
    sonos_command_line = "sonos " + _substitute_speaker_ips(macro)
    print(PREFIX + "Executing: " + sonos_command_line)

    # Execute the command
    try:
        output = check_output(sonos_command_line, shell=True)
        return "Command line output: " + output.decode("utf-8")
    except:
        return "Error running command line: " + sonos_command_line


def _lookup_macro(macro_name: str) -> str:
    global MACROS
    return MACROS[macro_name]


def _substitute_speaker_ips(macro: str, use_local: bool = False) -> str:
    """
    Substitute speaker names for IP addresses, for efficiency.
    Speaker names must be exact.
    """
    terms = shlex.split(macro)
    new_macro_list = []
    for term in terms:
        device, error_msg = get_speaker(term, use_local_speaker_list=use_local)
        if device is not None and device.player_name == term:
            new_macro_list.append(device.ip_address)
        else:
            new_macro_list.append(term)
    new_macro = (" ").join(new_macro_list)
    return new_macro


def _load_macros(macros: dict, filename: str) -> bool:
    print(PREFIX + "Attempting to load macros from '{}'".format(filename))
    try:
        with open(filename, "r") as f:
            line = f.readline()
            while line != "":
                if not line.startswith("#") and line != "\n":
                    if line.count("=") != 1:
                        print(PREFIX + "Malformed macro '{}'... ignored".format(line))
                        print(line, end="")
                    else:
                        macro = line.split("=")
                        macros[macro[0].strip()] = macro[1].strip()
                line = f.readline()
        print(PREFIX + "Loaded macros: {}".format(macros))
        return True
    except:
        print(PREFIX + "Macro file not found")
        return False


if __name__ == "__main__":
    main()
