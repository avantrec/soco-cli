#!/usr/bin/env python3

# Find Sonos households and speakers

import ipaddress
import socket
import soco
import ifaddr
import threading

households = set()
speakers = {}


def is_ipv4_address(ip_address):
    try:
        ipaddress.IPv4Network(ip_address)
        return True
    except ValueError:
        return False


def find_my_ipv4_networks():
    """Return a list of unique IPv4 networks to which this node is attached"""
    ipv4_net_list = []
    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for ip in adapter.ips:
            if is_ipv4_address(ip.ip):
                # Omit the loopback address
                if ip.ip != "127.0.0.1":
                    nw = ipaddress.ip_network(
                        (ip.ip + "/" + str(ip.network_prefix)), False
                    )
                    # Avoid duplicate subnets
                    if nw not in ipv4_net_list:
                        ipv4_net_list.append(nw)
    return ipv4_net_list


# ToDo: make sure we select the coordinator speaker from speaker groups
def check_ips(ip_list, timeout, sonos_devices):
    while len(ip_list) > 0:
        ip_addr = ip_list.pop(0)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        if s.connect_ex((str(ip_addr), 1400)) == 0:
            speaker = soco.SoCo(str(ip_addr))
            info = speaker.get_speaker_info()
            print("Found", info["zone_name"], "at", str(ip_addr))
            households.add(speaker.household_id)
            if not speakers.get(info["zone_name"]):
                speakers[info["zone_name"]] = (str(ip_addr), speaker.household_id)


DEFAULT_THREADCOUNT = 128
DEFAULT_TIMEOUT = 2  # seconds


def scan_for_sonos(network=None, threadcount=DEFAULT_THREADCOUNT, timeout=DEFAULT_TIMEOUT):
    """Returns a list of ..."""
    ip_list = []
    sonos_devices = []
    # Set up the list of IPs to search
    for network in find_my_ipv4_networks():
        for ip_addr in network:
            ip_list.append(ip_addr)
    # Start threads to check IPs for Sonos devices
    threads = []
    for _ in range(threadcount):
        thread = threading.Thread(
            target=check_ips, args=(ip_list, timeout, sonos_devices)
        )
        threads.append(thread)
        thread.start()
    # Wait for all threads to finish before returning
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    # Populate IP list to search
    scan_for_sonos()

    print(households)
    print()
    print(speakers)
