#!/usr/bin/env python3

# Find Sonos households and speakers

import ipaddress
import socket
import soco
import ifaddr

households = set()
speakers = {}


def is_ipv4_address(ip_address):
    try:
        ipaddress.IPv4Network(ip_address)
        return True
    except ValueError:
        return False


def find_my_ipv4_networks():
    ip_list = []
    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for ip in adapter.ips:
            if is_ipv4_address(ip.ip):
                # Omit the loopback address
                if ip.ip != "127.0.0.1":
                    ip_list.append(ip.ip + "/" + str(ip.network_prefix))
    return ip_list


# ToDo: make sure we select the group coordinator speaker
ip_searched_list = []
for ip_net in find_my_ipv4_networks():
    network = ipaddress.ip_network(ip_net, False)
    for ip_addr in network:
        if not ip_addr in ip_searched_list:
            ip_searched_list.append(ip_addr)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
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
