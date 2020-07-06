import os
import pickle
import ipaddress
import socket
import soco
import ifaddr
import threading
from collections import namedtuple

# Type for holding speaker details
SonosDevice = namedtuple(
    "SonosDevice",
    ["household_id", "ip_address", "speaker_name", "is_coordinator", "is_visible"],
    rename=False,
)


class Speakers:
    """A class for discovering Sonos speakers, saving and loading speaker data,
    and looking up speaker names.
    """

    def __init__(
        self,
        save_directory=None,
        save_file=None,
        network_threads=128,
        network_timeout=3.0,
    ):
        self._save_directory = (
            save_directory
            if save_directory
            else os.path.expanduser("~") + "/.soco-cli/"
        )
        self._save_file = save_file if save_file else "speakers.pickle"
        self._network_threads = network_threads
        self._network_timeout = network_timeout
        self._speakers = []

    @property
    def speakers(self):
        return self._speakers

    @property
    def save_directory(self):
        return self._save_directory

    @save_directory.setter
    def save_directory(self, directory):
        self._save_directory = directory

    @property
    def save_file(self):
        return self._save_file

    @save_file.setter
    def save_file(self, file):
        self._save_file = file

    @property
    def save_pathname(self):
        return self._save_directory + self._save_file

    @property
    def network_threads(self):
        return self._network_threads

    @network_threads.setter
    def network_threads(self, threads):
        self._network_threads = threads

    @property
    def network_timeout(self):
        return self._network_timeout

    @network_timeout.setter
    def network_timeout(self, timeout):
        self._network_timeout = timeout

    def save(self):
        """Saves the speaker list as a pickle file.
        """
        if not os.path.exists(self._save_directory):
            os.mkdir(self._save_directory)
        if self._speakers:
            pickle.dump(self._speakers, open(self.save_pathname, "wb"))
            return True
        else:
            return False

    def load(self):
        if os.path.exists(self.save_pathname):
            try:
                self._speakers = pickle.load(open(self.save_pathname, "rb"))
            except:
                return False
            return True
        else:
            return False

    def clear(self):
        self._speakers = []

    def remove_save_file(self):
        os.remove(self.save_pathname)

    @staticmethod
    def is_ipv4_address(ip_address):
        try:
            ipaddress.IPv4Network(ip_address)
            return True
        except ValueError:
            return False

    @staticmethod
    def find_ipv4_networks():
        """Return a list of unique IPv4 networks to which this node is attached."""
        ipv4_net_list = []
        adapters = ifaddr.get_adapters()
        for adapter in adapters:
            for ip in adapter.ips:
                if Speakers.is_ipv4_address(ip.ip):
                    # Restrict to common domestic private IP ranges and sensible
                    # netmasks. Experimental ... assumptions need to be tested.
                    if (
                        ip.ip.startswith("192.168") or ip.ip.startswith("10.")
                    ) and ip.network_prefix <= 24:
                        nw = ipaddress.ip_network(
                            ip.ip + "/" + str(ip.network_prefix), False
                        )
                        # Avoid duplicate subnets
                        if nw not in ipv4_net_list:
                            ipv4_net_list.append(nw)
        return ipv4_net_list

    @staticmethod
    def get_ip_search_list():
        ip_list = []
        for network in Speakers.find_ipv4_networks():
            for ip_addr in network:
                ip_list.append(ip_addr)
        return ip_list

    @staticmethod
    def check_ip_and_port(ip, port, timeout):
        """Determine if a port is open"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        if s.connect_ex((ip, port)) == 0:
            return True
        else:
            return False

    @staticmethod
    def get_sonos_device_data(ip_addr, soco_timeout):
        """Interrogate a Sonos device"""
        try:
            speaker = soco.SoCo(str(ip_addr))
            info = speaker.get_speaker_info(refresh=True, timeout=soco_timeout)
            return SonosDevice(
                speaker.household_id,
                str(ip_addr),
                info["zone_name"],
                speaker.is_coordinator,
                speaker.is_visible,
            )
        except Exception as e:
            # Probably not a Sonos device
            return None

    @staticmethod
    def discovery_worker(ip_list, socket_timeout, soco_timeout, sonos_devices):
        """Worker thread to pull IP addresses off a list, test if port 1400 is open,
        and if so pull down the Sonos device data. Return when the list is empty.
        """
        while len(ip_list) > 0:
            ip_addr = ip_list.pop(0)
            if Speakers.check_ip_and_port(str(ip_addr), 1400, socket_timeout):
                device = Speakers.get_sonos_device_data(ip_addr, soco_timeout)
                if device:
                    sonos_devices.append(device)

    def discover(self):
        """Discover the Sonos speakers on the network(s) to which
        this host is attached."""
        ip_list = Speakers.get_ip_search_list()
        thread_list = []
        self._speakers = []
        # Disable SoCo caching to prevent problems caused by multiple households
        soco.core.zone_group_state_shared_cache.enabled = False
        # Create parallel threads to scan the IP range
        threads = self._network_threads
        if threads > len(ip_list):
            threads = len(ip_list)
        for _ in range(threads):
            try:
                # Catch thread creation exceptions
                thread = threading.Thread(
                    target=Speakers.discovery_worker,
                    args=(
                        ip_list,
                        self._network_timeout,
                        (self._network_timeout, self._network_timeout),
                        self._speakers,
                    ),
                )
            except:
                break
            thread_list.append(thread)
            thread.start()
        # Wait for all threads to finish before returning
        for thread in thread_list:
            thread.join()

    def find(self, speaker_name, require_visible=True):
        """Find a speaker by name and return its SoCo object."""
        for speaker in self._speakers:
            # Replace funny Sonos single quotes
            s = speaker.speaker_name.replace("’", "'")
            if s.lower() == speaker_name.lower():
                if require_visible:
                    if speaker.is_visible:
                        return soco.SoCo(speaker.ip_address)
                else:
                    return soco.SoCo(speaker.ip_address)
        return None
