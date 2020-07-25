# SoCo CLI: Control Sonos Systems from the Command Line

<!--ts-->
   * [SoCo CLI: Control Sonos Systems from the Command Line](#soco-cli-control-sonos-systems-from-the-command-line)
      * [Overview](#overview)
      * [Supported Environments](#supported-environments)
      * [Installation](#installation)
      * [User Guide: the sonos Command](#user-guide-the-sonos-command)
         * [Simple Usage Examples](#simple-usage-examples)
         * [Options for the sonos Command](#options-for-the-sonos-command)
      * [Guidelines on Playing Content](#guidelines-on-playing-content)
         * [Radio Stations](#radio-stations)
         * [Single Tracks](#single-tracks)
         * [Albums and Playlists](#albums-and-playlists)
      * [Available Actions](#available-actions)
         * [Volume and EQ Control](#volume-and-eq-control)
         * [Playback Control](#playback-control)
         * [Queue Actions](#queue-actions)
         * [Favourites and Playlists](#favourites-and-playlists)
         * [Grouping and Stereo Pairing](#grouping-and-stereo-pairing)
         * [Speaker and Sonos System Information](#speaker-and-sonos-system-information)
      * [Multiple Sequential Commands](#multiple-sequential-commands)
         * [Inserting Delays: wait and wait_until](#inserting-delays-wait-and-wait_until)
         * [Examples](#examples)
         * [Waiting Until Playback has Started or Stopped: wait_start and wait_stop Actions](#waiting-until-playback-has-started-or-stopped-wait_start-and-wait_stop-actions)
      * [Alternative Discovery](#alternative-discovery)
         * [Usage](#usage)
         * [Speaker Naming](#speaker-naming)
         * [Refreshing the Local Speaker List](#refreshing-the-local-speaker-list)
         * [Discovery Options](#discovery-options)
         * [The sonos-discover Command](#the-sonos-discover-command)
         * [Options for the sonos-discover Command](#options-for-the-sonos-discover-command)
      * [Resources](#resources)
      * [Acknowledgments](#acknowledgments)

<!-- Added by: pwt, at: Sat Jul 25 19:59:39 BST 2020 -->

<!--te-->

## Overview

Soco CLI is a command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems. Soco CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command is provided which allows easy control of speaker playback, volume, groups, EQ settings, sleep timers, etc. Multiple commands can be run in sequence, including the ability to insert delays between commands.

Sonos CLI aims for an orderly command structure and consistent return values, making it suitable for use in automated scripts, `cron` jobs, etc.

## Supported Environments

- Requires Python 3.5 or greater.
- Should run on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.
- Works with Sonos 'S1' and 'S2' systems, as well as split S1/S2 systems.

## Installation

Install the latest version from PyPi [2] using **`pip install -U soco-cli`**.

Please see the CHANGELOG.txt file for a list of the user-facing changes in each release.

## User Guide: the `sonos` Command

The installer adds the `sonos` command to the PATH. All commands have the form:

```
sonos SPEAKER ACTION <parameters>
```

- `SPEAKER` identifies the speaker to operate on, and can be the speaker's Sonos Room (Zone) name or its IPv4 address in dotted decimal format. Note that the speaker name is case sensitive (unless using 'alternative discovery', discussed below).
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0). If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code. Note that `sonos` actions are executed without seeking any user confirmation; please bear this in mind when manipulating the queue, playlists, etc.!

If you experience any issues with finding your speakers, or if you have multiple Sonos systems ('Households') on your network, please take a look at the [Alternative Discovery](#alternative-discovery) section below. You may prefer to use this approach anyway, even if normal SoCo discovery works for you, as it can be more convenient.

### Simple Usage Examples

- **`sonos "Living Room" volume`** Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.
- **`sonos Kitchen play_favourite Jazz24 : wait 30m : Kitchen stop`** Plays 'Jazz24' for 30 minutes, then stops playback.

### Options for the `sonos` Command

- **`--version, -v`**: Print the versions of soco-cli and SoCo, and exit.
- **`--log <level>`**: Turn on logging. Available levels are NONE (default), CRITICAL, ERROR, WARN, INFO, DEBUG, in order of increasing verbosity.

The following options are for use with the alternative discovery mechanism:

- **`--use-local-speaker-list, -l`**: Use the local speaker list instead of SoCo discovery. The speaker list will first be created and saved if it doesn't already exist.
- **`--refresh-local-speaker-list, -l`**: In conjunction with the `-l` option, the speaker list will be regenerated and saved.
- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 2.0s.

Note that the `sonos-discover` utility (discussed below) can also be used to manage the local speaker list.

## Guidelines on Playing Content

Currently, **soco-cli** enables playback of content from the **Sonos Favourites** and **Sonos Playlists** collections. You should add content to these lists in order to facilitate playback. Content can be from local libraries, streaming services, or streaming radio stations.

### Radio Stations

The best way to play a radio station is to add it to your general list of Sonos Favourites (**not** the radio station favourites), then play it using:

`sonos <speaker_name> play_fav <favourite_name>`

### Single Tracks

As with radio stations, add single tracks from local libraries and music services to your Sonos Favourites, and play them using `play_fav`.

`sonos <speaker_name> play_fav <favourite_name>`

### Albums and Playlists

Albums and playlists from local libraries or music services should be added to your Sonos Playlists. They can then be played by adding them to the queue, and playing from the queue. For example:

`sonos <speaker_name> clear_queue : <speaker_name> add_playlist_to_queue <playlist> : <speaker_name> play_from_queue`

Or, to add to the current queue, then play the first playlist track:

```
sonos <speaker_name> add_playlist_to_queue <playlist>
24 <-- Returns queue position of the first playlist track
sonos <speaker_name> play_from_queue 24
```

## Available Actions

### Volume and EQ Control

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

### Playback Control

- **`cross_fade`** (or **`crossfade`**): Returns the cross fade setting of the speaker, 'on' or 'off'.
- **`cross_fade <on|off>`** (or **`crossfade`**): Sets the cross fade setting of the speaker to 'on' or 'off'.
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
- **`sleep_timer <duration | off | cancel>` (or `sleep`)**: Set the sleep timer to `<duration>`, which can be **one** of seconds, minutes or hours. Floating point values for the duration are acceptable. Examples: **`10s`, `30m`, `1.5h`**. If the s/m/h is omitted, `s` (seconds) is assumed. The time duration formats HH:MM and HH:MM:SS can also be used. To **cancel** a sleep timer, use `off` or `cancel` instead of a duration.
- **`sleep_at <HH:MM:SS>`** Sets the sleep timer to sleep at a time up to 24 hours in the future. For example, to set the speaker to sleep at 4pm, use `sleep_at 16:00`.
- **`stop`**: Stop playback.
- **`track`**: Return information about the currently playing track.

### Queue Actions

- **`add_playlist_to_queue <playlist_name>`** (or **`add_pl_to_queue`, `apq`**): Add `<playlist_name>` to the queue. Name matching is case insensitive, and will work on partial matches. The number in the queue of the first track in the playlist will be returned. To start playback, follow with action `play_from_queue`, optionally followed by the track number.
- **`clear_queue`** (or **`cq`**): Clears the current queue
- **`list_queue`** (or **`lq`, `q`**): List the tracks in the queue
- **`play_from_queue <track_number>`** (or **`pfq`, `pq`**): Play `<track_number>` from the queue. Track numbers start from 1. If no `<track_number>` is provided, play starts from the beginning of the queue.
- **`queue_length`** (or **`ql`**): Return the length of the current queue.
- **`remove_from_queue <track_number>`** (or **`rfq`, `rq`**): Remove `<track_number>` from the queue. Track numbers start from 1.
- **`save_queue <title>`** (or **`sq`**): Save the current queue as a Sonos playlist called `<title>`.

The following has issues and requires further development. For example, it's currently possible to add radio stations to the queue!

- **`add_favourite_to_queue`** (or **`add_favorite_to_queue`, `add_fav_to_queue`, `afq`**): Add a Sonos Favourite to the queue.

### Favourites and Playlists

- **`clear_playlist <playlist>`**: Clear the Sonos playlist named `<playlist>`.
- **`create_playlist <playlist>`**: Create a Sonos playlist named `<playlist>`.
- **`delete_playlist <playlist>`** (or **`remove_playlist`**): Delete the Sonos playlist named `<playlist>`.
- **`favourite_radio_stations`** (or **`favorite_radio_stations`**): List the favourite radio stations.
- **`list_all_playlist_tracks`** (or **`lapt`**): Lists all tracks in all Sonos Playlists.
- **`list_favs`** (or **`list_favorites`, `list_favourites`, `lf`**): Lists all Sonos favourites.
- **`list_playlists`** (or **`playlists`, `lp`**): Lists the Sonos playlists.
- **`list_playlist_tracks <playlist_name>`** (or **`lpt`**): List the tracks in a given Sonos Playlist.
- **`play_favourite <favourite_name>` (or `play_favorite`, `favourite`, `favorite`, `fav`, `pf`, `play_fav`)**: Plays the Sonos favourite identified by `<favourite_name>`. The name is loosely matched; if `<favourite_name>` is a (case insensitive) substring of a Sonos favourite, it will match. In the case of duplicates, the first match encountered will be used. If a queueable item, the favourite will be added to the end of the current queue and played. **Note: this currently works only for certain types of favourite: local library tracks and playlists, radio stations, single Spotify tracks, etc.**
- **`play_favourite_radio_station <station_name>`** (or **`play_favorite_radio_station`, `pfrs`**): Play a favourite radio station. Note that this action doesn't work well: it's better to add radio stations as normal Sonos favourites, and play them using `favourite`.
- **`remove_from_playlist <playlist_name> <track_number>`** (or **`rfp`**): Remove a track from a Sonos playlist.

### Grouping and Stereo Pairing

- **`group <master_speaker>`(or `g`**): Groups the speaker with `<master_speaker>`.
- **`pair <right_hand_speaker`**: Creates a stereo pair, where the target speaker becomes the left-hand speaker of the pair and `<right_hand_speaker>` becomes the right-hand of the pair. Can be used to pair dissimilar Sonos devices (e.g., to stereo-pair a Play:1 with a One).
- **`party_mode` (or `party`)**: Adds all speakers in the system into a single group. The target speaker becomes the group coordinator. Remove speakers individually using `ungroup`.
- **`ungroup` (or `ug`, `u`)**: Removes the speaker from a group.
- **`ungroup_all`**: Removes all speakers in the target speaker's household from all groups.
- **`unpair`**: Separate a stereo pair. Can be applied to either speaker in the pair.

### Speaker and Sonos System Information

- **`alarms`**: List the alarms in the Sonos system.
- **`groups`**: Lists all groups in the Sonos system. Also includes single speakers as groups of one, and paired/bonded sets as groups.
- **`info`**: Provides detailed information on the speaker's settings, current state, software version, IP address, etc.
- **`libraries`** (or **`shares`**): List the local music library shares.
- **`reindex`**: Start a reindex of the local music libraries.
- **`status_light` (or `light`)**: Returns the state of the speaker's status light, 'on' or 'off'.
- **`status_light <on|off>` (or `light`)**: Switch the speaker's status light on or off.
- **`sysinfo`**: Prints a table of information about all speakers in the system.
- **`zones` (or `visible_zones`, `rooms`, `visible_rooms`)**: Returns the room names (and associated IP addresses) that are visible in the Sonos controller apps. Use **`all_zones` (or `all_rooms`)** to return all devices including ones not visible in the Sonos controller apps.

## Multiple Sequential Commands

Multiple commands can be run as part of the same `sonos` invocation by using the `:` separator to add multiple `SPEAKER ACTION <parameters>` sequences to the command line. **The `:` separator must be surrounded by spaces** to disambiguate from other uses of `:` in sonos actions.

An arbitrary number of commands can be supplied as part of a single `sonos` invocation. If a failure is encountered with any command, `sonos` will terminate and will not execute the remaining commands.

### Inserting Delays: `wait` and `wait_until`

```
sonos wait <duration>
sonos wait_until <time>
```

The **`wait <duration>`** action waits for the specified duration before moving on to the next command. Do not supply a speaker name. This action is useful when, for example, one wants to play audio for a specific period of time, or maintain a speaker grouping for a specific period then ungroup, etc.

`<duration>` can be **one** of seconds, minutes or hours. Floating point values for the duration are acceptable. Examples: `wait 10s`, `wait 30m`, `wait 1.5h`. (If the s/m/h is omitted, `s` (seconds) is assumed.) The time duration formats HH:MM and HH:MM:SS can also be used. Examples are `wait 2:30` (waits 2hrs and 30mins), `wait 0:1:25` (waits 1min 25secs).

The **`wait_until <time>`** action pauses sonos command line execution until the specified time, in 24hr HH:MM or HH:MM:SS format, for example `wait_until 16:30`.

### Examples

- **`sonos Bedroom group Study : Study group_volume 50 : Study play : wait 10m : Study stop : Study ungroup`**
- **`sonos Kitchen play_favourite Jazz24 : wait 30m : Kitchen stop`**
- **`sonos Bedroom volume 0 : Bedroom play_favourite "Radio 4" : Bedroom ramp 40 : wait 1h : Bedroom ramp 0 : Bedroom stop`**

### Waiting Until Playback has Started or Stopped: `wait_start` and `wait_stop` Actions

The **`<speaker> wait_start`** and **`<speaker> wait_stop`** actions are used to pause execution of the sequence of `sonos` command processing until a speaker has either started or stopped playback. For example, to reset the volume back to `25` after the `Bedroom` speaker has stopped playing, use the following command sequence:

`sonos Bedroom wait_stop : Bedroom volume 25`

Note that if a speaker is already playing, `wait_start` will continue immediately, and if a speaker is already stopped, `wait_stop` will continue immediately. If the behaviour you want is to continue **after** the **next** piece of audio ends, then you can chain commands as follows:

`<speaker> wait_start : <speaker> wait_stop`

## Alternative Discovery

Soco CLI depends on the speaker discovery mechanisms in SoCo, which uses the native Sonos SSDP multicast process to discover Sonos devices, and then to look up speakers by their name.

Soco CLI also provides an alternative discovery process, which works by scanning the network(s) to which your device is attached, and generating and saving a list of Sonos speaker names and other speaker information.

There are three reasons why you might want to use this alternative mechanism:

1. On some networks, particularly when using WiFi, multicast forwarding does not work properly. This blocks normal SoCo speaker discovery.

2. If you have two Sonos systems on the same network, for example when there is a 'split' S1/S2 system, normal SoCo discovery will find only one of the systems (randomly), which may not be the system that includes the speaker you want to control. In this case, discovery will fail.

3. It's often faster and more convenient to use the local cached speaker list. For example, in terms of convenience, speaker name matches can be case insensitive and can match on substrings.

The disadvantage of using the alternative discovery mechanism is that the speaker list can become stale, requiring a manual refresh.

Note that it's always possible to avoid any kind of discovery step by simply using a speaker's IP address directly.

### Usage

To use this discovery mechanism with `sonos`, use the `--use-local-speaker-list` or `-l` flag. The first time this flag is used, the discovery process will be initiated. This will take a few seconds to complete, after which the `sonos` command will execute. A local speaker list is stored in `<your_home_directory>/.soco-cli/` for use with future invocations of the `sonos` command.

**Example**: **`sonos -l "living room" volume 50`** uses the local speaker database to look up the "living room" speaker.

### Speaker Naming

When using the local speaker list, speaker naming does not need to be exact, unlike when using standard discovery. Matching is case insensitive, and matching works on substrings. For example, if you have a speaker named `Front Reception`, then `"front reception"` or just `front` will match. (Be careful not to submit ambiguously matchable speaker names; the first hit will be matched, and may not be the speaker you intend.)

Note that if you have speakers with the same names in multiple Sonos systems (Households), you will get inconsistent name matches. It's best to keep speaker names unique within a network.

### Refreshing the Local Speaker List

If your speakers change in some way (e.g., they are renamed, are assigned different IP addresses, or you add/remove speakers), you can refresh the discovery cache using the `--refresh-speaker-list` or `-r` option. Note that this option only has an effect when combined with the `-l` option. You can also use the `sonos-discover` command (below)

**Example**: **`sonos -lr "living room" volume 50`** will refresh the discovery cache before executing the `sonos` command.

### Discovery Options

The following flags can be used to adjust network discovery behaviour if the discovery process is failing:

- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 2.0s.

These options only have an effect when combined with the `-l` **and** `-r` options.

**Example**: **`sonos -lr -t 256 -n 1.0 "living room" volume 50`**

### The `sonos-discover` Command

**`sonos-discover`** is a standalone utility for creating/updating the local speaker cache, and for seeing the results of the discovery process. It offers the same `-t` and `-n` options as the `sonos` command. The **`--print`** or **`-p`** option will print the results of the discovery process. It's an alternative to using the `sonos -r` command.

**Example**: **`sonos-discover -p -t 256 -n 1.0`** will run `sonos-discover` with a maximum of 256 threads, a network timeout of 1.0s, and will print the result.

### Options for the `sonos-discover` Command

Without options, `sonos-discover` will execute the discovery process and complete silently. It will create a speaker cache file, or replace it if already present.

Other options:

- **`--print, -p`**: Print the results after discovery, including the networks that were searched.
- **`--show-local-speaker-cache, -s`**: Read and print the current contents of the speaker cache file, then exit.
- **`--delete-local-speaker-cache, -d`**: Delete the local speaker cache file.
- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 2.0s; increase this if sonos-discover is not finding all of your Sonos devices.
- **`--version, -v`**: Print the versions of soco-cli and SoCo, and exit.
- **`--log <level>`**: Turn on logging. Available levels are NONE (default), CRITICAL, ERROR, WARN, INFO, DEBUG, in order of increasing verbosity.

## Resources

[1] https://github.com/SoCo/SoCo \
[2] https://pypi.org/project/soco-cli

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.
