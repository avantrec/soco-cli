# Soco CLI: Control Sonos Systems from the Command Line

**Warning: Please consider this utility to be experimental at the moment. The code is immature and requires cleanup, and the command line structure and return values are not yet fully stable.**

## Overview

Soco CLI is a command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems. Soco CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command is provided which allows easy control of speaker playback, volume, groups, EQ settings, sleep timers, etc.

Sonos CLI aims for an orderly command structure and consistent return values, making it suitable for use in scripted automation scenarios, `cron` jobs, etc.

If you experience any issues with finding speakers, please take a look at the [Alternative Discovery](#alternative-discovery) section below.

## Supported Environments

- Requires Python 3.5 or greater.
- Should run on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.

## Installation

Install from PyPi using **`pip install soco-cli`**.

## User Guide

The installer puts the `sonos` command on the PATH. All commands have the form:

```
sonos SPEAKER ACTION <parameters_required_by_action>
```

- `SPEAKER` identifies the speaker, and can be the speaker's Sonos Room name or its IPv4 address in dotted decimal format. Note that the speaker name is case sensitive (unless using alternative discovery, discussed below).
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0).

If an error is encountered, a short error message will be printed to `stderr`, and the program will return a non-zero exit code.

### Simple Usage Examples:

- **`sonos "Living Room" volume`** Returns the current volume setting of the Living Room speaker.
- **`sonos Study volume 25`** Sets the volume of the Study speaker to 25.
- **`sonos Study group Den`** Groups the Study speaker with the Den.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.

### Available Actions

- **`balance`**: Returns the balance setting of the speaker as a pair of values (L, R) where each of L and R is between 0 and 100.
- **`balance <L:number> <R:number>`**: Sets the balance of the speaker to. L and R must be between 0 and 100. (Examples: L=100, R=100 is level balance; L=0, R=100 drives the right channel only, etc.)
- **`bass`**: Returns the bass setting of the speaker, from -10 to 10.
- **`bass <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`cross_fade`**: Returns the cross fade setting of the speaker, 'on' or 'off'.
- **`cross_fade <on|off>`**: Sets the cross fade setting of the speaker to 'on' of 'off'.
- **`favourite <favourite_name>` (or `favorite`, `fav`)**: Plays the Sonos favourite identified by `<favourite_name>`. The name is loosely matched; if `<favourite_name>` is a (case insensitive) substring of a Sonos favourite, it will match. In the case of duplicates, the first match encountered will be used. **Note: this currently works only for certain types of favourite: local library tracks and playlists, radio stations, single Spotify tracks, etc.**
- **`group <master_speaker>`**: Groups the speaker with `<master_speaker>`.
- **`group_mute`**: Returns the group mute state of a group of speakers, 'on' or 'off'.
- **`group_mute <on|off>`**: Sets the group mute state of a group of speakers to 'on' or 'off'.
- **`groups`**: Lists all groups in the Sonos system. Also includes single speakers as groups of one, and paired/bonded sets as groups.
- **`group_relative_volume <adjustment>` (or `group_rel_vol`)**: Raises or lowers the group volume by <adjustment> which must be a number from -100 to 100.
- **`group_volume` (or `group_vol`)**: Returns the current group volume setting of the speaker's group (0 to 100)
- **`grouo_volume <volume>` (or `group_vol`)**: Sets the volume of the speaker's group to `<volume>` (0 to 100).
- **`info`**: Provides detailed information on the speaker's settings, current state, software version, IP address, etc.
- **`line_in`**: Returns a speaker's Line-In state, 'on' if its input is set to Line-In, 'off' otherwise.
- **`line_in on`**: Switch a speaker to its Line-In input (if applicable). Note that this does not start Line_in playback; issue the `play` action to start Line-In playback.
- **`line_in on <line_in_speaker`**: Switch a speaker to the Line-In input of `<line_in_speaker>` (if applicable). Note that this does not start Line_in playback; issue the `play` action to start Line-In playback.
- **`loudness`**: Returns the loudness setting of the speaker, 'on' or 'off'.
- **`loudness <on|off>`**: Sets the loudness setting of the speaker to 'on' of 'off'.
- **`mute`**: Returns the mute setting of the speaker, 'on' or 'off'.
- **`mute <on|off>`**: Sets the mute setting of the speaker to 'on' of 'off'.
- **`next`**: Move to the next track (if applicable for the current audio source).
- **`pair <right_hand_speaker`**: Creates a stereo pair, where the target speaker becomes the left-hand speaker of the pair and `<right_hand_speaker>` becomes the right-hand of the pair.
- **`party_mode` (or `party`)**: Adds all speakers in the system into a single group. The target speaker becomes the group coordinator. Remove speakers individually using `ungroup`.
- **`pause`**: Pause playback (if applicable for the audio source).
- **`pause_all`**: Pause playback on all speakers in the system. (Note: only pauses speakers that are in the same Sonos Household.)
- **`play`**: Start playback.
- **`playback`**: Returns the current playback state for the speaker.
- **`play_mode` (or `mode`)**: Returns the play mode of the speaker, one of NORMAL, REPEAT_ONE, REPEAT_ALL, SHUFFLE or SHUFFLE_NO_REPEAT.
- **`play_mode <mode>` (or `mode`)**: Sets the play mode of the speaker to `<mode>`, which is one of the values above.
- **`play_uri <uri> <title>` (also `uri`)**: Plays the audio object given by the `<uri>` parameter (e.g., a radio stream URL). `<title>` is optional, and if present will be used for the title of the audio stream.
- **`previous` (or `prev`)**: Move to the previous track (if applicable for the audio source).
- **`ramp_to_volume <volume>` (or `ramp`)**: Gently raise or reduce the volume to `<volume>`, which is between 0 and 100. Returns the number of seconds to complete the ramp.
- **`reindex`**: Start a reindex of the local music libraries.
- **`relative_volume <adjustment>` (or `rel_vol`)**: Raises or lowers the volume by <adjustment> which must be a number from -100 to 100.
- **`seek <HH:MM:SS>`**: Seek to a point within a track (if applicable for the audio source).
- **`sleep_timer` (or `sleep`)**: Returns the current sleep timer remaining time in seconds; 0 if no sleep timer is active.
- **`sleep_timer <seconds>` (or `sleep`)**: Set the sleep timer to `<seconds>` seconds.
- **`status_light` (or `light`)**: Returns the state of the speaker's status light, 'on' or 'off'.
- **`status_light <on|off>` (or `light`)**: Switch the speaker's status light on or off.
- **`stop`**: Stop playback.
- **`track`**: Return information about the currently playing track.
- **`treble`**: Returns the treble setting of the speaker, from -10 to 10.
- **`treble <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`ungroup`**: Removes the speaker from a group.
- **`unpair`**: Separate a stereo pair. Can be applied to either speaker in the pair.
- **`volume` (or `vol`)**: Returns the current volume setting of the speaker (0 to 100)
- **`volume <volume>` (or `vol`)**: Sets the volume of the speaker to `<volume>` (0 to 100).
- **`zones` (or `visible_zones`, `rooms`, `visible_rooms`)**: Returns the room names (and associated IP addresses) that are visible in the Sonos controller apps. Use **`all_zones` (or `all_rooms`)** to return all devices including ones not visible in the Sonos controller apps.

