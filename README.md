# Soco CLI: Control Sonos Systems from the Command Line

**Please consider this utility to be experimental at the moment. The command line structure and return values are not yet fully finalised. Feedback welcome.**

## Overview

Soco CLI is a command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems. Soco CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command is provided which allows easy control of speaker playback, volume, groups, EQ settings, sleep timers, etc. Multiple commands can be run in sequence, including the ability to insert delays between commands.

Sonos CLI aims for an orderly command structure and consistent return values, making it suitable for use in scripted automation scenarios, `cron` jobs, etc.

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

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0). If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code.

If you experience any issues with finding your speakers, or if you have multiple Sonos systems ('Households') on your network, please take a look at the [Alternative Discovery](#alternative-discovery) section below. You may prefer to use this approach anyway, even if normal SoCo discovery works for you, as it offers some advantages.

### Simple Usage Examples:

- **`sonos "Living Room" volume`** Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.
- **`sonos Kitchen play_favourite Jazz24 : wait 1800 : Kitchen stop`** Plays 'Jazz24' for 30 minutes (1800 seconds), then stops playback.

#### Options

- **`--version, -v`**: Print the versions of soco-cli and SoCo, and exit.

The following options are for use with the alternative discovery mechanism:

- **`--use-local-speaker-list, -l`**: Use the local speaker list instead of SoCo discovery. The speaker list will first be created and saved if it doesn't already exist.
- **`--refresh-local-speaker-list, -l`**: In conjunction with the `-l` option, the speaker list will be regenerated and saved.
- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 3.0s.

Note that the `sonos-discover` utility (discussed below) can also be used to manage the local speaker list.

### Actions

#### Volume and EQ Control

- **`balance`**: Returns the balance setting of the speaker as a value between -100 and +100, where -100 is left channel only, 0 is left and right set to the same volume, and +100 is right channel only.
- **`balance <balance_setting>`**: Sets the balance of the speaker to a value between -100 and +100, where -100 is left channel only, 0 is left and right set to the same volume, and +100 is right channel only. Intermediate values produce a mix of right/left channels.
- **`bass`**: Returns the bass setting of the speaker, from -10 to 10.
- **`bass <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`dialog_mode <on|off>`** (or **`dialog`**): Sets the dialog mode setting of the speaker to 'on' of 'off' (if applicable).
- **`dialog_mode`** (or **`dialog`**): Returns the dialog mode setting of the speaker, 'on' or 'off' (if applicable).
- **`group_mute`**: Returns the group mute state of a group of speakers, 'on' or 'off'.
- **`group_mute <on|off>`**: Sets the group mute state of a group of speakers to 'on' or 'off'.
- **`group_relative_volume <adjustment>` (or `group_rel_vol`, `grv`)**: Raises or lowers the group volume by `<adjustment>` which must be a number from -100 to 100.
- **`group_volume` (or `group_vol`)**: Returns the current group volume setting of the speaker's group (0 to 100)
- **`group_volume <volume>` (or `group_vol`)**: Sets the volume of the speaker's group to `<volume>` (0 to 100).
- **`loudness`**: Returns the loudness setting of the speaker, 'on' or 'off'.
- **`loudness <on|off>`**: Sets the loudness setting of the speaker to 'on' or 'off'.
- **`mute`**: Returns the mute setting of the speaker, 'on' or 'off'.
- **`night_mode <on|off>`** (or **`night`**): Sets the night mode setting of the speaker to 'on' or 'off' (if applicable).
- **`night_mode`** (or **`night`**): Returns the night mode setting of the speaker, 'on' or 'off' (if applicable).
- **`mute <on|off>`**: Sets the mute setting of the speaker to 'on' or 'off'.
- **`ramp_to_volume <volume>` (or `ramp`)**: Gently raise or reduce the volume to `<volume>`, which is between 0 and 100. Returns the number of seconds to complete the ramp.
- **`relative_volume <adjustment>` (or `rel_vol`, `rv`)**: Raises or lowers the volume by `<adjustment>`, which must be a number from -100 to 100.
- **`treble`**: Returns the treble setting of the speaker, from -10 to 10.
- **`treble <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`volume` (or `vol`)**: Returns the current volume setting of the speaker (0 to 100)
- **`volume <volume>` (or `vol`)**: Sets the volume of the speaker to `<volume>` (0 to 100).

#### Playback Control

- **`cross_fade`**: Returns the cross fade setting of the speaker, 'on' or 'off'.
- **`cross_fade <on|off>`**: Sets the cross fade setting of the speaker to 'on' of 'off'.
- **`line_in`**: Returns a speaker's Line-In state, 'on' if its input is set to a Line-In source, 'off' otherwise.
- **`line_in <on or line_in_speaker>`**: Switch a speaker to its own Line-In input (`<on>`), **or** the Line-In input of `<line_in_speaker>` (if applicable). Note that this does not start Line_in playback; issue the `play` action to start Line-In playback.
- **`next`**: Move to the next track (if applicable for the current audio source).
- **`pause`**: Pause playback (if applicable for the audio source).
- **`pause_all`**: Pause playback on all speakers in the system. (Note: only pauses speakers that are in the same Sonos Household.)
- **`play`**: Start playback.
- **`playback`** (or **`state`**): Returns the current playback state for the speaker.
- **`play_from_queue <track>`** (or **`play_queue`, `pfq`, `pq`**): Play track number `<track>` from the queue. Tracks begin at 1. If `<track>` is omitted, the first item in the queue is played.
- **`play_mode` (or `mode`)**: Returns the play mode of the speaker, one of `NORMAL`, `REPEAT_ONE`, `REPEAT_ALL`, `SHUFFLE` or `SHUFFLE_NOREPEAT`.
- **`play_mode <mode>` (or `mode`)**: Sets the play mode of the speaker to `<mode>`, which is one of the values above.
- **`play_uri <uri> <title>` (or `uri`, `pu`)**: Plays the audio object given by the `<uri>` parameter (e.g., a radio stream URL). `<title>` is optional, and if present will be used for the title of the audio stream.
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
- **`play_from_queue <track_number>`** (or **`pfq`, `pq`**): Play `<track_number>` from the queue. Track numbers start from 1. If no `<track_number>` is provided, play starts from the beginning of the queue.
- **`queue_length`** (or **`ql`**): Return the length of the current queue.
- **`remove_from_queue <track_number>`** (or **`rq`**): Remove `<track_number>` from the queue. Track numbers start from 1.
- **`save_queue <title>`** (or **`sq`**): Save the current queue as a Sonos playlist called `<title>`.

#### Favourites and Playlists

- **`clear_playlist <playlist>`**: Clear the Sonos playlist named `<playlist>`.
- **`create_playlist <playlist>`**: Create a Sonos playlist named `<playlist>`.
- **`delete_playlist <playlist>`** (or **`remove_playlist`**): Delete the Sonos playlist named `<playlist>`.
- **`favourite_radio_stations`** (or **`favorite_radio_stations`**): List the favourite radio stations.
- **`list_favs`** (or **`list_favorites`, `list_favourites`, `lf`**): Lists all Sonos favourites.
- **`list_playlists`** (or **`playlists`, `lp`**): Lists the Sonos playlists.
- **`play_favourite <favourite_name>` (or `play_favorite`, `favourite`, `favorite`, `fav`, `pf`, `play_fav`)**: Plays the Sonos favourite identified by `<favourite_name>`. The name is loosely matched; if `<favourite_name>` is a (case insensitive) substring of a Sonos favourite, it will match. In the case of duplicates, the first match encountered will be used. If a queueable item, the favourite will be added to the end of the current queue and played. **Note: this currently works only for certain types of favourite: local library tracks and playlists, radio stations, single Spotify tracks, etc.**
- **`play_favourite_radio_station <station_name>`** (or **`play_favorite_radio_station`, `pfrs`**): Play a favourite radio station. Note that this action doesn't work well: it's better to add radio stations as normal Sonos favourites, and play them using `favourite`.
- **`remove_from_playlist <playlist_name> <track_number>`** (or **`rfp`**): Remove a track from a Sonos playlist.

#### Grouping and Stereo Pairing

- **`group <master_speaker>`(or `g`**): Groups the speaker with `<master_speaker>`.
- **`pair <right_hand_speaker`**: Creates a stereo pair, where the target speaker becomes the left-hand speaker of the pair and `<right_hand_speaker>` becomes the right-hand of the pair. Can be used to pair dissimilar Sonos devices (e.g., to stereo-pair a Play:1 with a One).
- **`party_mode` (or `party`)**: Adds all speakers in the system into a single group. The target speaker becomes the group coordinator. Remove speakers individually using `ungroup`.
- **`ungroup` (or `ug`, `u`)**: Removes the speaker from a group.
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

## Multiple Sequential Commands

Multiple commands can be run as part of the same `sonos` invocation by using the `:` separator to add multiple `SPEAKER ACTION <parameters>` sequences to the command line. The `:` separator must be surrounded by spaces.

A `wait <seconds>` (or `w`, `sleep`) primitive is available that simply waits for the specified number of seconds before moving on to the next command. This is useful when, for example, one wants to play audio for a specific period of time, or maintain a speaker grouping for a specific period, etc.

An arbitrary number of commands can be supplied as part of a single `sonos` invocation. If a failure is encountered with any command, `sonos` will terminate and will not execute the remaining commands.

Examples:

- **`sonos Bedroom group Study : Study group_volume 50 : Study play : wait 600 : Study stop : Study ungroup`**
- **`sonos Kitchen play_favourite Jazz24 : wait 1800 : Kitchen stop`**

## Alternative Discovery

Sonos CLI depends on the speaker discovery mechanisms in SoCo, which uses mDNS multicast to discover Sonos devices when they are referenced by speaker name.

Sonos CLI also provides an alternative discovery process, which works by scanning the network(s) to which your device is attached, and generating and saving a list of Sonos speaker names and other information.

There are three reasons why you might want to use this alternative mechanism:

1. On some networks, particularly on WiFi, multicast forwarding does not work properly. This prevents normal SoCo speaker discovery.

2. If you have two Sonos systems on the same network, for example when there is a 'split' S1/S2 system, normal SoCo discovery will find only one of the systems, which may not include the speaker you want to control. In this case, discovery will fail.

3. It's often faster and more convenient to use the local cached speaker list. For example, speaker name matches can be case insensitive and can match on substrings.

It should be noted that it's always possible to avoid any kind of discovery step by using a speaker's IP address directly.

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
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 10.0s.

These options only have an effect when combined with the `-l` **and** `-r` options.

**Example**: **`sonos -lr -t 256 -n 1.0 "living room" volume 50`**

### The `sonos-discover` Utility

**`sonos-discover`** is a standalone utility for creating/updating the local speaker cache, and for seeing the results of the discovery process. It offers the same `-t` and `-n` options as the `sonos` command. The **`--print`** or **`-p`** option will print the results of the discovery process. It's an alternative to using the `sonos -r` command.

**Example**: **`sonos-discover -p -t 256 -n 1.0`** will run `sonos-discover` with a maximum of 256 threads, a network timeout of 1.0s, and will print the result.

#### `sonos-discover` options

Without options, `sonos-discover` will execute the discovery process and complete silently. It will create a speaker cache file, or replace it if already present.

Other options:

- **`--print, -p`**: Print the results after discovery, including the networks that were searched.
- **`--show-local-speaker-cache, -s`**: Read and print the current contents of the speaker cache file, then exit.
- **`--delete-local-speaker-cache, -d`**: Delete the local speaker cache file.
- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 10.0s; increase this if sonos-discover is not finding all of your Sonos devices.

## Resources

[1] https://github.com/SoCo/SoCo \
[2] https://pypi.org/project/soco-cli

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.