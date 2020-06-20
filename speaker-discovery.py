#!/usr/bin/env python3

# Find Sonos households and speakers

import ipaddress
import socket
import soco
import ifaddr
import threading
import time

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


def check_ip(ip_list):
    while len(ip_list) > 0:
        ip_addr = ip_list.pop(0)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        if s.connect_ex((str(ip_addr), 1400)) == 0:
            speaker = soco.SoCo(str(ip_addr))
            info = speaker.get_speaker_info()
            print("Found", info["zone_name"], "at", str(ip_addr))
            households.add(speaker.household_id)
            if not speakers.get(info["zone_name"]):
                speakers[info["zone_name"]] = (str(ip_addr), speaker.household_id)


# ToDo: make sure we select the coordinator speaker from speaker groups
def search_ips():
    for network in find_my_ipv4_networks():
        for ip_addr in network:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex((str(ip_addr), 1400)) == 0:
                speaker = soco.SoCo(str(ip_addr))
                info = speaker.get_speaker_info()
                print("Found", info["zone_name"], "at", str(ip_addr))
                households.add(speaker.household_id)
                if not speakers.get(info["zone_name"]):
                    speakers[info["zone_name"]] = (str(ip_addr), speaker.household_id)

    print(households)
    print()
    print(speakers)


if __name__ == "__main__":
    # Populate IP list to search
    ip_list = []
    for network in find_my_ipv4_networks():
        for ip_addr in network:
            ip_list.append(ip_addr)
    # Start threads
    for _ in range(128):
        thread = threading.Thread(target=check_ip, args=(ip_list,))
        thread.start()
