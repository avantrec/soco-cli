"""Captures single keystrokes."""

import sys
from os import name as os_name

if os_name == "nt":
    import msvcrt

else:
    try:
        import termios

    except ImportError:
        pass


def get_keystroke():
    """Wait for a keypress, then return it."""

    # Windows
    if os_name == "nt":
        result = msvcrt.getch().decode()

    # Unix
    else:
        result = None
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        try:
            result = sys.stdin.read(1)
        except IOError:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

    return result
