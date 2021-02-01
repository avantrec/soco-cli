"""Manages speaker information for Cached Discovery mode."""

import ipaddress
import logging
import os
import pickle
from collections import namedtuple

import soco
import tabulate

from soco_cli.match_speaker_names import speaker_name_matches

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
        network_threads=256,
        network_timeout=0.1,
        min_netmask=24,
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
        self._min_netmask = min_netmask
        self._speakers = []

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

    @property
    def min_netmask(self):
        return self._min_netmask

    @min_netmask.setter
    def min_netmask(self, min_netmask):
        self._min_netmask = min_netmask

    def save(self):
        """Saves the speaker list as a pickle file."""
        if self._speakers:
            if not os.path.exists(self._save_directory):
                os.mkdir(self._save_directory)
            with open(self.save_pathname, "wb") as f:
                pickle.dump(self._speakers, f)
            return True
        else:
            return False

    def load(self):
        """Loads a saved speaker list"""
        if os.path.exists(self.save_pathname):
            try:
                with open(self.save_pathname, "rb") as f:
                    self._speakers = pickle.load(f)
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
        return self.save_pathname

    def rename(self, old_name, new_name):
        for index, speaker in enumerate(self._speakers):
            if old_name.replace("’", "'") == speaker.speaker_name.replace("’", "'"):
                # Update old record, delete, replace with new
                new_speaker = speaker._replace(speaker_name=new_name)
                del self._speakers[index]
                self._speakers.append(new_speaker)
                logging.info(
                    "Renamed speaker in cache: '{}' to '{}'".format(old_name, new_name)
                )
                self.save()
                logging.info("Saved updated cache file")
                return True
        logging.info("Failed to find speaker '{}' for rename".format(old_name))
        return False

    @staticmethod
    def is_ipv4_address(ip_address):
        """Tests for an IPv4 address"""
        try:
            ipaddress.IPv4Network(ip_address)
            return True
        except ValueError:
            return False

    @staticmethod
    def get_sonos_device_data(ip_addr):
        """Get information from a Sonos device"""
        try:
            speaker = soco.SoCo(str(ip_addr))
            info = speaker.get_speaker_info(refresh=True)
            return SonosDevice(
                speaker.household_id,
                str(ip_addr),
                info["zone_name"],
                speaker.is_visible,
                info["model_name"],
                info["display_version"],
            )
        except:
            logging.info("Not a Sonos device: '{}'".format(ip_addr))
            return None

    def discover(self):
        """Discover the Sonos speakers on the network(s) to which
        this host is attached."""

        devices = soco.discovery.scan_network(
            include_invisible=True,
            multi_household=True,
            scan_timeout=self._network_timeout,
            max_threads=self._network_threads,
            min_netmask=self._min_netmask,
        )

        # Populate the device information for each speaker
        for device in devices:
            self._speakers.append(self.get_sonos_device_data(device.ip_address))

    def find(self, speaker_name, require_visible=True):
        """Find a speaker by name and return its SoCo object."""

        speaker_names = set()
        return_speaker = None

        for speaker in self._speakers:
            if require_visible and not speaker.is_visible:
                continue

            match, exact = speaker_name_matches(speaker_name, speaker.speaker_name)

            if match and exact:
                speaker_names.add(speaker.speaker_name)
                return soco.SoCo(speaker.ip_address)

            if match and not exact:
                speaker_names.add(speaker.speaker_name)
                if not return_speaker:
                    return_speaker = soco.SoCo(speaker.ip_address)

        if len(speaker_names) > 1:
            print(
                "Speaker name '{}' is ambiguous within {}".format(
                    speaker_name, speaker_names
                )
            )
            return None

        return return_speaker

    def get_all_speakers(self):
        soco_speakers = []
        for speaker in self._speakers:
            soco_speakers.append(soco.SoCo(speaker.ip_address))
        if soco_speakers:
            return soco_speakers
        else:
            return None

    def get_all_speaker_names(self, include_invisible=False):
        soco_speaker_names = []
        for speaker in self._speakers:
            if speaker.is_visible:
                soco_speaker_names.append(speaker.speaker_name)
        soco_speaker_names.sort()
        return soco_speaker_names

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
