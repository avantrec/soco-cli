#!/usr/bin/env python3

# Find all Sonos speakers on your local network(s)

import ipaddress
import socket
import soco
import ifaddr
import threading
import argparse
import pprint


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
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    if s.connect_ex((ip, port)) == 0:
        return True
    else:
        return False


def get_sonos_device_data(ip_addr, soco_timeout):
    try:
        speaker = soco.SoCo(str(ip_addr))
        info = speaker.get_speaker_info(refresh=True, timeout=soco_timeout)
        # sonos_devices is a list of four-tuples:
        #   (Household ID, IP, Zone Name, Is Coordinator?)
        return (
            speaker.household_id,
            str(ip_addr),
            info["zone_name"],
            speaker.is_coordinator,
        )
    except BaseException as e:
        # Probably not a Sonos device
        return None


def scan_for_sonos_worker(ip_list, socket_timeout, soco_timeout, sonos_devices):
    while len(ip_list) > 0:
        ip_addr = ip_list.pop(0)
        if probe_ip_and_port(str(ip_addr), 1400, socket_timeout):
            device = get_sonos_device_data(ip_addr, soco_timeout)
            if device:
                sonos_devices.append(device)


def list_sonos_devices(threads=256, socket_timeout=1, soco_timeout=1):
    """Returns a list of ..."""
    ip_list = []
    # Set up the list of IPs to search
    for network in find_my_ipv4_networks():
        for ip_addr in network:
            ip_list.append(ip_addr)
    # Start threads to check IPs for Sonos devices
    thread_list = []
    sonos_devices = []
    # Create parallel threads to scan the IP range
    if threads > len(ip_list):
        threads = len(ip_list)
    for _ in range(threads):
        thread = threading.Thread(
            target=scan_for_sonos_worker,
            args=(ip_list, socket_timeout, soco_timeout, sonos_devices),
        )
        thread_list.append(thread)
        thread.start()
    # Wait for all threads to finish before returning
    for thread in thread_list:
        thread.join()
    return sonos_devices


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
        default=1,
        help="Network timeouts (float, seconds) to use when probing the network (default = 1s)",
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

    pp = pprint.PrettyPrinter()
    pp.pprint(
        list_sonos_devices(
            threads=args.threads,
            socket_timeout=args.network_timeout,
            soco_timeout=args.network_timeout,
        )
    )
