import os
import pickle
import ipaddress
import socket
import soco
import ifaddr
import threading
import logging
import tabulate
from collections import namedtuple


# Type for holding speaker details
SonosDevice = namedtuple(
    "SonosDevice",
    [
        "household_id",
        "ip_address",
        "speaker_name",
        "is_visible",
        "model_name",
        "display_version",
    ],
    rename=False,
)


class Speakers:
    """A class for discovering Sonos speakers, saving and loading speaker data,
    and finding speakers by name. An alternative to using SoCo discovery.
    """

    def __init__(
        self,
        save_directory=None,
        save_file=None,
        network_threads=128,
        network_timeout=2.0,
    ):
        self._save_directory = (
            save_directory
            if save_directory
            else os.path.expanduser("~") + "/.soco-cli/"
        )
        self._save_file = save_file if save_file else "speakers_v2.pickle"
        self.remove_deprecated_pickle_files()
        self._network_threads = network_threads
        self._network_timeout = network_timeout
        self._speakers = []
        self._networks = []

    def remove_deprecated_pickle_files(self):
        """Remove any older, incompatible versions of the pickle file"""
        for old_file in ["speakers.pickle"]:
            pathname = self._save_directory + old_file
            if os.path.exists(pathname):
                logging.info("Removing old local speaker cache {}".format(pathname))
                # print("Removing deprecated local speaker file:", pathname)
                os.remove(pathname)

    @property
    def speaker_cache_loaded(self):
        if self._speakers:
            return True
        else:
            return False

    @property
    def speaker_cache_file_exists(self):
        if os.path.exists(self.save_pathname):
            return True
        else:
            return False

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
        if self._speakers:
            if not os.path.exists(self._save_directory):
                os.mkdir(self._save_directory)
            pickle.dump(self._speakers, open(self.save_pathname, "wb"))
            return True
        else:
            return False

    def load(self):
        """Loads a saved speaker list"""
        if os.path.exists(self.save_pathname):
            try:
                self._speakers = pickle.load(open(self.save_pathname, "rb"))
            except:
                return False
            return True
        else:
            return False

    def clear(self):
        """Clears the in-memory speaker list"""
        self._speakers = []

    def remove_save_file(self):
        """Removes the saved speaker list file"""
        os.remove(self.save_pathname)

    @staticmethod
    def is_ipv4_address(ip_address):
        """Tests for an IPv4 address"""
        try:
            ipaddress.IPv4Network(ip_address)
            return True
        except ValueError:
            return False

    def find_ipv4_networks(self):
        """Returns a set of IPv4 networks to which this node is attached."""
        ipv4_net_list = set()
        adapters = ifaddr.get_adapters()
        for adapter in adapters:
            for ip in adapter.ips:
                if Speakers.is_ipv4_address(ip.ip):
                    # Restrict to common domestic private IP ranges and sensible
                    # netmasks. Experimental ... assumptions need to be tested.
                    if (
                        ip.ip.startswith("192.168.") or ip.ip.startswith("10.")
                    ) and ip.network_prefix <= 24:
                        nw = ipaddress.ip_network(
                            ip.ip + "/" + str(ip.network_prefix), False
                        )
                        ipv4_net_list.add(nw)
        self._networks = list(ipv4_net_list)
        return ipv4_net_list

    def get_ip_search_list(self):
        """Returns a set of IP addresses to test"""
        ip_list = set()
        for network in self.find_ipv4_networks():
            for ip_addr in network:
                ip_list.add(ip_addr)
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
        """Get information from a Sonos device"""
        try:
            speaker = soco.SoCo(str(ip_addr))
            info = speaker.get_speaker_info(refresh=True, timeout=soco_timeout)
            return SonosDevice(
                speaker.household_id,
                str(ip_addr),
                info["zone_name"],
                speaker.is_visible,
                info["model_name"],
                info["display_version"],
            )
        except Exception as e:
            # Probably not a Sonos device
            return None

    @staticmethod
    def discovery_worker(ip_set, socket_timeout, soco_timeout, sonos_devices):
        """Worker thread to pull IP addresses from a set, test if port 1400 is open,
        and if so pull down the Sonos device data. Return when the list is empty.
        """
        while len(ip_set) > 0:
            ip_addr = ip_set.pop()
            if Speakers.check_ip_and_port(str(ip_addr), 1400, socket_timeout):
                device = Speakers.get_sonos_device_data(ip_addr, soco_timeout)
                if device:
                    sonos_devices.append(device)
                    logging.info("Found Sonos device at: {}".format(device.ip_address))

    def discover(self):
        """Discover the Sonos speakers on the network(s) to which
        this host is attached."""
        ip_list = self.get_ip_search_list()
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
            except RuntimeError:
                break
            thread_list.append(thread)
            thread.start()
        logging.info("Created {} threads for network scan".format(len(thread_list)))
        # Wait for all threads to finish before returning
        for thread in thread_list:
            thread.join()
        # Finally, for each household ID, check that all zones have been recorded
        # using zone information obtained from Sonos
        households = []
        for speaker in self._speakers:
            if speaker.household_id not in households:
                households.append(speaker.household_id)
                try:
                    for zone in soco.SoCo(speaker.ip_address).all_zones:
                        device = Speakers.get_sonos_device_data(
                            zone.ip_address, self._network_timeout
                        )
                        if not device in self._speakers:
                            logging.info(
                                "Group discovery found additional speaker at {}".format(
                                    device.ip_address
                                )
                            )
                            self._speakers.append(device)
                except:
                    pass

    def find(self, speaker_name, require_visible=True):
        """Find a speaker by name and return its SoCo object."""
        # Normalise apostrophes
        speaker_name = speaker_name.replace("’", "'")
        # Check for exact match first
        for speaker in self._speakers:
            # Normalise apostrophes
            s = speaker.speaker_name.replace("’", "'")
            if speaker_name.lower() == s.lower():
                if require_visible:
                    if speaker.is_visible:
                        return soco.SoCo(speaker.ip_address)
                else:
                    return soco.SoCo(speaker.ip_address)
        # Check for partial match if no exact match
        for speaker in self._speakers:
            # Normalise apostrophes
            s = speaker.speaker_name.replace("’", "'")
            if speaker_name.lower() in s.lower():
                if require_visible:
                    if speaker.is_visible:
                        return soco.SoCo(speaker.ip_address)
                else:
                    return soco.SoCo(speaker.ip_address)
        return None

    def print(self):
        if not self._speakers:
            return
        households = {}
        num_devices = 0
        for device in self._speakers:
            if device.household_id not in households:
                households[device.household_id] = []
            if device.is_visible:
                visible = "Visible"
            else:
                visible = "Hidden"
            households[device.household_id].append(
                (
                    device.speaker_name,
                    device.ip_address,
                    device.model_name.replace("Sonos ", ""),
                    visible,
                    device.display_version,
                )
            )
            num_devices += 1

        if self._networks:
            print()
            print("Networks searched: {}".format(self._networks))

        headers = [
            "Room/Zone Name",
            "IP Address",
            "Device Model",
            "Visibility",
            "SW Version",
        ]
        for household in households:
            print()
            print("Sonos Household: {}\n".format(household))
            print(
                tabulate.tabulate(
                    sorted(households[household]), headers, numalign="left"
                )
            )
            print()

        print("{} Sonos Household(s) found".format(len(households)))
        print("{} Sonos device(s) found".format(num_devices))
        print()
