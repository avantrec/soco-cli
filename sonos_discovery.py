# Find Sonos households and speakers

import ipaddress
import socket
import soco

households = set()
speakers = {}

network = ipaddress.ip_network("192.168.0.0/24")
for ip_addr in network:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    endpoint = (str(ip_addr), 1400)
    check = s.connect_ex(endpoint)
    if check == 0:
        speaker = soco.SoCo(str(ip_addr))
        info = speaker.get_speaker_info()
        print("Found", info["zone_name"], "at", str(ip_addr))
        households.add(speaker.household_id)
        if not speakers.get(info["zone_name"]):
            speakers[info["zone_name"]] = (str(ip_addr), speaker.household_id)

print(households)
print()
print(speakers)
