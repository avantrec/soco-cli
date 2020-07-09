# Soco CLI: Control Sonos Systems from the Command Line

**Please consider this utility to be experimental at the moment. The code is functional but requires cleanup, and the command line structure and return values are not yet finalised.**

## Overview

Soco CLI is a command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems. Soco CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command is provided which allows easy control of speaker playback, volume, groups, EQ settings, sleep timers, etc.

Sonos CLI aims for an orderly command structure and consistent return values, making it suitable for use in scripted automation scenarios, `cron` jobs, etc.

If you experience any issues with finding speakers, please take a look at the [Alternative Discovery](#alternative-discovery) section below. (You may prefer to use this approach anyway, even if normal SoCo discovery works for you.)

## Supported Environments

- Requires Python 3.5 or greater.
- Should run on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.

## Installation

Install from PyPi [2] using **`pip install soco-cli`**.

## User Guide

The installer adds the `sonos` command to the PATH. All commands have the form:

```
sonos SPEAKER ACTION <parameters>
```

- `SPEAKER` identifies the speaker, and can be the speaker's Sonos Room name or its IPv4 address in dotted decimal format. Note that the speaker name is case sensitive (unless using alternative discovery, discussed below).
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0).

If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code.

### Simple Usage Examples:

- **`sonos "Living Room" volume`** Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.

### Available Actions

#### Volume and EQ Control

- **`balance`**: Returns the balance setting of the speaker as a pair of values (L, R) where each of L and R is between 0 and 100.
- **`balance <left volume> <right volume>`**: Sets the balance of the speaker to. L and R must be between 0 and 100. (Examples: L=100, R=100 is level balance; L=0, R=100 drives the right channel only, etc.)
- **`bass`**: Returns the bass setting of the speaker, from -10 to 10.
- **`bass <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`dialog_mode <on|off>`** (or **`dialog`**): Sets the dialog mode setting of the speaker to 'on' of 'off' (if applicable).
- **`dialog_mode`** (or **`dialog`**): Returns the dialog mode setting of the speaker, 'on' or 'off' (if applicable).
- **`group_mute`**: Returns the group mute state of a group of speakers, 'on' or 'off'.
- **`group_mute <on|off>`**: Sets the group mute state of a group of speakers to 'on' or 'off'.
- **`group_relative_volume <adjustment>` (or `group_rel_vol`)**: Raises or lowers the group volume by `<adjustment>` which must be a number from -100 to 100.
- **`group_volume` (or `group_vol`)**: Returns the current group volume setting of the speaker's group (0 to 100)
- **`group_volume <volume>` (or `group_vol`)**: Sets the volume of the speaker's group to `<volume>` (0 to 100).
- **`loudness`**: Returns the loudness setting of the speaker, 'on' or 'off'.
- **`loudness <on|off>`**: Sets the loudness setting of the speaker to 'on' of 'off'.
- **`mute`**: Returns the mute setting of the speaker, 'on' or 'off'.
- **`night_mode <on|off>`** (or **`night`**): Sets the night mode setting of the speaker to 'on' of 'off' (if applicable).
- **`night_mode`** (or **`night`**): Returns the night mode setting of the speaker, 'on' or 'off' (if applicable).
- **`mute <on|off>`**: Sets the mute setting of the speaker to 'on' of 'off'.
- **`ramp_to_volume <volume>` (or `ramp`)**: Gently raise or reduce the volume to `<volume>`, which is between 0 and 100. Returns the number of seconds to complete the ramp.
- **`relative_volume <adjustment>` (or `rel_vol`)**: Raises or lowers the volume by `<adjustment>`, which must be a number from -100 to 100.
- **`treble`**: Returns the treble setting of the speaker, from -10 to 10.
- **`treble <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`volume` (or `vol`)**: Returns the current volume setting of the speaker (0 to 100)
- **`volume <volume>` (or `vol`)**: Sets the volume of the speaker to `<volume>` (0 to 100).

#### Playback Control

