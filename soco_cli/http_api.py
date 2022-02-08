"""Implements an HTTP API server for SoCo-CLI commands."""

from sys import version_info

if version_info.major == 3 and version_info.minor < 6:
    print("HTTP API Server requires Python 3.6 or above")
    exit(1)

import argparse
import pprint
import shlex
from os.path import abspath
from subprocess import STDOUT, CalledProcessError, check_output
from typing import Dict, Tuple

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
PREFIX_MACRO = PREFIX + "Macro: "
MACROS: Dict[str, str] = {}
MACRO_FILE = ""
PP = pprint.PrettyPrinter(indent=len(PREFIX_MACRO))

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

    # Quote speaker names & arguments containing spaces
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


@sc_app.get("/macros/list")
def macros_list() -> Dict:
    return MACROS


@sc_app.get("/macros/reload")
def macros_reload() -> Dict:
    global MACROS
    _load_macros(MACROS, filename=MACRO_FILE)
    return MACROS


@sc_app.get("/macro/{macro_name}")
def run_macro(macro_name: str) -> Dict:
    command, result = _process_macro(macro_name)
    return {"command": command, "result": result}


@sc_app.get("/macro/{macro_name}/{arg_1}")
def run_macro_1(macro_name: str, arg_1: str) -> Dict:
    command, result = _process_macro(macro_name, arg_1)
    return {"command": command, "result": result}


@sc_app.get("/macro/{macro_name}/{arg_1}/{arg_2}")
def run_macro_2(macro_name: str, arg_1: str, arg_2: str) -> Dict:
    command, result = _process_macro(macro_name, arg_1, arg_2)
    return {"command": command, "result": result}


@sc_app.get("/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}")
def run_macro_3(macro_name: str, arg_1: str, arg_2: str, arg_3: str) -> Dict:
    command, result = _process_macro(macro_name, arg_1, arg_2, arg_3)
    return {"command": command, "result": result}


@sc_app.get("/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}")
def run_macro_4(
    macro_name: str, arg_1: str, arg_2: str, arg_3: str, arg_4: str
) -> Dict:
    command, result = _process_macro(macro_name, arg_1, arg_2, arg_3, arg_4)
    return {"command": command, "result": result}


@sc_app.get("/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}/{arg_5}")
def run_macro_5(
    macro_name: str, arg_1: str, arg_2: str, arg_3: str, arg_4: str, arg_5: str
) -> Dict:
    command, result = _process_macro(macro_name, arg_1, arg_2, arg_3, arg_4, arg_5)
    return {"command": command, "result": result}


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
        print(PREFIX + "Discovering speakers ... ", end="", flush=True)
        try:
            # This forces speaker discovery
            # For some reason, using 'get_all_speakers()' generates Uvicorn errors
            get_speaker("")
            print(get_all_speaker_names())
        except:
            print(PREFIX + "Discovery failed: try '/rediscover'")

        # Start the server
        uvicorn.run(sc_app, host="0.0.0.0", use_colors=False, port=PORT)
        print(PREFIX + INFO + " stopped")
        exit(0)

    except Exception as error:
        print("Error: {}".format(error))
        exit(1)


def _process_macro(macro_name: str, *args) -> Tuple[str, str]:
    # Look up the macro
    try:
        macro = _lookup_macro(macro_name)
        print(PREFIX_MACRO + "Processing macro '{}' = '{}'".format(macro_name, macro))
    except KeyError:
        print(PREFIX_MACRO + "macro '{}' not found".format(macro_name))
        return "", "Error: macro '{}' not found".format(macro_name)

    # Substitute variable arguments
    sonos_command_line = _substitute_variables(macro, args)

    # Substitute speaker names for IP addresses, for efficiency
    sonos_command_line = _substitute_speaker_ips(sonos_command_line)

    # Finalise the command line
    sonos_command_line = "sonos " + sonos_command_line

    # Execute the command
    print(PREFIX_MACRO + "Executing: '" + sonos_command_line + "' in a subprocess")
    try:
        output = check_output(sonos_command_line, stderr=STDOUT, shell=True)
        print(PREFIX_MACRO + "Exit code = 0")
        return sonos_command_line, output.decode("utf-8").rstrip()
    except CalledProcessError as exc:
        error = exc.output.decode("utf-8").rstrip().replace("\n", "; ")
        print(PREFIX_MACRO + "Exit code = {} [{}]".format(exc.returncode, error))
        return sonos_command_line, error


