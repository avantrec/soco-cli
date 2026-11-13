"""Determine the directory used for SoCo-CLI's persistent state.

Resolution order:

1. The ``SOCO_CLI_CONFIG_DIR`` environment variable, if set.
2. The legacy ``~/.soco-cli`` directory, if it already exists. This
   ensures existing installations keep their aliases, shell history,
   speaker cache, etc., without any migration step.
3. A platform-appropriate location:
   - Windows: ``%LOCALAPPDATA%\\soco-cli``
   - macOS: ``~/.soco-cli`` (unchanged)
   - Linux and other POSIX: ``$XDG_CONFIG_HOME/soco-cli``, falling back to
     ``~/.config/soco-cli``
"""

import logging
import os
import platform
from typing import Mapping, Optional

APP_DIR_NAME = "soco-cli"
LEGACY_DIR_NAME = ".soco-cli"
ENV_OVERRIDE = "SOCO_CLI_CONFIG_DIR"


def get_config_dir(
    system: Optional[str] = None,
    home: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return the path of the SoCo-CLI config directory (without creating it).

    The parameters exist to support testing; by default the current platform,
    home directory and environment are used.
    """
    system = platform.system() if system is None else system
    home = os.path.expanduser("~") if home is None else home
    environ = os.environ if environ is None else environ

    override = environ.get(ENV_OVERRIDE)
    if override:
        return os.path.expanduser(override)

    legacy_dir = os.path.join(home, LEGACY_DIR_NAME)
    if os.path.isdir(legacy_dir):
        return legacy_dir

    if system == "Windows":
        local_app_data = environ.get("LOCALAPPDATA")
        if local_app_data:
            return os.path.join(local_app_data, APP_DIR_NAME)
        return legacy_dir

    if system == "Darwin":
        return legacy_dir

    # Linux and other POSIX platforms: XDG Base Directory Specification.
    # Empty or relative values of XDG_CONFIG_HOME must be ignored.
    xdg_config_home = environ.get("XDG_CONFIG_HOME", "")
    if not os.path.isabs(xdg_config_home):
        xdg_config_home = os.path.join(home, ".config")
    return os.path.join(xdg_config_home, APP_DIR_NAME)


def ensure_config_dir(directory: Optional[str] = None) -> bool:
    """Create the config directory (and any parents) if it doesn't exist.

    Returns True if the directory exists on return, False otherwise.
    """
    directory = CONFIG_DIR if directory is None else directory
    if os.path.isdir(directory):
        return True
    logging.info("Creating directory '{}'".format(directory))
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except OSError as e:
        logging.info("Failed to create directory '{}': {}".format(directory, e))
        return False


CONFIG_DIR = get_config_dir()
