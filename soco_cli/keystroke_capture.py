"""Captures single keystrokes.

This feature is currently not available on Windows.
"""

import sys

# termios is not available on Windows
try:
    import termios

except ImportError:
    pass


def get_keystroke():
    """Waits for a keypress, then returns it."""

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
