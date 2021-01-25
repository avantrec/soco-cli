"""Manages aliases for use with the interactive shell"""

import logging
import pickle

from os import mkdir, path


CONFIG_DIR = path.join(path.expanduser("~"), ".soco-cli")
ALIAS_FILE = path.join(CONFIG_DIR, "aliases.pickle")


class AliasManager:
    def __init__(self):
        self._aliases = {}

    def create_alias(self, alias_name, alias_actions):
        if alias_actions in [None, ""]:
            return self.remove_alias(alias_name)
        else:
            if self._aliases.get(alias_name, None):
                new = False
            else:
                new = True
            logging.info("Adding alias '{}', new = {}".format(alias_name, new))
            self._aliases[alias_name] = alias_actions
            return True, new

    def action(self, alias_name):
        return self._aliases.get(alias_name, None)

    def remove_alias(self, alias_name):
        try:
            del self._aliases[alias_name]
            logging.info("Removing alias '{}'".format(alias_name))
            return True
        except KeyError:
            logging.info("Alias '{}' not found".format(alias_name))
            return False

    def alias_names(self):
        return list(self._aliases.keys())

    def save_aliases(self):
        if not path.exists(CONFIG_DIR):
            try:
                logging.info("Creating directory '{}'".format(CONFIG_DIR))
                mkdir(CONFIG_DIR)
            except:
                pass
        with open(ALIAS_FILE, "wb") as f:
            logging.info("Saving aliases")
            pickle.dump(self._aliases, f)

    def load_aliases(self):
        logging.info("Reading aliases")
        try:
            with open(ALIAS_FILE, "rb") as f:
                self._aliases = pickle.load(f)
        except:
            logging.info("Failed to read aliases from file")
            pass

    def print_aliases(self):
        if len(self._aliases) == 0:
            print("No current aliases")
            return

        # Find the longest alias name
        max_alias = 0
        for alias_name in self._aliases.keys():
            alias_len = len(alias_name)
            max_alias = max_alias if alias_len <= max_alias else alias_len

        # Print each alias
        print()
        for alias_name in sorted(self._aliases.keys()):
            print("  ", alias_name.ljust(max_alias), "=", self._aliases[alias_name])
            # print(spacer + alias_name + " = " + self._aliases[alias_name])
        print()