## Alternative Discovery

Sonos CLI depends on the speaker discovery mechanisms in SoCo (unless one knows and uses the speaker IP addresses directly). This should work for most people, but there are issues (related to multicast forwarding) on some networks that can prevent Soco from finding speakers. There is also an issue if there is more than one Sonos system ('Household') on the same network, as would be the case if there is a 'split' S1/S2 Sonos system: SoCo discovery will pick one of the systems, and your required speaker may not be in that system.

To overcome these issues, Soco CLI provides an alternative discovery mechanism that scans the network for Sonos devices without depending on multicast, and which works with multiple systems on the same network. This mechanism scans your local network(s) for Sonos devices and caches the results for use in subsequent `sonos` calls. You can see the results of a network scan by using the `sonos-discovery` utility.

### Usage

To use this discovery mechanism with `sonos`, use the `--use-local-speaker-list` or `-l` flag. The first time this flag is used, the discovery process will be initiated. This will take a few seconds to complete, after which the `sonos` command will execute. The results of the discovery scan are stored in `<your_home_directory>/.soco-cli/` for use with future invocations of the `sonos` command.

**Example**: **`sonos -l "living room" volume 50`** uses the local speaker database to look up the "living room speaker".

If your speakers subsequently change (e.g., they are renamed or their IP addresses change, or you add/remove speakers), you can force a refresh of the discovery cache using the `--refresh-speaker-list` or `-r` option. Note that this option only has an effect when combined with the `-l` option.

**Example**: **`sonos -lr "living room" volume 50`** will refresh the discovery cache before executing the `sonos` command.

(Note: this approach will shortly be improved so that `sonos-discover` can be used separately to create or refresh the discovery cache.)

## Resources

[1] https://github.com/SoCo/SoCo

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.