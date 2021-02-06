"""Manages aliases for use with the interactive shell."""

import logging
import pickle
from os import mkdir, path

CONFIG_DIR = path.join(path.expanduser("~"), ".soco-cli")
ALIAS_FILE = path.join(CONFIG_DIR, "aliases.pickle")


class AliasManager:
    def __init__(self):
        self._aliases = {}

    def create_alias(self, alias_name, alias_actions):
        alias_name = alias_name.strip()
        if alias_actions:
            alias_actions = alias_actions.strip()
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
        alias_name = alias_name.strip()
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
        print()
        print(self._aliases_to_text())

    def save_aliases_to_file(self, filename):
        try:
            with open(filename, "w") as f:
                f.write("# Soco-CLI Aliases File\n")
                f.write(self._aliases_to_text(raw=True))
                return True
        except:
            return False

    def load_aliases_from_file(self, filename):
        try:
            with open(filename, "r") as f:
                line = f.readline()
                while line != "":
                    if not line.startswith("#") and line != "\n":
                        if line.count("=") != 1:
                            print("Malformed alias ... ignored")
                            print(line, end="")
                        else:
                            alias = line.split("=")
                            self.create_alias(alias[0], alias[1])
                    line = f.readline()
            self.save_aliases()
            return True
        except:
            return False

    def _aliases_to_text(self, raw=False):
        output = ""
        if not raw:
            max_alias = len(max(self._aliases.keys(), key=len))
        for alias_name in sorted(self._aliases.keys()):
            if raw:
                output = output + alias_name + " = " + self._aliases[alias_name] + "\n"
            else:
                output = (
                    output
                    + "  "
                    + alias_name.ljust(max_alias)
                    + " = "
                    + self._aliases[alias_name]
                    + "\n"
                )
        return output
