# Soco CLI: Control Sonos Systems from the Command Line

**Warning: Please consider this to be experimental at the moment. The code is immature and requires cleanup, and the command line structure and return values are not yet stable.**

## Overview

Soco CLI is a command line wrapper for the popular Python SoCo library, used to develop control programs for Sonos systems. Soco CLI is written entirely in Python, is portable across platforms, and has an orderly command structure and return values suitable for use in scripts.

## Supported Environments

- Requires Python 3.5 or greater.
- Should run on all platforms supported by Python. Tested on Linux, macOS and Windows.

## Installation

Instruction to install from PyPi will follow shortly.

## User Guide

The installer puts the `sonos` command on the PATH. All commands have the form:

```
sonos <flags> SPEAKER_NAME_OR_IP ACTION <parameters_required_by_action>
```

- `SPEAKER_NAME_OR_IP` identifies the speaker, and can be an IPv4 address in dotted decimal format, or the name of the speaker as configured in the Sonos system.
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

### Some simple examples:

| Example | Effect | Returns |
| ------- | ------ | ------- |
| `sonos "Living Room" volume` |  None | 0 to 100 |
| `sonos "Living Room" volume 25` | Sets volume to 25 | No return value |
| `sonos 192.168.0.10 mute on` | Mutes the speaker | No return value |
| `sonos Study group Den` | Groups the Study speaker with Den (master) | No return value |


### Flags


### Commands 

## Speaker Discovery

## Examples

## Known Problems

## Resources