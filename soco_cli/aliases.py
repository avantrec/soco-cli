"""Manages aliases for use with the interactive shell"""

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
            self._aliases[alias_name] = alias_actions
            return True

    def action(self, alias_name):
        return self._aliases.get(alias_name, None)

    def remove_alias(self, alias_name):
        try:
            del self._aliases[alias_name]
            return True
        except KeyError:
            return False

    def alias_names(self):
        return list(self._aliases.keys())

    def save_aliases(self):
        if not path.exists(CONFIG_DIR):
            try:
                mkdir(CONFIG_DIR)
            except:
                pass
        with open(ALIAS_FILE, "wb") as f:
            pickle.dump(self._aliases, f)

    def load_aliases(self):
        try:
            with open(ALIAS_FILE, "rb") as f:
                self._aliases = pickle.load(f)
        except:
            pass

    def print_aliases(self):
        spacer = " " * 4
        print()
        for alias_name in sorted(self._aliases.keys()):
            print(spacer + alias_name + " : " + self._aliases[alias_name])
        print()
