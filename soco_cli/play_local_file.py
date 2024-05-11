"""Plays files from the local filesystem."""

import functools
import http.client
import logging
import socket
import sys
import time
import urllib.parse
from http.server import HTTPServer
from ipaddress import IPv4Address, IPv4Network
from os import chdir, path
from socketserver import ThreadingMixIn
from threading import Thread
from typing import List, Optional

import ifaddr  # type: ignore
from RangeHTTPServer import RangeRequestHandler  # type: ignore
from soco import SoCo  # type: ignore

from soco_cli.utils import (
    error_report,
    event_unsubscribe,
    forget_event_sub,
    remember_event_sub,
    set_speaker_playing_local_file,
)

# The HTTP server port range to use
PORT_START = 54000
PORT_END = 54099

SUPPORTED_TYPES = ["MP3", "M4A", "MP4", "FLAC", "OGG", "WMA", "WAV", "AIFF"]


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads.

    Use the MixIn approach instead of the core ThreadingHTTPServer
    class for backwards compatibility with Python 3.5+
    """


class MyHTTPHandler(RangeRequestHandler):
    # Handle the change to the SimpleHTTPRequestHandler __init__() in Python 3.7+
    if sys.version_info >= (3, 7):

        def __init__(self, *args, filename=None, speaker_ips=None, **kwargs):
            self.filename = filename
            self.speaker_ips = speaker_ips
            super().__init__(*args, **kwargs)

    else:

        def __init__(
            self, *args, filename=None, speaker_ips=None, directory="", **kwargs
        ):
            self.filename = filename
            self.speaker_ips = speaker_ips
            try:
                chdir(directory)
            except:
                pass
            super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        logging.info("Get request received by HTTP server")

        # Only serve the specific file requested on the command line,
        # and only to Sonos speakers in the Sonos system
        error = False
        if self.path.replace("/", "") != self.filename:
            logging.info("Access to file '{}' forbidden".format(self.path))
            error = True
        if self.client_address[0] not in self.speaker_ips:
            logging.info("Access from IP '{}' forbidden".format(self.client_address[0]))
            error = True
        if error:
            RangeRequestHandler.send_error(
                self, code=403, message="SoCo-CLI HTTP Server: Access forbidden"
            )
            return

        # Forward the GET request
        try:
            super().do_GET()
        except Exception as e:
            # It's normal to hit some exceptions with Sonos
            logging.info("Exception ignored: {}".format(e))

    def log_message(self, format, *args) -> None:
        # Suppress HTTP logging
        return


def http_server(
    server_ip: str, directory: str, filename: str, speaker_ips: List[str]
) -> Optional[ThreadedHTTPServer]:
    # Set the directory from which to serve files, in the handler
    # Set the specific filename and client IP that are authorised
    handler = functools.partial(
        MyHTTPHandler, filename=filename, speaker_ips=speaker_ips, directory=directory
    )

    # For possible future use: set up MIME types
    # MyHTTPHandler.extensions_map[".m4a"] = "audio/x-m4a"
    # MyHTTPHandler.extensions_map[".aac"] = "audio/aac"

    # Find an available port by trying ports in sequence
    for port in range(PORT_START, PORT_END + 1):
        try:
            httpd = ThreadedHTTPServer((server_ip, port), handler)
            logging.info("Using {}:{} for web server".format(server_ip, port))
            httpd_thread = Thread(target=httpd.serve_forever, daemon=True)
            httpd_thread.start()
            logging.info("Web server started")
            return httpd
        except OSError:
            # Assume this means that the port is in use
            logging.info(
                "Port {}:{} already in use ... trying next".format(server_ip, port)
            )
            continue
    return None


def get_server_ip(speaker: SoCo) -> Optional[str]:
    # Get the host IP address to use as a server IP for Sonos
    # on this host.

    adapters = ifaddr.get_adapters()

    # First, try to find a host IP address in the same network as the speaker
    for adapter in adapters:
        for ip in adapter.ips:
            if ip.is_IPv4 and ip.ip != "127.0.0.1":
                logging.info(
                    "Checking if IP address '{}' is in target speaker's network".format(
                        ip.ip
                    )
                )
                network = IPv4Network(
                    ip.ip + "/" + str(ip.network_prefix), strict=False
                )
                if IPv4Address(speaker.ip_address) in network:
                    return ip.ip

    # If that fails, try to find a host IP address that can reach the target speaker
    for adapter in adapters:
        for ip in adapter.ips:
            if ip.is_IPv4 and ip.ip != "127.0.0.1":
                # Find an available port
                for port in range(PORT_START, PORT_END + 1):
                    try:
                        logging.info("Checking if port {} is available".format(port))
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.bind((ip.ip, port))
                            available_port = port
                            logging.info("Port {} is available".format(port))
                            break
                    except socket.error:
                        continue
                else:
                    logging.info("No available ports for IP address '{}'".format(ip.ip))
                    continue
                try:
                    logging.info(
                        "Checking target speaker's reachability from IP address '{}'".format(
                            ip.ip
                        )
                    )
                    http_connection = http.client.HTTPConnection(
                        speaker.ip_address,
                        port=1400,
                        timeout=5.0,
                        source_address=(ip.ip, available_port),
                    )
                    http_connection.request("GET", "/status/info")
                    response = http_connection.getresponse()
                    http_connection.close()
                    if response.status == 200:
                        return ip.ip
                except:
                    continue

    return None


def wait_until_stopped(speaker: SoCo, uri: str, end_on_pause: bool):
    playing_states = ["PLAYING", "TRANSITIONING"]
    if not end_on_pause:
        playing_states.append("PAUSED_PLAYBACK")
    logging.info("Playing states = {}".format(playing_states))

    try:
        sub = speaker.avTransport.subscribe(auto_renew=True)
        remember_event_sub(sub)
    except Exception as e:
        error_report("Exception {}".format(e))
        return

    while True:
        try:
            event = sub.events.get(timeout=1.0)
            state = event.variables["transport_state"]
            logging.info("Event received: playback state = '{}'".format(state))

            if state not in playing_states:
                logging.info(
                    "Speaker '{}' in state '{}'".format(
                        speaker.player_name, event.variables["transport_state"]
                    )
                )
                break

            # Check that the expected URI is still playing
            try:
                current_uri = event.variables["current_track_meta_data"].get_uri()
            except:
                # Can only call get_uri() on certain datatypes
                current_uri = ""
            if current_uri != uri:
                logging.info("Playback URI changed: exit event wait loop")
                break

        except:
            pass

    event_unsubscribe(sub)
    forget_event_sub(sub)
    return


def is_supported_type(filename: str) -> bool:
    file_upper = filename.upper()
    for file_type in SUPPORTED_TYPES:
        if file_upper.endswith("." + file_type):
            return True
    return False


def play_local_file(speaker: SoCo, pathname: str, end_on_pause: bool = False) -> bool:
    if not path.exists(pathname):
        error_report("File '{}' not found".format(pathname))
        return False

    directory, filename = path.split(pathname)

    if not is_supported_type(filename):
        error_report(
            "Unsupported file type; must be one of: {}".format(SUPPORTED_TYPES)
        )
        return False

    # Make filename compatible with URL naming
    url_filename = urllib.parse.quote(filename)

    server_ip = get_server_ip(speaker)
    if not server_ip:
        error_report("Can't determine an IP address for web server")
        return False
    logging.info("Using server IP address: {}".format(server_ip))

    # Start the webserver (runs in a daemon thread)
    speaker_ips = []
    for zone in speaker.all_zones:
        speaker_ips.append(zone.ip_address)
    httpd = http_server(server_ip, directory, url_filename, speaker_ips)
    if not httpd:
        error_report("Cannot create HTTP server")
        return False

    # This ensures that other running invocations of 'play_file'
    # receive their stop events, and terminate.
    logging.info("Stopping speaker '{}'".format(speaker.player_name))
    speaker.stop()

    # Assemble the URI
    uri = "http://" + server_ip + ":" + str(httpd.server_port) + "/" + url_filename
    logging.info("Playing file '{}' from directory '{}'".format(filename, directory))
    logging.info("Playback URI: {}".format(uri))

    logging.info("Send URI to '{}' for playback".format(speaker.player_name))
    speaker.play_uri(uri)

    logging.info("Setting flag to stop playback on CTRL-C")
    set_speaker_playing_local_file(speaker)

    logging.info("Waiting 1s for playback to start")
    time.sleep(1.0)
    logging.info("Waiting for playback to stop")
    wait_until_stopped(speaker, uri, end_on_pause)
    logging.info("Playback stopped ... terminating web server")
    httpd.shutdown()
    logging.info("Web server terminated")

    set_speaker_playing_local_file(None)

    return True