- **`cross_fade`**: Returns the cross fade setting of the speaker, 'on' or 'off'.
- **`cross_fade <on|off>`**: Sets the cross fade setting of the speaker to 'on' of 'off'.
- **`favourite <favourite_name>` (or `favorite`, `fav`, `pf`, `play_fav`)**: Plays the Sonos favourite identified by `<favourite_name>`. The name is loosely matched; if `<favourite_name>` is a (case insensitive) substring of a Sonos favourite, it will match. In the case of duplicates, the first match encountered will be used. **Note: this currently works only for certain types of favourite: local library tracks and playlists, radio stations, single Spotify tracks, etc.**
- **`line_in`**: Returns a speaker's Line-In state, 'on' if its input is set to Line-In, 'off' otherwise.
- **`line_in on`**: Switch a speaker to its Line-In input (if applicable). Note that this does not start Line_in playback; issue the `play` action to start Line-In playback.
- **`line_in on <line_in_speaker`**: Switch a speaker to the Line-In input of `<line_in_speaker>` (if applicable). Note that this does not start Line_in playback; issue the `play` action to start Line-In playback.
- **`list_favs`** (or **`list_favorites`, `list_favourites`, `lf`**): Lists the Sonos favourites applicable to this speaker.
- **`list_playlists`** (or **`playlists`, `lp`**): Lists the Sonos playlists applicable to this speaker.
- **`next`**: Move to the next track (if applicable for the current audio source).
- **`pause`**: Pause playback (if applicable for the audio source).
- **`pause_all`**: Pause playback on all speakers in the system. (Note: only pauses speakers that are in the same Sonos Household.)
- **`play`**: Start playback.
- **`playback`** (or **`state`**): Returns the current playback state for the speaker.
- **`play_from_queue <track>`** (or **`play_queue`, `pfq`, `pq`**): Play track number `<track>` from the queue. Tracks begin at 1.
- **`play_mode` (or `mode`)**: Returns the play mode of the speaker, one of `NORMAL`, `REPEAT_ONE`, `REPEAT_ALL`, `SHUFFLE` or `SHUFFLE_NO_REPEAT`.
- **`play_mode <mode>` (or `mode`)**: Sets the play mode of the speaker to `<mode>`, which is one of the values above.
- **`play_uri <uri> <title>` (also `uri`)**: Plays the audio object given by the `<uri>` parameter (e.g., a radio stream URL). `<title>` is optional, and if present will be used for the title of the audio stream.
- **`previous` (or `prev`)**: Move to the previous track (if applicable for the audio source).
- **`seek <HH:MM:SS>`**: Seek to a point within a track (if applicable for the audio source).
- **`sleep_timer` (or `sleep`)**: Returns the current sleep timer remaining time in seconds; 0 if no sleep timer is active.
- **`sleep_timer <seconds>` (or `sleep`)**: Set the sleep timer to `<seconds>` seconds.
- **`stop`**: Stop playback.
- **`track`**: Return information about the currently playing track.

#### Queue Actions

- **`add_playlist_to_queue <playlist_name>`** (or **`add_pl_to_queue`, `apq`**): Add `<playlist_name>` to the queue. Name matching is case insensitive, and will work on partial matches. (To start playback, follow with action `play_from_queue`.)
- **`clear_queue`** (or **`cq`**): Clears the current queue
- **`list_queue`** (or **`lq`**): List the tracks in the queue
- **`play_from_queue <track_number>`** (or **`pfq`, `pq`, `q`**): Play `<track_number>` from the queue. Track numbers start from 1.
- **`remove_from_queue <track_number>`** (or **`rq`**): Remove `<track_number>` from the queue. Track numbers start from 1.

#### Grouping and Stereo Pairing

- **`group <master_speaker>`(or `g`**): Groups the speaker with `<master_speaker>`.
- **`pair <right_hand_speaker`**: Creates a stereo pair, where the target speaker becomes the left-hand speaker of the pair and `<right_hand_speaker>` becomes the right-hand of the pair. Can be used on dissimilar speakers.
- **`party_mode` (or `party`)**: Adds all speakers in the system into a single group. The target speaker becomes the group coordinator. Remove speakers individually using `ungroup`.
- **`ungroup` (or `u`)**: Removes the speaker from a group.
- **`ungroup_all`**: Removes all speakers in the target speaker's household from all groups.
- **`unpair`**: Separate a stereo pair. Can be applied to either speaker in the pair.

#### Speaker and Sonos System Information

