
# SoCo-CLI: Control Sonos from the Command Line

## Overview

SoCo-CLI is a powerful command line wrapper for the popular Python SoCo library [1], for controlling Sonos systems. SoCo-CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command provides easy control over a huge range of speaker functions, including playback, volume, groups, EQ settings, sleep timers, alarms, speaker settings, the playback queue, etc. Multiple commands can be run in sequence, including the ability to insert delays between commands, to wait for speakers to stop or start playing, and to create repeated action sequences using loops. Audio files from the local filesystem can be played directly on Sonos.

SoCo-CLI has an orderly command structure and consistent return values, making it suitable for use in automated scripts, `cron` jobs, etc.

For interactive command line use, SoCo-CLI provides a powerful **Interactive Shell Mode** that improves speed of operation and reduces typing.

SoCo-CLI can be imported as a streamlined, high-level **API** library by other Python programs, and acts as an intermediate abstraction layer between the client program and the underlying SoCo library, simplifying the use of SoCo.

SoCo-CLI can also run as a simple **HTTP API server**, providing access to a huge range of actions via simple HTTP requests. (Requires Python 3.6 or above.)

## Supported Environments

- Requires Python 3.5+. (The HTTP API Server functionality requires Python 3.6 or above.)
- Runs on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.
- Works with Sonos 'S1' and 'S2' systems, as well as split S1/S2 systems.

## Installation

Install from PyPI using **`pip install soco-cli`**.

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