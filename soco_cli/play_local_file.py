import functools
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from ipaddress import IPv4Address, IPv4Network
from os import path
from queue import Empty
from threading import Thread
import ifaddr
import urllib.parse
from .utils import error_and_exit, set_speaker_playing_local_file

# The port range to use
PORT_START = 54000
PORT_END = 54100


class MyHTTPHandler(SimpleHTTPRequestHandler):
    filename = None

    def do_GET(self):
        # Only serve the specific file requested on the command line
        logging.info("Get request received by HTTP server")
        if MyHTTPHandler.filename != self.path.replace("/", ""):
            SimpleHTTPRequestHandler.send_error(
                self, code=404, message="File not found"
            )
            logging.info("Attempt to access non-specified file")
            return
        try:
            super().do_GET()
        except:
            # It's normal to hit exceptions with Sonos. Ignore.
            pass

    def log_message(self, format, *args):
        # Suppress HTTP logging
        return


def http_server(server_ip, directory, filename):
    # Set the directory from which to serve files, in the handler
    handler = functools.partial(MyHTTPHandler, directory=directory)
    # Set up the only filename that will be served
    MyHTTPHandler.filename = filename

    # Try ports within the range, in sequence
    httpd = None
    for port in range(PORT_START, PORT_END + 1):
        try:
            httpd = HTTPServer((server_ip, port), handler)
            break
        except OSError:
            continue
    logging.info("Using {}:{} for web server".format(server_ip, port))
    httpd_thread = Thread(target=httpd.serve_forever, daemon=True)
    httpd_thread.start()
    logging.info("Web server started")
    return httpd


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


def play_local_file(speaker, pathname):
    # speaker is a SoCo instance
    # pathname is the local file to be played

    if not path.exists(pathname):
        error_and_exit("File '{}' not found".format(pathname))
        return False
    directory, filename = path.split(pathname)

    # Sanitise filename for URL
    filename = urllib.parse.quote(filename)

    server_ip = get_server_ip(speaker)
    if not server_ip:
        logging.info("No suitable server IP found")
        error_and_exit("Can't determine the server_ip IP address")
        return False
    logging.info("Using server IP address: {}".format(server_ip))

    # Start the webserver (runs in a daemon thread)
    httpd = http_server(server_ip, directory, filename)
    if not httpd:
        exit(1)

    uri = "http://" + server_ip + ":" + str(httpd.server_port) + "/" + filename
    logging.info("Playing file '{}' from directory '{}'".format(filename, directory))
    speaker.play_uri(uri)

    # Flag that playback is stopped in the event of a CTRL-C
    logging.info("Setting flag to stop playback on signal")
    set_speaker_playing_local_file(speaker)

    # Wait until the track has finished, then shut down the
    # web server
    logging.info("Waiting for playback to stop")
    wait_until_stopped(speaker)
    logging.info("Playback stopped")
    httpd.shutdown()
    logging.info("Web server thread terminated")
    set_speaker_playing_local_file(None)
    return True


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