- **`groups`**: Lists all groups in the Sonos system. Also includes single speakers as groups of one, and paired/bonded sets as groups.
- **`info`**: Provides detailed information on the speaker's settings, current state, software version, IP address, etc.
- **`reindex`**: Start a reindex of the local music libraries.
- **`status_light` (or `light`)**: Returns the state of the speaker's status light, 'on' or 'off'.
- **`status_light <on|off>` (or `light`)**: Switch the speaker's status light on or off.
- **`zones` (or `visible_zones`, `rooms`, `visible_rooms`)**: Returns the room names (and associated IP addresses) that are visible in the Sonos controller apps. Use **`all_zones` (or `all_rooms`)** to return all devices including ones not visible in the Sonos controller apps.
- **`version`**: Report the versions of soco-cli and soco. (A speaker name must be provided, but doesn't need to be a valid name.)

## Multiple Commands

Multiple commands can be run as part of the same `sonos` invocation by using the `:` separator to add multiple `SPEAKER ACTION <parameters>` sequences to the command line. These will be executed in order.

When using multiple commands, a new `wait <seconds>` (or `w`, `sleep`) primitive is available that simply waits for the specified number of seconds before moving on to the next command. This is useful for instances where one wants to play audio for a specific period of time, or maintain a speaker goruping for a specific period, etc.

An arbitrary number of commands can be supplied as part of a single `sonos` invoctaion. If a failure is encountered with any command, `sonos` will terminate and will not execute the remaining commands.

Examples:

- **`sonos Bedroom group Study : Study group_volume 50 : Study play : wait 600 : Study stop : Study ungroup`**
- **`sonos Kitchen play_favourite Jazz24 : wait 1800 : Kitchen stop`**

## Alternative Discovery

Sonos CLI depends on the speaker discovery mechanisms in SoCo (unless one knows and uses the speaker IP addresses directly). This should work for most people, but there are issues (related to multicast forwarding) on some networks that can prevent Soco from finding speakers. There is also an issue if there is more than one Sonos system ('Household') on the same network, as would be the case if there is a 'split' S1/S2 Sonos system: SoCo discovery will pick one of the systems, and your required speaker may not be in that system.

To overcome these issues, Soco CLI provides an alternative discovery mechanism that scans the network for Sonos devices without depending on multicast, and which works with multiple Sonos systems on the same network. This mechanism scans your local network(s) for Sonos devices and caches the results for use in subsequent invocations of the `sonos` command. These will execute immediately, without the discovery delay.

### Usage

To use this discovery mechanism with `sonos`, use the `--use-local-speaker-list` or `-l` flag. The first time this flag is used, the discovery process will be initiated. This will take a few seconds to complete, after which the `sonos` command will execute. A local speaker list is stored in `<your_home_directory>/.soco-cli/` for use with future invocations of the `sonos` command.

**Example**: **`sonos -l "living room" volume 50`** uses the local speaker database to look up the "living room speaker".

### Speaker Naming

When using the local speaker list, speaker naming does not need to be exact, unlike when using standard discovery. Matching is case insensitive, and matching works on substrings. For example, if you have a speaker named `Front Reception`, then `"front reception"` or just `front` will match. (Be careful not to submit ambiguously matchable speaker names; the first hit will be matched, and may not be the speaker you intend.)

### Refreshing the Local Speaker List

If your speakers change in some way (e.g., they are renamed, are assigned different IP addresses, or you add/remove speakers), you can refresh the discovery cache using the `--refresh-speaker-list` or `-r` option. Note that this option only has an effect when combined with the `-l` option. You can also use the `sonos-discover` command (below)

**Example**: **`sonos -lr "living room" volume 50`** will refresh the discovery cache before executing the `sonos` command.

### Discovery Options

The following flags can be used to adjust network discovery behaviour if the discovery process is failing:

- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 3.0s.

These options only have an effect when combined with the `-l` **and** `-r` options.

**Example**: **`sonos -lr -t 256 -n 1.0 "living room" volume 50`**

### The `sonos-discover` Utility

**`sonos-discover`** is a standalone utility for creating/updating the local speaker cache, and for seeing the results of the discovery process. It offers the same `-t` and `-n` options as the `sonos` command. The **`--print`** or **`-p`** option will print the results of the discovery process. It's an alternative to using the `sonos -r` command.

**Example**: **`sonos-discover -p -t 256 -n 1.0`** will run `sonos-discover` with a maximum of 256 threads, a network timeout of 1.0s, and will print the result.

#### `sonos-discover` options

Without options, `sonos-discover` will execute the discovery process and complete silently. It will create a speaker cache file, or replace it if already present.

Other options:

- **`--print, -p`**: Prints the results of a discovery, including the networks that were searched.
- **`--show-local-speaker-cache, -s`**: Read and print the current contents of the speaker cache file.
- **`--delete-local-speaker-cache, -d`**: Delete the local speaker cache file.
- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 3.0s.

## Resources

[1] https://github.com/SoCo/SoCo \
[2] https://pypi.org/project/soco-cli

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.