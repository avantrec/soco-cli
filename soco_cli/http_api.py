"""Implements an HTTP API server for SoCo-CLI commands."""

from sys import version_info

if version_info.major == 3 and version_info.minor < 7:
    print("HTTP API Server requires Python 3.7 or above")
    exit(1)

import argparse
import pprint
import shlex
from os import kill
from os.path import abspath
from signal import SIGINT
from subprocess import STDOUT, CalledProcessError, Popen, check_output
from sys import exit
from typing import Dict, Optional, Tuple

import uvicorn  # type: ignore
from fastapi import FastAPI

from soco_cli.__init__ import __version__ as version  # type: ignore
from soco_cli.api import get_all_speaker_names
from soco_cli.api import get_soco_object as get_speaker
from soco_cli.api import rescan_speakers
from soco_cli.api import run_command as sc_run
from soco_cli.speakers import Speakers
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
ASYNC_PREFIX = "async_"

# Gets used with the local speaker list only
SPEAKER_LIST = Speakers(network_timeout=1.0)


class ActiveAsyncOps:
    """
    Keep track of running async processes, and allow
    processes to be stopped.
    """

    def __init__(self):
        self.active_async_ops = {}

    def add_async_pid(self, speaker_ip: str, pid: int):
        self.active_async_ops.update({speaker_ip: pid})

    def get_async_pid(self, speaker_ip) -> Optional[int]:
        return self.active_async_ops.get(speaker_ip)

    def remove_async_pid(self, speaker_ip) -> Optional[int]:
        pid = self.active_async_ops.get(speaker_ip)
        if pid is not None:
            self.active_async_ops.pop(speaker_ip)
        return pid

    def stop_async_process(self, speaker_ip: str):
        pid = self.get_async_pid(speaker_ip)
        if pid is None:
            return
        try:
            kill(pid, SIGINT)
        except:
            pass
        self.remove_async_pid(speaker_ip)


ASYNC_OPS = ActiveAsyncOps()


sc_app = FastAPI(
    title="SoCo-CLI HTTP API Server",
    description="**Use this interface to review and test SoCo-CLI's HTTP API**",
    version=version,
    contact={"name": "Avantrec Ltd", "url": "https://github.com/avantrec/soco-cli"},
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)


def command_core(
    speaker: str, action: str, *args: str, use_local: bool = False
) -> Dict:
    device, error_msg = get_speaker(speaker, use_local_speaker_list=use_local)
    if device:
        speaker = device.player_name
        if not action.startswith(ASYNC_PREFIX):
            exit_code, result, error_msg = sc_run(
                device, action, *args, use_local_speaker_list=use_local
            )
        else:
            action = action.replace(ASYNC_PREFIX, "")
            try:
                ASYNC_OPS.stop_async_process(device.ip_address)
                proc = Popen(["sonos", device.ip_address, action, *args])
                ASYNC_OPS.add_async_pid(device.ip_address, proc.pid)
                exit_code = 0
                error_msg = ""
                result = ""
            except Exception as e:
                exit_code = 1
                error_msg = str(e)
                result = ""
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


@sc_app.get("/speakers")
def speakers() -> Dict:
    if USE_LOCAL:
        speakers = SPEAKER_LIST.get_all_speaker_names()
    else:
        speakers = get_all_speaker_names()
    print(PREFIX + "Speakers: {}".format(speakers))
    return {"speakers": speakers}


@sc_app.get("/rediscover")
def rediscover() -> Dict:
    if USE_LOCAL:
        SPEAKER_LIST.discover()
        SPEAKER_LIST.save()
        print(PREFIX + "Saved new local speaker list")
        speakers = SPEAKER_LIST.get_all_speaker_names()
    else:
        rescan_speakers(timeout=2.0)
        speakers = get_all_speaker_names()
    print(PREFIX + "Speakers (re)discovered: {}".format(speakers))
    return {"speakers_discovered": speakers}


# Deprecated
@sc_app.get("/macros", include_in_schema=False)
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


@sc_app.get("/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}/{arg_5}/{arg_6}")
def run_macro_6(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
) -> Dict:
    command, result = _process_macro(
        macro_name, arg_1, arg_2, arg_3, arg_4, arg_5, arg_6
    )
    return {"command": command, "result": result}


@sc_app.get(
    "/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}/{arg_5}/{arg_6}/{arg_7}"
)
def run_macro_7(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
    arg_7: str,
) -> Dict:
    command, result = _process_macro(
        macro_name, arg_1, arg_2, arg_3, arg_4, arg_5, arg_6, arg_7
    )
    return {"command": command, "result": result}


@sc_app.get(
    "/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}/{arg_5}/{arg_6}/{arg_7}/{arg_8}"
)
def run_macro_8(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
    arg_7: str,
    arg_8: str,
) -> Dict:
    command, result = _process_macro(
        macro_name, arg_1, arg_2, arg_3, arg_4, arg_5, arg_6, arg_7, arg_8
    )
    return {"command": command, "result": result}


@sc_app.get(
    "/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}/{arg_5}/{arg_6}/{arg_7}/{arg_8}/{arg_9}"
)
def run_macro_9(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
    arg_7: str,
    arg_8: str,
    arg_9: str,
) -> Dict:
    command, result = _process_macro(
        macro_name, arg_1, arg_2, arg_3, arg_4, arg_5, arg_6, arg_7, arg_8, arg_9
    )
    return {"command": command, "result": result}


