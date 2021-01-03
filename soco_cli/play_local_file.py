import functools
import logging
import urllib.parse
from http.server import ThreadingHTTPServer
from ipaddress import IPv4Address, IPv4Network
from os import path
from queue import Empty
from threading import Thread

import ifaddr
from RangeHTTPServer import RangeRequestHandler

from .utils import error_and_exit, set_speaker_playing_local_file

# The port range to use
PORT_START = 54000
PORT_END = 54099

SUPPORTED_TYPES = ["MP3", "M4A", "MP4", "FLAC", "OGG", "WMA", "WAV", "AAC"]


class MyHTTPHandler(RangeRequestHandler):
    def __init__(self, *args, filename=None, speaker_ip=None, **kwargs):
        self.filename = filename
        self.speaker_ip = speaker_ip
        super().__init__(*args, **kwargs)

    def do_GET(self):
        logging.info("Get request received by HTTP server")

        # Only serve the specific file requested on the command line,
        # and only to the specific Sonos speaker IP address
        error = False
        if self.path.replace("/", "") != self.filename:
            logging.info("Access to file '{}' forbidden".format(self.path))
            error = True
        if self.client_address[0] != self.speaker_ip:
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
            # It's normal to hit some exceptions with Sonos.
            logging.info("Exception ignored: {}".format(e))
            pass

    def log_message(self, format, *args):
        # Suppress HTTP logging
        return


def http_server(server_ip, directory, filename, speaker_ip):
    # Set the directory from which to serve files, in the handler
    # Set the specific filename and client IP that are authorised
    handler = functools.partial(
        MyHTTPHandler, filename=filename, speaker_ip=speaker_ip, directory=directory
    )

    # For possible future use: set up MIME types
    # MyHTTPHandler.extensions_map[".m4a"] = "audio/x-m4a"
    # MyHTTPHandler.extensions_map[".aac"] = "audio/aac"

    # Find an available port by trying ports in sequence
    for port in range(PORT_START, PORT_END + 1):
        try:
            httpd = ThreadingHTTPServer((server_ip, port), handler)
            logging.info("Using {}:{} for web server".format(server_ip, port))
            httpd_thread = Thread(target=httpd.serve_forever, daemon=True)
            httpd_thread.start()
            logging.info("Web server started")
            return httpd
        except OSError:
            # Assume this means that the port is in use
            continue
    else:
        return None


def get_server_ip(speaker):
    # Get a suitable IP address to use as a server address for Sonos
    # on this host
    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for ip in adapter.ips:
            if ip.is_IPv4:
                network = IPv4Network(
                    ip.ip + "/" + str(ip.network_prefix), strict=False
                )
                if IPv4Address(speaker.ip_address) in network:
                    return ip.ip
    else:
        return None


def wait_until_stopped(speaker):
    sub = speaker.avTransport.subscribe(auto_renew=True)
    # Includes a hack for AAC files, which would be played in a repeat loop.
    # The speaker never goes into a 'STOPPED' state, so we have
    # to detect the second shift into a 'TRANSITIONING' state,
    # which occurs at the end of first playback.
    transitioning_count = 0
    while True:
        try:
            event = sub.events.get(timeout=1.0)
            # Special case for AAC files
            if event.variables["current_track_uri"].startswith("aac:"):
                if event.variables["transport_state"] == "TRANSITIONING":
                    if transitioning_count == 1:
                        sub.unsubscribe()
                        speaker.stop()
                        return True
                    else:
                        transitioning_count = 1
            # General case for other file types
            if event.variables["transport_state"] not in ["PLAYING", "TRANSITIONING"]:
                logging.info(
                    "Speaker '{}' in state '{}'".format(
                        speaker.player_name, event.variables["transport_state"]
                    )
                )
                sub.unsubscribe()
                return True
        except Empty:
            pass


def is_supported_type(filename):
    file_upper = filename.upper()
    for type in SUPPORTED_TYPES:
        if file_upper.endswith("." + type):
            # Supported file type
            return True
    else:
        return False


def play_local_file(speaker, pathname):
    # speaker is a SoCo instance
    # pathname is the local file to be played

    if not path.exists(pathname):
        error_and_exit("File '{}' not found".format(pathname))
        return False

    directory, filename = path.split(pathname)

    if not is_supported_type(filename):
        error_and_exit(
            "Unsupported file type; must be one of: {}".format(SUPPORTED_TYPES)
        )
        return False

    # Make filename compatible with URL naming
    url_filename = urllib.parse.quote(filename)

    server_ip = get_server_ip(speaker)
    if not server_ip:
        error_and_exit("Can't determine an IP address for web server")
        return False
    logging.info("Using server IP address: {}".format(server_ip))

    # Start the webserver (runs in a daemon thread)
    httpd = http_server(server_ip, directory, url_filename, speaker.ip_address)
    if not httpd:
        error_and_exit("Cannot create HTTP server")
        return False

    # This ensures that other running invocations of 'play_file'
    # receive their stop events, and terminate.
    logging.info("Stopping speaker '{}'".format(speaker.player_name))
    speaker.stop()

    # Assemble the URI
    uri = "http://" + server_ip + ":" + str(httpd.server_port) + "/" + url_filename
    logging.info("Playing file '{}' from directory '{}'".format(filename, directory))
    logging.info("Playback URI: {}".format(uri))

    # Send the URI to the speaker for playback
    # A special hack is required for AAC files, which have to be treated like radio.
    if filename.lower().endswith(".aac"):
        speaker.play_uri(uri, force_radio=True)
    else:
        speaker.play_uri(uri)

    logging.info("Setting flag to stop playback on CTRL-C")
    set_speaker_playing_local_file(speaker)

    logging.info("Waiting for playback to stop")
    wait_until_stopped(speaker)

    logging.info("Playback stopped ... terminating web server")
    httpd.shutdown()

    logging.info("Web server thread terminated")
    set_speaker_playing_local_file(None)

    return True
