# SoCo-CLI: Control Sonos Systems from the Command Line

## Overview

SoCo-CLI is a powerful command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems. SoCo-CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command is provided which allows easy control of speaker playback, volume, groups, EQ settings, sleep timers, etc. Multiple commands can be run in sequence, including the ability to insert delays between commands, to wait for speaker states, and to create repeated action sequences using loops.

SoCo-CLI aims for an orderly command structure and consistent return values, making it suitable for use in scripted automation scenarios, `cron` jobs, etc.

## Supported Environments

- Requires Python 3.5 or greater.
- Runs on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.
- Works with Sonos 'S1' and 'S2' systems, as well as split S1/S2 systems.

## Installation

Install from PyPi [2] using **`pip install soco-cli`**.

## User Guide

The installer adds the `sonos` command to the PATH. All commands have the form:

```
sonos SPEAKER ACTION <parameters>
```

- `SPEAKER` identifies the speaker, and can be the speaker's Sonos Room name or its IPv4 address in dotted decimal format. Note that the speaker name is case sensitive (unless using alternative discovery, discussed in the full documentation).
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0). If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code.

### Simple Usage Examples:

- **`sonos "Living Room" volume`** Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.
- **`sonos Kitchen play_favourite Jazz24 : wait 30m : Kitchen stop`** Plays 'Jazz24' for 30 minutes, then stops playback.

Please see [https://github.com/avantrec/soco-cli](https://github.com/avantrec/soco-cli) for full documentation.

## Links

[1] https://github.com/SoCo/SoCo

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.