@sc_app.get(
    "/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}"
    "/{arg_5}/{arg_6}/{arg_7}/{arg_8}/{arg_9}/{arg_10}"
)
def run_macro_10(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
    arg_7: str,
    arg_8: str,
    arg_9: str,
    arg_10: str,
) -> Dict:
    command, result = _process_macro(
        macro_name,
        arg_1,
        arg_2,
        arg_3,
        arg_4,
        arg_5,
        arg_6,
        arg_7,
        arg_8,
        arg_9,
        arg_10,
    )
    return {"command": command, "result": result}


@sc_app.get(
    "/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}"
    "/{arg_5}/{arg_6}/{arg_7}/{arg_8}/{arg_9}/{arg_10}/{arg_11}"
)
def run_macro_11(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
    arg_7: str,
    arg_8: str,
    arg_9: str,
    arg_10: str,
    arg_11: str,
) -> Dict:
    command, result = _process_macro(
        macro_name,
        arg_1,
        arg_2,
        arg_3,
        arg_4,
        arg_5,
        arg_6,
        arg_7,
        arg_8,
        arg_9,
        arg_10,
        arg_11,
    )
    return {"command": command, "result": result}


@sc_app.get(
    "/macro/{macro_name}/{arg_1}/{arg_2}/{arg_3}/{arg_4}"
    "/{arg_5}/{arg_6}/{arg_7}/{arg_8}/{arg_9}/{arg_10}/{arg_11}/{arg_12}"
)
def run_macro_12(
    macro_name: str,
    arg_1: str,
    arg_2: str,
    arg_3: str,
    arg_4: str,
    arg_5: str,
    arg_6: str,
    arg_7: str,
    arg_8: str,
    arg_9: str,
    arg_10: str,
    arg_11: str,
    arg_12: str,
) -> Dict:
    command, result = _process_macro(
        macro_name,
        arg_1,
        arg_2,
        arg_3,
        arg_4,
        arg_5,
        arg_6,
        arg_7,
        arg_8,
        arg_9,
        arg_10,
        arg_11,
        arg_12,
    )
    return {"command": command, "result": result}


@sc_app.get("/{speaker}/{action}")
def action_0(speaker: str, action: str) -> Dict:
    return command_core(speaker, action, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1}")
def action_1(speaker: str, action: str, arg_1: str) -> Dict:
    return command_core(speaker, action, arg_1, use_local=USE_LOCAL)


@sc_app.get("/{speaker}/{action}/{arg_1:path}")
def action_1_path(speaker: str, action: str, arg_1: str) -> Dict:
    """
    Handle the case where 'arg_1' is a path.
    """

    # Handle special case of _end_on_pause_ being appended to a file path
    # instead of being treated as a separate argument.
    arg_2 = "_end_on_pause_"
    if arg_1.endswith(arg_2):
        arg_1 = arg_1.replace("/" + arg_2, "")
        return command_core(speaker, action, arg_1, arg_2, use_local=USE_LOCAL)

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
    parser.add_argument(
        "--use-local-speaker-list",
        "-l",
        action="store_true",
        default=False,
        help="Use the local speaker list instead of SoCo discovery",
    )
    parser.add_argument(
        "--subnets",
        type=str,
        help="Only with '-l': specify the networks or IP addresses to search",
    )

    args = parser.parse_args()

    if args.version:
        print_version()
        exit(0)

    global PORT
    if args.port is not None:
        PORT = args.port

    global USE_LOCAL
    USE_LOCAL = args.use_local_speaker_list
    if USE_LOCAL and args.subnets is not None:
        subnets = args.subnets.split(",")
        SPEAKER_LIST.set_subnets_no_check(subnets)
        print(PREFIX + "/rediscover will use subnets = {}".format(subnets))
    if not USE_LOCAL and args.subnets is not None:
        print(PREFIX + "Option '--subnets' ignored; only valid with local cache")

    global MACRO_FILE
    MACRO_FILE = abspath(args.macros)


def main() -> None:
    args_processor()
    print(PREFIX + "Starting " + INFO)

    # Load local macros
    global MACROS
    _load_macros(MACROS, filename=MACRO_FILE)

    try:
        print(PREFIX + "Loading speakers ... ", end="", flush=True)
        if USE_LOCAL:
            SPEAKER_LIST.load()
            print(SPEAKER_LIST.get_all_speaker_names())
        else:
            try:
                # This forces speaker discovery
                # For some reason, using 'get_all_speakers()' generates Uvicorn errors
                get_speaker("", USE_LOCAL)
                print(get_all_speaker_names())
            except:
                print(PREFIX + "Discovery failed: try '/rediscover'")

        # Start the server
        try:
            uvicorn.run(sc_app, host="0.0.0.0", use_colors=False, port=PORT)
        except KeyboardInterrupt:
            pass
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

    # Finalise the command line
    if USE_LOCAL:
        sonos_command_line = "sonos -l " + sonos_command_line
    else:
        # Substitute speaker names for IP addresses, for efficiency
        sonos_command_line = _substitute_speaker_ips(sonos_command_line)
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
    parameters_list = [
        "%1",
        "%2",
        "%3",
        "%4",
        "%5",
        "%6",
        "%7",
        "%8",
        "%9",
        "%10",
        "%11",
        "%12",
    ]
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
    # Create the 'generic' macro
    macros["__"] = "%1 %2 %3 %4 %5 %6 %7 %8 %9 %10 %11 %12"
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
