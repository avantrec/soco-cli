# SoCo-CLI: Control Sonos Systems from the Command Line

<!--ts-->
   * [SoCo-CLI: Control Sonos Systems from the Command Line](#soco-cli-control-sonos-systems-from-the-command-line)
      * [Overview](#overview)
      * [Supported Environments](#supported-environments)
      * [Installation](#installation)
      * [User Guide: The sonos Command](#user-guide-the-sonos-command)
         * [Simple Usage Examples](#simple-usage-examples)
         * [Options for the sonos Command](#options-for-the-sonos-command)
         * [Operating on All Speakers: Using _all_](#operating-on-all-speakers-using-_all_)
      * [Guidelines on Playing Content](#guidelines-on-playing-content)
         * [Radio Stations](#radio-stations)
         * [Single Tracks](#single-tracks)
         * [Albums and Playlists](#albums-and-playlists)
      * [Complete List of Available Actions](#complete-list-of-available-actions)
         * [Volume and EQ Control](#volume-and-eq-control)
         * [Playback Control](#playback-control)
         * [Queue Actions](#queue-actions)
         * [Favourites and Playlists](#favourites-and-playlists)
         * [TuneIn Radio Station Favourites](#tunein-radio-station-favourites)
         * [Grouping and Stereo Pairing](#grouping-and-stereo-pairing)
         * [Speaker and Sonos System Information](#speaker-and-sonos-system-information)
         * [Music Library Search Functions](#music-library-search-functions)
      * [Multiple Sequential Commands](#multiple-sequential-commands)
         * [Chaining Commands Using the : Separator](#chaining-commands-using-the--separator)
         * [Inserting Delays: wait and wait_until](#inserting-delays-wait-and-wait_until)
         * [Waiting Until Playback has Started/Stopped: wait_start and wait_stop](#waiting-until-playback-has-startedstopped-wait_start-and-wait_stop)
         * [The wait_stopped_for &lt;duration&gt; Action](#the-wait_stopped_for-duration-action)
         * [Repeating Commands: The loop Actions](#repeating-commands-the-loop-actions)
      * [Conditional Command Execution](#conditional-command-execution)
      * [Alternative Discovery](#alternative-discovery)
         * [Usage](#usage)
         * [Speaker Naming](#speaker-naming)
         * [Refreshing the Local Speaker List](#refreshing-the-local-speaker-list)
         * [Discovery Options](#discovery-options)
         * [The sonos-discover Command](#the-sonos-discover-command)
         * [Options for the sonos-discover Command](#options-for-the-sonos-discover-command)
      * [Known Issues](#known-issues)
      * [Uninstalling](#uninstalling)
      * [Acknowledgments](#acknowledgments)
      * [Resources](#resources)

<!-- Added by: pwt, at: Wed Nov 18 09:39:49 GMT 2020 -->

<!--te-->

## Overview

SoCo-CLI is a powerful command line wrapper for the popular Python SoCo library [1] for controlling Sonos systems. SoCo-CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command is provided which allows easy control of speaker playback, volume, groups, EQ settings, sleep timers, etc. Multiple commands can be run in sequence, including the ability to insert delays between commands, to wait for speaker states, and to create repeated action sequences using loops.

SoCo-CLI aims for an orderly command structure and consistent return values, making it suitable for use in automated scripts, `cron` jobs, etc.

## Supported Environments

- Requires Python 3.5 or greater.
- Should run on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.
- Works with Sonos 'S1' and 'S2' systems, as well as split S1/S2 systems.

## Installation

Install the latest version from PyPI [2] using **`pip install -U soco-cli`**.

Please see the CHANGELOG.txt file for a list of the user-facing changes in each release.

## User Guide: The `sonos` Command

The installer adds the `sonos` command to the PATH. All commands have the form:

```
sonos SPEAKER ACTION <parameters>
```

- `SPEAKER` identifies the speaker to operate on, and can be the speaker's Sonos Room (Zone) name or its IPv4 address in dotted decimal format. Note that the speaker name is case sensitive (unless using 'alternative discovery', discussed below).
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the operation.

As usual, command line arguments containing spaces must be surrounded by quotes: double quotes work on all OS platforms, while Linux and macOS also support single quotes.

The `soco` command is also added to the PATH, and can be used as an alias for the `sonos` command if preferred.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0). If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code. Note that `sonos` actions are executed without seeking any user confirmation; please bear this in mind when manipulating the queue, playlists, etc.

If you experience any issues with finding your speakers, or if you have multiple Sonos systems ('Households') on your network, please take a look at the [Alternative Discovery](#alternative-discovery) section below. You may prefer to use this approach anyway, even if normal SoCo discovery works for you, as it can be more convenient.

### Simple Usage Examples

- **`sonos "Living Room" volume`** Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.
- **`sonos Kitchen play_favourite Jazz24 : wait 30m : Kitchen stop`** Plays 'Jazz24' for 30 minutes, then stops playback.

### Options for the `sonos` Command

- **`--version, -v`**: Print the versions of SoCo-CLI and SoCo.
- **`--actions`**: Print the list of available actions.
- **`--docs`**: Print the URL of this README documentation, for the version of SoCo-CLI being used.
- **`--log <level>`**: Turn on logging. Available levels are NONE (default), CRITICAL, ERROR, WARN, INFO, DEBUG, in order of increasing verbosity.

The following options are for use with the alternative discovery mechanism:

- **`--use-local-speaker-list, -l`**: Use the local speaker list instead of SoCo discovery. The speaker list will first be created and saved if it doesn't already exist.
- **`--refresh-local-speaker-list, -r`**: In conjunction with the `-l` option, the speaker list will be regenerated and saved.
- **`--network_discovery_threads, -t`**: The maximum number of parallel threads used to scan the local network.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up).
- **`--min_netmask, -m`**: The minimum netmask to use when scanning networks. Used to constrain the IP search space.

Note that the `sonos-discover` utility (discussed below) can also be used to manage the local speaker list. This is the recommended way of using alternative discovery: first run `sonos-discover` first to create the local speaker database, then use `sonos` with the `-l` option to use the local database.

### Operating on All Speakers: Using `_all_`

There is a limited set of operations where it can be desirable to operate on all speakers, e.g., muting every speaker in the house. This is done by using **`_all_`** as the speaker name. Operations will only be performed on devices that are coordinators (i.e.., the master speakers in any groups or bonded configurations).

If `_all_` is used with the alternative discovery (`--use_local_speaker_list`) mechanism, then the operation is applied to all speakers in all households.

**Examples**: `sonos _all_ mute on` and `sonos _all_ relative_volume -10`.

Note that `_all_` can be used with every `sonos` operation; no checking is performed to ensure that the use of `all` is appropriate, so use with caution.

## Guidelines on Playing Content

SoCo-CLI enables playback of content from the **Sonos Favourites** and **Sonos Playlists** collections, from **local libraries**, and from the **TuneIn 'My Radio Stations'** list.

### Radio Stations

Radio stations can be played by adding them to your Sonos Favourites, and then starting playback using `play_fav`. Alternatively, stations can be added to the TuneIn 'My Radio Stations' list, and played using `play_favourite_radio_station`.

### Single Tracks

As with radio stations, add single tracks from local libraries and music services to your Sonos Favourites, and play them using `play_fav`.

`sonos <speaker_name> play_fav <favourite_name>`

Tracks from local music libraries can also be added to the queue using `sonos <speaker> queue_track <track_name>`, which returns the queue position of the track. It can then be played using `sonos <speaker> play_from_queue <track_number>`.

### Albums and Playlists

Albums and playlists from local libraries or music services can be added to your Sonos Playlists, and then played by adding them to the queue, followed by playing from the queue. For example:

`sonos <speaker_name> clear_queue : <speaker_name> add_playlist_to_queue <playlist> : <speaker_name> play_from_queue`

Or, to add to the current queue, then play the first playlist track:

```
sonos <speaker_name> add_playlist_to_queue <playlist>
24 <-- Returns queue position of the first playlist track
sonos <speaker_name> play_from_queue 24
```

Albums from local music libraries can also be added to the queue using `sonos <speaker> queue_album <album_name>`. The action returns the queue position of the first track in the album, which can then be played as in the example above:

## Complete List of Available Actions

### Volume and EQ Control

- **`balance`**: Returns the balance setting of the speaker as a value between -100 and +100, where -100 is left channel only, 0 is left and right set to the same volume, and +100 is right channel only.
- **`balance <balance_setting>`**: Sets the balance of the speaker to a value between -100 and +100, where -100 is left channel only, 0 is left and right set to the same volume, and +100 is right channel only. Intermediate values produce a mix of right/left channels.
- **`bass`**: Returns the bass setting of the speaker, from -10 to 10.
- **`bass <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`dialog_mode`** (or **`dialog`**, **`dialogue_mode`**, **`dialogue`**): Returns the dialog mode setting of the speaker, 'on' or 'off' (if applicable).
- **`dialog_mode <on|off>`** (or **`dialog`**, **`dialogue_mode`**, **`dialogue`**): Sets the dialog mode setting of the speaker to 'on' of 'off' (if applicable).
- **`group_mute`**: Returns the group mute state of a group of speakers, 'on' or 'off'.
- **`group_mute <on|off>`**: Sets the group mute state of a group of speakers to 'on' or 'off'.
- **`group_relative_volume <adjustment>` (or `group_rel_vol`, `grv`)**: Raises or lowers the group volume by `<adjustment>` which must be a number from -100 to 100.
- **`group_volume` (or `group_vol`)**: Returns the current group volume setting of the speaker's group (0 to 100)
- **`group_volume <volume>` (or `group_vol`)**: Sets the volume of the speaker's group to `<volume>` (0 to 100).
- **`loudness`**: Returns the loudness setting of the speaker, 'on' or 'off'.
- **`loudness <on|off>`**: Sets the loudness setting of the speaker to 'on' or 'off'.
- **`mute`**: Returns the mute setting of the speaker, 'on' or 'off'.
- **`mute <on|off>`**: Sets the mute setting of the speaker to 'on' or 'off'.
- **`night_mode <on|off>`** (or **`night`**): Sets the night mode setting of the speaker to 'on' or 'off' (if applicable).
- **`night_mode`** (or **`night`**): Returns the night mode setting of the speaker, 'on' or 'off' (if applicable).
- **`ramp_to_volume <volume>` (or `ramp`)**: Gently raise or reduce the volume to `<volume>`, which is between 0 and 100. Returns the number of seconds to complete the ramp.
- **`relative_volume <adjustment>` (or `rel_vol`, `rv`)**: Raises or lowers the volume by `<adjustment>`, which must be a number from -100 to 100.
- **`treble`**: Returns the treble setting of the speaker, from -10 to 10.
- **`treble <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`volume` (or `vol`)**: Returns the current volume setting of the speaker (0 to 100)
- **`volume <volume>` (or `vol`)**: Sets the volume of the speaker to `<volume>` (0 to 100).

### Playback Control

- **`cross_fade`** (or **`crossfade`, `fade`**): Returns the cross fade setting of the speaker, 'on' or 'off'.
- **`cross_fade <on|off>`** (or **`crossfade`, `fade`**): Sets the cross fade setting of the speaker to 'on' or 'off'.
- **`line_in`**: Returns a speaker's Line-In state, 'on' if its input is set to a Line-In source, 'off' otherwise. (Use `state` to check whether the Line-In is actually playing.)
- **`line_in <on | line_in_speaker | left_input, right_input | line_in_speaker right_input>`**: Switch a speaker to a Line-In input. Playback is started automatically. A speaker can be switched to its own Line-In input (`<on>`), **or** the Line-In input of another `<line_in_speaker>` (if applicable). For the case where there is a stereo pair of Play:5 or Five speakers, the left hand speaker's Line-In source is selected using `left_input` (default), and the right-hand speaker's Line-In input is selected using `right_input`. (Complicated example: `sonos Bedroom line_in Lounge right_input`, switches the Bedroom to the right-hand input of stereo pair in the Lounge, and starts playback.)
- **`next`**: Move to the next track (if applicable for the current audio source).
- **`pause`**: Pause playback (if applicable for the audio source).
- **`pause_all`**: Pause playback on all speakers in the system. (Note: only pauses speakers that are in the same Sonos Household.)
- **`play`** (or **`start`**): Start playback.
- **`playback`** (or **`state`, `status`**): Returns the current playback state for the speaker.
- **`play_from_queue <track>`** (or **`play_queue`, `pfq`, `pq`**): Play track number `<track>` from the queue. Tracks begin at 1. If `<track>` is omitted, the first item in the queue is played.
- **`play_mode` (or `mode`)**: Returns the play mode of the speaker, one of `NORMAL`, `REPEAT_ONE`, `REPEAT_ALL`, `SHUFFLE`, `SHUFFLE_REPEAT_ONE`, or `SHUFFLE_NOREPEAT`.
- **`play_mode <mode>` (or `mode`)**: Sets the play mode of the speaker to `<mode>`, which is one of the values above.
- **`play_uri <uri> <title>` (or `uri`, `pu`)**: Plays the audio object given by the `<uri>` parameter (e.g., a radio stream URL). `<title>` is optional, and if present will be used for the title of the audio stream.
- **`previous` (or `prev`)**: Move to the previous track (if applicable for the audio source).
- **`repeat` (or `rpt`)**: Returns the repeat mode state: 'off', 'one', or 'all'.
- **`repeat <off,none|one|all>` (or `rpt`)**: Sets the repeat mode state to one of: 'off' (or 'none'), 'one', or 'all'.
- **`seek <time>` (or `seek_to`)**: Seek to a point within a track (if applicable for the audio source). `<time>` can be expressed using the same formats as used for `sleep_timer` below. 
- **`seek_forward <time>` (or `sf`)**: Seek forward within a track (if applicable for the audio source). `<time>` can be expressed using the same formats as used for `sleep_timer` below.
- **`seek_back <time>` (or `sb`)**: Seek backward within a track (if applicable for the audio source). `<time>` can be expressed using the same formats as used for `sleep_timer` below.
- **`shuffle` (or `sh`)**: Returns 'on' if shuffle is enabled, 'off' if not.
- **`shuffle <on|off>` (or `sh`)**: Enables or disables shuffle mode.
- **`sleep_timer` (or `sleep`)**: Returns the current sleep timer remaining time in seconds; 0 if no sleep timer is active.
- **`sleep_timer <duration|off|cancel>` (or `sleep`)**: Set the sleep timer to `<duration>`, which can be **one** of seconds, minutes or hours. Floating point values for the duration are acceptable. Examples: **`10s`, `30m`, `1.5h`**. If the s/m/h is omitted, `s` (seconds) is assumed. The time duration formats HH:MM and HH:MM:SS can also be used. To **cancel** a sleep timer, use `off` or `cancel` instead of a duration.
- **`sleep_at <HH:MM:SS>`**: Sets the sleep timer to sleep at a time up to 24 hours in the future. For example, to set the speaker to sleep at 4pm, use `sleep_at 16:00`.
- **`stop`**: Stop playback.
- **`track`**: Return information about the currently playing track.

### Queue Actions

- **`add_playlist_to_queue <playlist_name> <play_next|next or first|start>`** (or **`queue_playlist`, `add_pl_to_queue`, `apq`**): Add `<playlist_name>` to the queue. Name matching is case insensitive, and will work on partial matches. The number in the queue of the first track in the playlist will be returned. Optionally, `play_next` or `next` can be added to insert the playlist at the next queue position. To start playback, follow with action `play_from_queue`, optionally followed by the track number.
- **`clear_queue`** (or **`cq`**): Clears the current queue
- **`list_queue`** (or **`lq`, `q`**): List the tracks in the queue
- **`list_queue <track_number>`** (or **`lq`, `q`**): List the track in the queue at position `<track_number>`
- **`play_from_queue <track_number>`** (or **`pfq`, `pq`**): Play `<track_number>` from the queue. Track numbers start from 1. If no `<track_number>` is provided, play starts from the beginning of the queue.
- **`queue_album <album_name> <play_next|next or first|start>`** (or **`qa`**): Add `<album_name>` from the local library to the queue. If multiple (fuzzy) matches are found for the album name, a random match will be chosen. Optionally, `next` or `play_next` can be added to insert the album at the next_play position in the queue. The queue position of the first track in the album will be returned.
- **`queue_length`** (or **`ql`**): Return the length of the current queue.
- **`queue_position`** (or **`qp`**): Return the current queue position.
- **`queue_search_result_number <search_index_number> <play_next|next|first|start>`** (or **`queue_search_number`**, **`qsn`**): Queue the item (track or album) at `<search_index_number>` from the last search performed. Optionally, `next` or `play_next` can be added to insert the item at the next_play position in the queue; `start` or `first` can be used to insert the item at the start of the queue. The queue position of the item will be returned.
- **`queue_track <track_name> <play_next|next or first|start>`** (or **`qt`**): Add `<track_name>` from the local library to the queue. If multiple (fuzzy) matches are found for the track name, a random match will be chosen. Optionally, `next` or `play_next` can be added to insert the track at the next_play position in the queue. The queue position of the track will be returned.
- **`remove_current_track_from_queue` (or `rctfq`)**: Remove from the queue the track at the current queue position. If the track is playing, this will have the effect of stopping playback and starting to play the next track. (If the last track in the queue is playing, playback will stop and the previous track will start to play.)
- **`remove_last_track_from_queue <count>` (or `rltfq`)**: Removes the last `<count>` tracks from the queue. If `<count>` is omitted, the last track is removed.
- **`remove_from_queue <track_number|sequence|range>`** (or **`rfq`, `rq`**): Remove tracks from the queue. Track numbers start from 1, and can be supplied as single integers, sequences (e.g., '4,7,3'), or ranges (e.g., '5-10'). Note: do not use spaces either side of the commas and dashes. Sequences and ranges can be mixed, e.g., '1,3-6,10'.
- **`save_queue <title>`** (or **`sq`, `create_playlist_from_queue`**): Save the current queue as a Sonos playlist called `<title>`.

The following has issues and requires further development. For example, it's currently possible to add radio stations to the queue!

- **`add_favourite_to_queue <play_next|next or first|start>` (or `add_favorite_to_queue`, `add_fav_to_queue`, `afq`)**: Add a Sonos Favourite to the queue. Optionally, `play_next` or `next` can be added to add the favourite as the next track or playlist to be played. Returns the queue position of the favourite.

### Favourites and Playlists

- **`clear_playlist <playlist>`**: Clear the Sonos playlist named `<playlist>`.
- **`create_playlist <playlist>`**: Create a Sonos playlist named `<playlist>`. (See also `save_queue` above).
- **`cue_favourite <favourite_name>`** (or **`cue_favorite`, `cue_fav`, `cf`**): Cues up a Sonos favourite for playback. This is a convenience action that issues the sequence: `mute, play_favourite, stop, unmute`. It's useful for silently setting a speaker to a state where it's ready to play the nominated favourite. Mute and group mute states are preserved. 
- **`delete_playlist <playlist>`** (or **`remove_playlist`**): Delete the Sonos playlist named `<playlist>`.
- **`list_all_playlist_tracks`** (or **`lapt`**): Lists all tracks in all Sonos Playlists.
- **`list_favs`** (or **`list_favorites`, `list_favourites`, `lf`**): Lists all Sonos favourites.
- **`list_playlists`** (or **`playlists`, `lp`**): Lists the Sonos playlists.
- **`list_playlist_tracks <playlist_name>`** (or **`lpt`**): List the tracks in a given Sonos Playlist.
- **`play_favourite <favourite_name>` (or `play_favorite`, `favourite`, `favorite`, `fav`, `pf`, `play_fav`)**: Plays the Sonos favourite identified by `<favourite_name>`. The name is loosely matched; if `<favourite_name>` is a (case insensitive) substring of a Sonos favourite, it will match. In the case of duplicates, the first match encountered will be used. If a queueable item, the favourite will be added to the end of the current queue and played. **Note: this currently works only for certain types of favourite: local library tracks and playlists, radio stations, single Spotify tracks, etc.**
- **`play_favourite_radio_station <station_name>`** (or **`play_favorite_radio_station`, `pfrs`**): Play a favourite radio station in TuneIn's 'My Stations' list.
- **`remove_from_playlist <playlist_name> <track_number>`** (or **`rfp`**): Remove a track from a Sonos playlist.

### TuneIn Radio Station Favourites

The following operate on the stations in TuneIn's 'My Radio Stations' list.

- **`cue_favourite_radio_station`** (or **`cue_favorite_radio_station`**, **`cfrs`**): Cue a favourite radio station for later playback. This is a convenience action that issues the sequence: `mute, play_favourite_radio_station, stop, unmute`. It's useful for silently setting a speaker to a state where it's ready to play the nominated favourite. Mute and group mute states are preserved.
- **`favourite_radio_stations`** (or **`favorite_radio_stations`**, **`lfrs`**, **`frs`**): List the favourite radio stations.
- **`play_favourite_radio_station <station_name>`** (or **`play_favorite_radio_station`, `pfrs`**): Play a favourite radio station.

### Grouping and Stereo Pairing

- **`group <master_speaker>`(or `g`)**: Groups the speaker with `<master_speaker>`.
- **`pair <right_hand_speaker>`**: Creates a stereo pair, where the target speaker becomes the left-hand speaker of the pair and `<right_hand_speaker>` becomes the right-hand of the pair. Can be used to pair dissimilar Sonos devices (e.g., to stereo-pair a Play:1 with a One).
- **`party_mode` (or `party`)**: Adds all speakers in the system into a single group. The target speaker becomes the group coordinator. Remove speakers individually using `ungroup`, or use `ungroup_all`.
- **`transfer_playback <target_speaker>` (or `transfer_to`, `transfer`)**: Transfers playback to <target_speaker>. This is achieved by grouping and ungrouping the speakers, and swapping the group coordinator. It's a convenience shortcut for `speaker1 group speaker2 : speaker1 ungroup`.
- **`ungroup` (or `ug`, `u`)**: Removes the speaker from a group.
- **`ungroup_all`**: Removes all speakers in the target speaker's household from all groups.
- **`unpair`**: Separate a stereo pair. Can be applied to either speaker in the pair.

### Speaker and Sonos System Information

- **`alarms`**: List the alarms in the Sonos system.
- **`battery`**: Shows the battery status for a Sonos Move speaker.
- **`groups`**: Lists all groups in the Sonos system. Also includes single speakers as groups of one, and paired/bonded sets as groups.
- **`info`**: Provides detailed information on the speaker's settings, current state, software version, IP address, etc.
- **`libraries`** (or **`shares`**): List the local music library shares.
- **`reindex`**: Start a reindex of the local music libraries.
- **`rename <new_name>`**: Rename the speaker.
- **`status_light` (or `light`)**: Returns the state of the speaker's status light, 'on' or 'off'.
- **`status_light <on|off>` (or `light`)**: Switch the speaker's status light on or off.
- **`sysinfo`**: Prints a table of information about all speakers in the system.
- **`zones` (or `visible_zones`, `rooms`, `visible_rooms`)**: Prints a simple list of comma separated visible zone/room names, each in double quotes. Use **`all_zones` (or `all_rooms`)** to return all devices including ones not visible in the Sonos controller apps.

### Music Library Search Functions

The actions below search the Sonos Music library.

- **`list_albums`** (or **`albums`**): Lists all the albums in the music library.
- **`list_artists`** (or **`artists`**): Lists all the artists in the music library.
- **`last_search`** (or **`ls`**): Prints the results of the last album, track or artist search performed, or the last use of `tracks_in_album`, `list_albums`, or `list_playlist_tracks`. Use with `queue_search_number` to add specific items to the queue.
- **`search_albums <album_name>`** (or **`search_album`**, **`salb`**): Searches the albums in your music library for a fuzzy match with `<album_name>`. Prints out the list of matching albums.
-  **`search_artists <artist_name>`** (or **`search_artist`**, **`sart`**): Searches the artists in your music library for a fuzzy match with `<artist_name>`. Prints out the list of albums featuring any artists that match the search.
- **`search_library <name>`** (or **`sl`**): Searches the titles in your music library for a fuzzy match with `<name>` against artists, albums and tracks. Prints out the lists of matches. This action is a superset of `search_artists`, `search_albums`, and `search_tracks`, i.e., it searches across all categories.
- **`search_tracks <track_name>`** (or **`search_track`**, **`st`**): Searches the tracks in your music library for a fuzzy match with `<track_name>`. Prints out the list of matching tracks.
- **`tracks_in_album <album_name>`** (or **`tia`**, **`lta`**): Searches the albums in your music library for a fuzzy match with `<album_name>`. Prints out the list of tracks in each matching album.

## Multiple Sequential Commands

### Chaining Commands Using the `:` Separator

Multiple commands can be run as part of the same `sonos` invocation by using the `:` separator to add multiple `SPEAKER ACTION <parameters>` sequences to the command line. **The `:` separator must be surrounded by spaces** to disambiguate from other uses of `:` in sonos actions.

An arbitrary number of commands can be supplied as part of a single `sonos` invocation. If a failure is encountered with any command, `sonos` will terminate and will not execute the remaining commands.

**Example:** `sonos Kitchen volume 25 : Kitchen play`

### Inserting Delays: `wait` and `wait_until`

```
sonos wait <duration>
sonos wait_until <time>
```

The **`wait <duration>`** (or **`wait_for`**) action waits for the specified duration before moving on to the next command. Do not supply a speaker name. This action is useful when, for example, one wants to play audio for a specific period of time, or maintain a speaker grouping for a specific period then ungroup, etc.

`<duration>` can be **one** of seconds, minutes or hours. Floating point values for the duration are acceptable. Examples: `wait 10s`, `wait 30m`, `wait 1.5h`. (If the s/m/h is omitted, `s` (seconds) is assumed.) The time duration formats HH:MM and HH:MM:SS can also be used. Examples are `wait 2:30` (waits 2hrs and 30mins), `wait 0:1:25` (waits 1min 25secs).

The **`wait_until <time>`** action pauses sonos command line execution until the specified time, in 24hr HH:MM or HH:MM:SS format, for example `wait_until 16:30`.

Examples:

- `sonos Bedroom group Study : Study group_volume 50 : Study play : wait 10m : Study stop : Study ungroup`
- `sonos Kitchen play_favourite Jazz24 : wait 30m : Kitchen stop`
- `sonos Bedroom volume 0 : Bedroom play_favourite "Radio 4" : Bedroom ramp 40 : wait 1h : Bedroom ramp 0 : Bedroom stop`

### Waiting Until Playback has Started/Stopped: `wait_start` and `wait_stop`

```
sonos <speaker> wait_start
sonos <speaker> wait_stop
```

The **`<speaker> wait_start`** and **`<speaker> wait_stop`** actions are used to pause execution of the sequence of `sonos` commands until a speaker has either started or stopped playback. For example, to reset the volume back to `25` only after the `Bedroom` speaker has stopped playing, use the following command sequence:

`sonos Bedroom wait_stop : Bedroom volume 25`

Note that if a speaker is already playing, `wait_start` will proceed immediately, and if a speaker is already stopped, `wait_stop` will proceed immediately. If the behaviour you want is to continue **after** the **next** piece of audio ends, then you can chain commands as shown in the following example:

`sonos <speaker> wait_start : <speaker> wait_stop : <speaker> vol 50`

### The `wait_stopped_for <duration>` Action

```
sonos <speaker> wait_stopped_for <duration>
```

The **`<speaker> wait_stopped_for <duration>`** (or **`wsf`**) action will wait until a speaker has stopped playback for `<duration>` (which uses the same time parameter formats as the `wait` action). If the speaker stops playback, but then restarts (any number of times) during `<duration>`, the timer will be reset to zero each time. Processing continues once the speaker has been stopped for a continuous period equalling the `<duration>`.

This function is useful if one wants to perform an action on a speaker (such as ungrouping it) only once its use has definitely stopped, as opposed to it just being temporarily paused, or stopped while switched to a different audio source. For example:

```
sonos Study wait_stopped_for 5m : Study line_in on : Study play
```

### Repeating Commands: The `loop` Actions

```
loop
loop <iterations>
loop_for <duration>
loop_until <time>
loop_to_start
```

The **`loop`** action loops back to the beginning of a sequence of commands and executes the sequence again. Do not supply a speaker name. In the absence of errors, `loop` will continue indefinitely until manually stopped.

To loop a specific number of times, use **`loop <iterations>`**, giving an integer number of iterations to perform before command processing continues. The number of iterations includes the one just performed, i.e., in the sequence `sonos <speaker> vol 25: wait 1h : loop 2`, the commands preceding the `loop 2` action will be performed twice in total.

To loop for a specific period of time, use **`loop_for <duration>`**, where the format for `<duration>` follows the same rules as `wait`. Note that timer starts from the point when the `loop` statement is reached, not from the overall start of command execution.

To loop until a specific time, use **`loop_until <time>`**, where the format for `<time>` follows the same rules as `wait_until`.

Multiple `loop` statements can be used in `sonos` command sequence. For any given `loop` statement, command execution returns to the command immediately after the most recent `loop`, i.e., the loop executes the commands between the current `loop` action and the previous one.  Note that `loop 1` can be considered a null loop action, and can be useful in restricting the scope of a subsequent `loop` action.

The **`loop_to_start`** action will loop back to the very start of a command sequence. It takes no parameters.

Examples:

```
sonos Study wait_start : Study wait_stopped_for 10m : Study volume 25 : loop
sonos wait_until 22:00 : Bedroom play_fav "Radio 4" : Bedroom sleep 30m : loop 3
sonos Bedroom play_fav Jazz24 : Bedroom sleep 30m : wait 1h : loop_for 3h
sonos wait_until 08:00 : Kitchen play_fav "World Service" : Kitchen sleep 10m : wait 1h : loop_until 12:01
```

## Conditional Command Execution

```
sonos <speaker> if_stopped <action> <parameters>
sonos <speaker> if_playing <action> <parameters>
```

The `if_stopped` modifier will execute the action that follows it only if the speaker is not currently playing. If the speaker is playing, the action will be skipped, and the next command in the sequence (if applicable) will be executed immediately. For example, to set the volume of a speaker back to a default value only if the speaker is not playing, use:

`sonos <speaker> if_stopped volume 25`

No action will be taken if the speaker is playing, and the command will terminate immediately.

Similarly, the `if_playing` modifier will execute the action that follows it only if the speaker is currently playing.

## Alternative Discovery

By default, SoCo-CLI uses the speaker discovery mechanisms in SoCo, which uses the native Sonos SSDP multicast process to discover Sonos devices, and then to look up speakers by their name.

SoCo-CLI also provides an alternative discovery process, which works by scanning the network(s) to which your device is attached, and generating and saving a list of Sonos speaker names and other speaker information.

There are three reasons why you might want to use this alternative mechanism:

1. On some networks, particularly when using WiFi, multicast forwarding does not work properly. This blocks normal SoCo speaker discovery.

2. If there are two Sonos systems on the same network, for example when there is a 'split' S1/S2 system, normal SoCo discovery will find only one of the systems (randomly), which may not be the system that includes the speaker to be controlled. In this case, discovery will fail.

3. It's often faster and more convenient to use the local cached speaker list. For example, in terms of convenience, speaker name matches can be case insensitive and can match on substrings.

The disadvantage of using the alternative discovery mechanism is that the speaker list can become stale, requiring a manual refresh.

Note that it's always possible to avoid any kind of discovery step simply by using a speaker's IP address directly.

### Usage

To use this discovery mechanism with `sonos`, use the `--use-local-speaker-list` or `-l` flag. The first time this flag is used, the discovery process will be initiated. This will take a few seconds to complete, after which the `sonos` command will execute. A local speaker list is stored in `<your_home_directory>/.soco-cli/` for use with future invocations of the `sonos` command.

**Example:** `sonos -l "living room" volume 50` uses the local speaker database to look up the "living room" speaker.

When executing a sequence of commands, supply the `-l` option only for the first speaker and it will be used for all speaker lookups, e.g.:
 
 `sonos -l kitchen wait_stop : kitchen vol 25 : study play_favourite "Radio 4"`

### Speaker Naming

When using the local speaker list, speaker naming does not need to be exact, unlike when using standard discovery. Matching is case insensitive, and matching works on substrings. For example, if you have a speaker named `Front Reception`, then `"front reception"` or just `front` will match. (Be careful not to submit ambiguously matchable speaker names; the first hit will be matched, and may not be the speaker you intend.)

Note that if you have speakers with the same names in multiple Sonos systems (Households), you will get inconsistent name matches. It's best to keep speaker names unique within a network (or fall back on using IP addresses instead of speaker names).

### Refreshing the Local Speaker List

If your speakers change in some way (e.g., they are renamed, are assigned different IP addresses, or you add/remove speakers), you can refresh the discovery cache using the `--refresh-speaker-list` or `-r` option. Note that this option only has an effect when combined with the `-l` option. You can also use the `sonos-discover` command (below).

**Example:** `sonos -lr "living room" volume 50` will refresh the discovery cache before executing the `sonos` command.

### Discovery Options

The following flags can be used to adjust network discovery behaviour if the discovery process is failing:

- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network. The default is 128.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). The default is 2.0s.

These options only have an effect when combined with the `-l` **and** `-r` options.

**Example:** `sonos -lr -t 256 -n 1.0 "living room" volume 50`

### The `sonos-discover` Command

**`sonos-discover`** is a standalone utility for creating/updating the local speaker cache, and for seeing the results of the discovery process. It's an alternative to using the `sonos -r` command. It accepts the same `-t`, `-n` and `-m` options as the `sonos` command. 

**Example:** `sonos-discover -t 256 -n 1.0 -m 24` will run `sonos-discover` with a maximum of 256 threads, a network timeout of 1.0s, a minimum netmask of 24 bits, and will print the result.

### Options for the `sonos-discover` Command

Without options, `sonos-discover` will execute the discovery process and print out its results. It will create a speaker cache file, or replace it if already present.

Other options:

- **`--print, -p`**: Print the the current contents of the speaker cache file
- **`--delete-local-speaker-cache, -d`**: Delete the local speaker cache file.
- **`--network_discovery_threads, -t`**: The maximum number of parallel threads used to scan the local network.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). Use this if `sonos-discover` is not finding all of your Sonos devices.
- **`--min_netmask, -m`**: The minimum netmask to use when scanning networks. Used to constrain the IP search space.
- **`--version, -v`**: Print the versions of SoCo-CLI and SoCo, and exit.
- **`--docs`**: Print the URL of this README documentation, for the version of SoCo-CLI being used.
- **`--log <level>`**: Turn on logging. Available levels are NONE (default), CRITICAL, ERROR, WARN, INFO, DEBUG, in order of increasing verbosity.

## Known Issues

Please report any problems you find using GitHub Issues [3].

## Uninstalling

- Use the normal Pip approach to uninstall the SoCo-CLI package: `pip uninstall soco-cli`. 
- You may also need to remove the directory `.soco-cli` and its contents from your home directory.

## Acknowledgments

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.

## Resources

[1] https://github.com/SoCo/SoCo \
[2] https://pypi.org/project/soco-cli \
[3] https://github.com/avantrec/soco-cli/issues
