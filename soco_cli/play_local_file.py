import functools
import logging
import urllib.parse
from http.server import HTTPServer
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

SUPPORTED_TYPES = ["MP3", "M4A", "MP4", "FLAC", "OGG", "WAV"]


class MyHTTPHandler(RangeRequestHandler):
    filename = None
    speaker_ip = None

    def do_GET(self):
        logging.info("Get request received by HTTP server")

        # Only serve the specific file requested on the command line,
        # and only to the specific Sonos speaker IP address
        if (
            MyHTTPHandler.filename != self.path.replace("/", "")
            or self.client_address[0] != MyHTTPHandler.speaker_ip
        ):
            RangeRequestHandler.send_error(self, code=403, message="Access forbidden")
            logging.info(
                "Access to '{}' from '{}' forbidden".format(
                    self.path, self.client_address[0]
                )
            )
            return

        try:
            super().do_GET()
        except:
            # It's normal to hit exceptions with Sonos. Ignore.
            pass

    def log_message(self, format, *args):
        # Suppress HTTP logging
        return


def http_server(server_ip, directory, filename, speaker_ip):
    # Set the directory from which to serve files, in the handler
    handler = functools.partial(MyHTTPHandler, directory=directory)

    # Set up the only filename that will be served, and the only IP to which
    # it will be served
    MyHTTPHandler.filename = filename
    MyHTTPHandler.speaker_ip = speaker_ip

    # Set up MIME types
    # MyHTTPHandler.extensions_map[".m4a"] = "audio/x-m4a"
    # MyHTTPHandler.extensions_map[".aac"] = "audio/aac"

    # Find an available port by trying ports in sequence
    for port in range(PORT_START, PORT_END + 1):
        try:
            httpd = HTTPServer((server_ip, port), handler)
            logging.info("Using {}:{} for web server".format(server_ip, port))
            httpd_thread = Thread(target=httpd.serve_forever, daemon=True)
            httpd_thread.start()
            logging.info("Web server started")
            return httpd
        except OSError:
            # Assume this means that the port is in use
            continue

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
    return None


def wait_until_stopped(speaker):
    sub = speaker.avTransport.subscribe(auto_renew=True)
    while True:
        try:
            event = sub.events.get(timeout=1.0)
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

    # Assemble the URI and send to the speaker for playback
    uri = "http://" + server_ip + ":" + str(httpd.server_port) + "/" + url_filename
    logging.info("Playing file '{}' from directory '{}'".format(filename, directory))
    logging.info("Playback URI: {}".format(uri))
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