def _lookup_macro(macro_name: str) -> str:
    global MACROS
    return MACROS[macro_name]


def _substitute_variables(macro: str, args: Tuple) -> str:
    """Substitute positional parameters with supplied variables."""
    parameters_list = ["%1", "%2", "%3", "%4", "%5"]
    supplied_parameters = set(parameters_list[: len(args)])
    parameters = set(parameters_list)
    used_parameters = []
    unsatisfied_parameters = set()
    variables_used = []

    elements = shlex.split(macro)
    sonos_command_line_terms = []
    for element in elements:
        if element in parameters:
            try:
                arg_sub = _quote_if_contains_space(args[int(element[1:]) - 1])
                if arg_sub == "_":
                    # If the supplied argument is an underscore, ignore it
                    raise IndexError
                sonos_command_line_terms.append(arg_sub)
                used_parameters.append(element)
                variables_used.append(arg_sub)
            except IndexError:
                # Omit unsatisfied arguments and continue
                unsatisfied_parameters.add(element)
        else:
            sonos_command_line_terms.append(_quote_if_contains_space(element))

    used_parameters_set = set(used_parameters)

    # Print out parameter usage
    if len(args) > 0:
        print(PREFIX_MACRO + "Parameter variables supplied: {}".format(list(args)))
    if len(used_parameters) > 0:
        print(
            PREFIX_MACRO
            + "Parameter variables used: {} -> {}".format(
                used_parameters, variables_used
            )
        )
    if len(unsatisfied_parameters) > 0:
        print(
            PREFIX_MACRO
            + "Parameter variables ignored or not supplied for: {}".format(
                sorted(list(unsatisfied_parameters))
            )
        )
    if len(supplied_parameters - used_parameters_set) > 0:
        unused_list = sorted(list(supplied_parameters - used_parameters_set))
        unused_variables = []
        for unused in unused_list:
            unused_variables.append(_quote_if_contains_space(args[int(unused[1:]) - 1]))
        print(
            PREFIX_MACRO
            + "Parameter variables supplied but ignored or not used: {} -> {}".format(
                sorted(list(supplied_parameters - used_parameters_set)),
                unused_variables,
            )
        )

    # Return the substituted command line
    return " ".join(sonos_command_line_terms)


def _substitute_speaker_ips(macro: str, use_local: bool = False) -> str:
    """
    Substitute speaker names for IP addresses, for efficiency.
    Speaker names must be exact.
    """
    elements = shlex.split(macro)
    new_macro_list = []
    for element in elements:
        device, error_msg = get_speaker(element, use_local_speaker_list=use_local)
        if device is not None and device.player_name == element:
            new_macro_list.append(device.ip_address)
            print(
                PREFIX_MACRO
                + "Substituting speaker name '{}' by IP address '{}'".format(
                    device.player_name, device.ip_address
                )
            )
        else:
            new_macro_list.append(_quote_if_contains_space(element))
    return " ".join(new_macro_list)


def _load_macros(macros: dict, filename: str) -> bool:
    print(PREFIX_MACRO + "Attempting to (re)load macros from '{}'".format(filename))
    try:
        with open(filename, "r") as f:
            line = f.readline()
            while line != "":
                if not line.startswith("#") and line != "\n":
                    if line.count("=") != 1:
                        print(
                            PREFIX_MACRO
                            + "Malformed macro '{}'... ignored".format(line)
                        )
                        print(line, end="")
                    else:
                        macro = line.split("=")
                        macros[macro[0].strip()] = macro[1].strip()
                line = f.readline()
        print(PREFIX_MACRO + "Loaded macros:")
        PP.pprint(macros)
        return True
    except:
        print(PREFIX_MACRO + "Macro file not found")
        return False


def _quote_if_contains_space(text: str) -> str:
    if " " in text:
        return '"' + text + '"'
    else:
        return text


if __name__ == "__main__":
    main()
