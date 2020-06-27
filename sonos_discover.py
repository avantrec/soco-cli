#!/usr/bin/env python3

# Find all Sonos speakers on your local network(s)

import ipaddress
import socket
import soco
import ifaddr
import threading
import argparse
import pprint
from collections import namedtuple

# Type for holding speaker details
SonosDevice = namedtuple(
    "Device", ["household_id", "ip_address", "speaker_name", "is_coordinator"]
)

# Cache of sonos discovery results
sonos_devices = []


def is_ipv4_address(ip_address):
    try:
        ipaddress.IPv4Network(ip_address)
        return True
    except ValueError:
        return False


def find_my_ipv4_networks():
    """Return a list of unique IPv4 networks to which this node is attached."""
    ipv4_net_list = []
    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for ip in adapter.ips:
            if is_ipv4_address(ip.ip):
                # Omit the loopback address
                if ip.ip != "127.0.0.1":
                    nw = ipaddress.ip_network(
                        ip.ip + "/" + str(ip.network_prefix), False
                    )
                    # Avoid duplicate subnets
                    if nw not in ipv4_net_list:
                        ipv4_net_list.append(nw)
    return ipv4_net_list


def probe_ip_and_port(ip, port, timeout):
    """Determine if a port is open"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    if s.connect_ex((ip, port)) == 0:
        return True
    else:
        return False


def get_sonos_device_data(ip_addr, soco_timeout):
    """Interrogate a Sonos device"""
    try:
        speaker = soco.SoCo(str(ip_addr))
        info = speaker.get_speaker_info(refresh=True, timeout=soco_timeout)
        # Return a four-namedtuple:
        #   (Household ID, IP, Zone Name, Is Coordinator?)
        return SonosDevice(
            speaker.household_id,
            str(ip_addr),
            info["zone_name"],
            speaker.is_coordinator,
        )
    except Exception as e:
        # Probably not a Sonos device
        return None


def list_sonos_devices_worker(ip_list, socket_timeout, soco_timeout, sonos_devices):
    """Worker thread to pull IP addresses off a list, test if port 1400 is open,
    then pull down the Sonos device data.
    """
    while len(ip_list) > 0:
        ip_addr = ip_list.pop(0)
        if probe_ip_and_port(str(ip_addr), 1400, socket_timeout):
            device = get_sonos_device_data(ip_addr, soco_timeout)
            if device:
                sonos_devices.append(device)


def list_sonos_devices(threads=256, socket_timeout=2, soco_timeout=2, refresh=False):
    """Returns a list of Sonos devices on the local network(s). """
    global sonos_devices  # Cache for results
    if len(sonos_devices) != 0 and refresh is False:
        # Use the cache
        return sonos_devices
    # Probe the network
    ip_list = []
    # Set up the list of IPs to search
    for network in find_my_ipv4_networks():
        for ip_addr in network:
            ip_list.append(ip_addr)
    # Start threads to check IPs for Sonos devices
    thread_list = []
    sonos_devices = []
    # Disable SoCo caching to prevent problems caused by multiple households
    soco.core.zone_group_state_shared_cache.enabled = False
    # Create parallel threads to scan the IP range
    if threads > len(ip_list):
        threads = len(ip_list)
    for _ in range(threads):
        thread = threading.Thread(
            target=list_sonos_devices_worker,
            args=(ip_list, socket_timeout, (soco_timeout, soco_timeout), sonos_devices),
        )
        thread_list.append(thread)
        thread.start()
    # Wait for all threads to finish before returning
    for thread in thread_list:
        thread.join()
    return sonos_devices


def discover_named_speaker_ip(speaker_name, household=None):
    """Find the IP address of a coordinator speaker. Optionally specify a household ID"""
    devices = list_sonos_devices()
    for device in devices:
        # Only return the speaker IP if the speaker is a Coordinator
        if device.speaker_name == speaker_name and device.is_coordinator is True:
            if household is None or device.household_id == household:
                return device.ip_address
    return None


def discover_any_speaker_ip(household=None):
    """Return the IP address of any coordinator speaker. Optionally specify a household ID"""
    devices = list_sonos_devices()
    for device in devices:
        if device.is_coordinator and (
            device.household_id == household or household is None
        ):
            return device.ip_address
    return None


def discover_households():
    """Return a list of household IDs found."""
    devices = list_sonos_devices()
    households = []
    for device in devices:
        if device.household_id not in households:
            households.append(device.household_id)
    return households


if __name__ == "__main__":
    # Create the argument parser
    parser = argparse.ArgumentParser(
        prog="sonos-discover",
        usage="%(prog)s",
        description="Discover all Sonos speakers on the local network(s).",
    )
    parser.add_argument(
        "--threads",
        "-t",
        required=False,
        type=int,
        default=256,
        help="Number of threads to use when probing the network (default = 256)",
    )
    parser.add_argument(
        "--network_timeout",
        "-n",
        required=False,
        type=float,
        default=3.0,
        help="Network timeouts (float, seconds) to use when probing the network (default = 3.0s)",
    )
    # Parse the command line
    args = parser.parse_args()
    # Parameter validation
    if not 1 <= args.threads <= 1024:
        print(
            "Error: value of 'threads' parameter should be an integer between 1 and 1024"
        )
        exit(1)
    if not 0 <= args.network_timeout <= 60:
        print(
            "Error: value of 'network_timeout' parameter should be a float between 0 and 60"
        )
        exit(1)

    devices = list_sonos_devices(
        threads=args.threads,
        socket_timeout=args.network_timeout,
        soco_timeout=args.network_timeout,
    )

    households = {}
    for device in devices:
        if device[0] not in households:
            households[device[0]] = []
        households[device[0]].append((device[2], device[1], device[3]))

    pp = pprint.PrettyPrinter()
    pp.pprint(households)