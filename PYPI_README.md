# Soco CLI: Control Sonos Systems from the Command Line

**Please consider this utility to be experimental at the moment. The code works but requires cleanup, and the command line structure and return values are not yet fully finalised.**

## Overview

Soco CLI is a command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems.

A simple `sonos` command is provided which allows easy control of a wide range of speaker actions including playback, volume, grouping, EQ settings, sleep timers, etc.

Sonos CLI aims for an orderly command structure and consistent return values, making it suitable for use in scripted automation scenarios, `cron` jobs, etc.

For cases where standard SoCo speaker discovery doesn't work, an alternative speaker discovery mechanism is provided that scans the network for Sonos devices and caches the results. This supports 'split S1/S2' Sonos systems, allowing control of both.

## Usage

The installer adds the `sonos` command to the PATH. All commands have the form:

```
sonos SPEAKER ACTION <parameters>
```

- `SPEAKER` identifies the speaker, and can be the speaker's Sonos Room name or its IPv4 address in dotted decimal format. Note that the speaker name is case sensitive (unless using alternative discovery, discussed below).
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0).

If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code.

### Usage Examples:

- **`sonos "Living Room" volume`** \
Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** \
Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** \
Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** \
Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** \
Mutes the speaker at the given IP address.

Please see [https://github.com/avantrec/soco-cli](https://github.com/avantrec/soco-cli) for full documentation.

## Links

[1] https://github.com/SoCo/SoCo

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.