# SoCo-CLI: Control Sonos from the Command Line

<!--ts-->
* [SoCo-CLI: Control Sonos from the Command Line](#soco-cli-control-sonos-from-the-command-line)
   * [Overview](#overview)
   * [Supported Environments](#supported-environments)
   * [Installation](#installation)
   * [User Guide](#user-guide)
      * [The sonos Command](#the-sonos-command)
      * [Speaker Discovery by Name](#speaker-discovery-by-name)
      * [Simple Usage Examples](#simple-usage-examples)
      * [The SPKR Environment Variable](#the-spkr-environment-variable)
      * [Using Shell Aliases](#using-shell-aliases)
      * [Options for the sonos Command](#options-for-the-sonos-command)
      * [Firewall Rules](#firewall-rules)
      * [Operating on All Speakers: Using _all_](#operating-on-all-speakers-using-_all_)
      * [Redirection of Actions to Coordinator Devices](#redirection-of-actions-to-coordinator-devices)
   * [Guidelines on Playing Content](#guidelines-on-playing-content)
      * [Radio Stations](#radio-stations)
      * [Single Tracks](#single-tracks)
      * [Albums and Playlists](#albums-and-playlists)
      * [Audio Files on the Local Filesystem](#audio-files-on-the-local-filesystem)
      * [Local Playlists (M3U Files)](#local-playlists-m3u-files)
      * [Directories of Audio Files](#directories-of-audio-files)
      * [Spotify, Tidal, Deezer, and Apple Music Share Links](#spotify-tidal-deezer-and-apple-music-share-links)
   * [Complete List of Available Actions](#complete-list-of-available-actions)
      * [Volume and EQ Control](#volume-and-eq-control)
      * [Playback Control](#playback-control)
      * [Queue Actions](#queue-actions)
      * [Favourites and Playlists](#favourites-and-playlists)
      * [TuneIn Radio Station Favourites](#tunein-radio-station-favourites)
      * [Grouping and Stereo Pairing](#grouping-and-stereo-pairing)
      * [Alarms](#alarms)
      * [Music Library Search Functions](#music-library-search-functions)
      * [Speaker and Sonos System Information](#speaker-and-sonos-system-information)
   * [Multiple Sequential Commands](#multiple-sequential-commands)
      * [Chaining Commands Using the : Separator](#chaining-commands-using-the--separator)
      * [Inserting Delays: wait and wait_until](#inserting-delays-wait-and-wait_until)
      * [Waiting Until Playback has Started/Stopped: wait_start, wait_stop and wait_end_track](#waiting-until-playback-has-startedstopped-wait_start-wait_stop-and-wait_end_track)
      * [The wait_stopped_for &lt;duration&gt; Action](#the-wait_stopped_for-duration-action)
      * [Repeating Commands: The loop Actions](#repeating-commands-the-loop-actions)
   * [Conditional Command Execution](#conditional-command-execution)
   * [Interactive Shell Mode](#interactive-shell-mode)
      * [Description](#description)
      * [Usage](#usage)
      * [Shell History and Auto-Completion](#shell-history-and-auto-completion)
      * [Shell Aliases](#shell-aliases)
         * [Push and Pop](#push-and-pop)
         * [Alias Subroutines](#alias-subroutines)
         * [Alias Arguments](#alias-arguments)
         * [Saving and Loading Aliases](#saving-and-loading-aliases)
      * [Single Keystroke Mode](#single-keystroke-mode)
   * [Cached Discovery](#cached-discovery)
      * [Usage](#usage-1)
      * [Speaker Naming](#speaker-naming)
      * [Refreshing the Local Speaker List](#refreshing-the-local-speaker-list)
      * [Discovery Options](#discovery-options)
      * [The sonos-discover Command](#the-sonos-discover-command)
      * [Options for the sonos-discover Command](#options-for-the-sonos-discover-command)
   * [The SoCo-CLI HTTP API Server](#the-soco-cli-http-api-server)
      * [Server Usage](#server-usage)
      * [Using the Local Speaker Cache](#using-the-local-speaker-cache)
      * [HTTP Request Structure](#http-request-structure)
      * [Return Values](#return-values)
      * [Asynchronous Actions](#asynchronous-actions)
      * [Macros: Defining Custom HTTP API Server Actions](#macros-defining-custom-http-api-server-actions)
         * [Macro Definition and Usage](#macro-definition-and-usage)
         * [Macro Arguments](#macro-arguments)
         * [Using the Generic Macro](#using-the-generic-macro)
         * [Troubleshooting](#troubleshooting)
         * [Specifying the Macro Definition File](#specifying-the-macro-definition-file)
         * [Reloading the Macro Definition File](#reloading-the-macro-definition-file)
         * [Return Values](#return-values-1)
         * [Listing Macros](#listing-macros)
      * [Listing Speakers](#listing-speakers)
      * [Rediscovering Speakers](#rediscovering-speakers)
      * [Inspecting the HTTP API](#inspecting-the-http-api)
   * [Using SoCo-CLI as a Python Library](#using-soco-cli-as-a-python-library)
      * [Importing the API](#importing-the-api)
      * [Using the API](#using-the-api)
      * [Convenience Functions](#convenience-functions)
   * [Known Issues](#known-issues)
   * [Uninstalling](#uninstalling)
   * [Acknowledgments](#acknowledgments)
   * [Resources](#resources)

<!-- Created by https://github.com/ekalinin/github-markdown-toc -->
<!-- Added by: pwt, at: Mon May 13 16:02:37 BST 2024 -->

<!--te-->

## Overview

SoCo-CLI is a powerful command line wrapper for the popular Python SoCo library [1], for controlling Sonos systems. SoCo-CLI is written entirely in Python and is portable across platforms.

A simple `sonos` command provides easy control over a huge range of speaker functions, including playback, volume, groups, EQ settings, sleep timers, alarms, speaker settings, the playback queue, etc. Multiple commands can be run in sequence, including the ability to insert delays between commands, to wait for speakers to stop or start playing, and to create repeated action sequences using loops. Audio files from the local filesystem can be played directly on Sonos.

SoCo-CLI has an orderly command structure and consistent return values, making it suitable for use in automated scripts, `cron` jobs, etc.

For interactive command line use, SoCo-CLI provides a powerful [Interactive Shell Mode](#interactive-shell-mode) that improves speed of operation and reduces typing.

SoCo-CLI can be imported as a streamlined, high-level [API](#using-soco-cli-as-a-python-library) library by other Python programs, and acts as an intermediate abstraction layer between the client program and the underlying SoCo library, simplifying the use of SoCo.

SoCo-CLI can also run as a simple [HTTP API server](#the-soco-cli-http-api-server), providing access to a huge range of actions via simple HTTP requests. (Requires Python 3.7 or above.)

## Supported Environments

- Requires Python 3.5+
  - For Python 3.5, the latest compatible version of the underlying SoCo library is v0.27.1. Python 3.6 and above supports the latest version of the SoCo library.
  - The HTTP API Server functionality requires Python 3.7 or above.
- Should run on all platforms supported by Python. Tested on various versions of Linux, macOS and Windows.
- Works with Sonos 'S1' and 'S2' systems, as well as split S1/S2 systems.

## Installation

Install the latest version from PyPI [2] using **`pip install -U soco-cli`**.

Soco-CLI can also be easily installed as a self-contained application with [**pipx**](https://pypa.github.io/pipx/) using **`pipx install soco-cli`**.

Please see the CHANGELOG.txt file for a list of the user-facing changes in each release.

## User Guide

### The `sonos` Command

The installer adds the `sonos` command to the PATH. If the `sonos` command is not found, make sure your `PATH` is set up correctly for the Python installation you want to use.

All commands have the form:

```
sonos SPEAKER ACTION <parameters>
```

- `SPEAKER` identifies the speaker to operate on, and can be the speaker's Sonos Room (Zone) name or its IPv4 address in dotted decimal format. Partial, case-insensitive speaker names will be matched, e.g., `kit` will match `Kitchen`. Partial matches must be unambiguous, or an error is returned.
- `ACTION` is the operation to perform on the speaker. It can take zero or more parameters depending on the action.

As usual, command line arguments containing spaces must be surrounded by quotes: double quotes work on all supported OS platforms, while Linux and macOS also support single quotes.

The `soco` command is also added to the PATH, and can be used as an alias for the `sonos` command if preferred.

Actions that make changes to speakers do not generally provide return values. Instead, the program exit code can be inspected to test for successful operation (exit code 0). If an error is encountered, an error message will be printed to `stderr`, and the program will return a non-zero exit code. Note that `sonos` actions are executed without seeking user confirmation; please bear this in mind when manipulating the queue, playlists, etc.

### Speaker Discovery by Name

SoCo-CLI will try a number of approaches to find a speaker's IP address by speaker name, which escalate in cost until the speaker is discovered or discovery fails. If SoCo-CLI seems slow to find speakers (especially if you have a multi-household Sonos system), or if you occasionally experience problems with speakers not being found, please take a look at the generally faster [Cached Discovery](#cached-discovery) method.

### Simple Usage Examples

- **`sonos "Living Room" volume`** Returns the current volume setting of the *Living Room* speaker.
- **`sonos Study volume 25`** Sets the volume of the *Study* speaker to 25.
- **`sonos Study group Kitchen`** Groups the *Study* speaker with the *Kitchen* speaker.
- **`sonos 192.168.0.10 mute`** Returns the mute state ('on' or 'off') of the speaker at the given IP address.
- **`sonos 192.168.0.10 mute on`** Mutes the speaker at the given IP address.
- **`sonos Kitchen play_favourite Jazz24 : wait 30m : Kitchen stop`** Plays 'Jazz24' for 30 minutes, then stops playback.
- **`sonos Study play_file "Zoo Station.mp3"`** Plays a local audio file.

### The `SPKR` Environment Variable

To avoid typing the speaker name, or to parameterise the use of SoCo-CLI commands, it's possible to use the `SPKR` environment variable instead of supplying the speaker name (or IP address) on the command line.

**Example:** The following will set up all sonos commands to operate on the "Front Reception" speaker:

Linux and macOS:

```
$ export SPKR="Front Reception"
$ sonos play
$ sonos wait_stop : volume 10
```

Windows:

```
C:\ set SPKR="Front Reception"
C:\ sonos play
C:\ sonos wait_stop : volume 10
```

IP addresses also work, e.g.: `$ export SPKR=192.168.0.50`.

If you want to ignore the `SPKR` environment variable for a specific `sonos` invocation, use the `--no-env` command line option.

### Using Shell Aliases

If your shell supports it, shell aliasing can be very convenient in creating shortcuts to SoCo-CLI commands. For example, I have the following in my `.zshrc` file:

```
# Sonos Aliases
alias s="sonos"
alias sk="sonos Kitchen"
alias sr="sonos 'Rear Reception'"
alias sf="sonos 'Front Reception'"
alias sm="sonos Move"
alias sb="sonos Bedroom"
alias sb2="sonos 'Bedroom 2'"
alias ss="sonos Study"
alias sd="sonos-discover"
```

This allows the use of shorthand like `sk stop`, to stop playback on the Kitchen speaker. Note, however, that this won't work with sequences of commands using a single `sonos` invocation, separated with ` : ` (see [Multiple Sequential Commands](#multiple-sequential-commands)), only for the first command in such a sequence. (Normal, mutiple `sonos` invocation, shell sequences using `;` or `&&` as separators will work, of course.)

### Options for the `sonos` Command

- **`--version, -v`**: Print the versions of SoCo-CLI, SoCo, and Python.
- **`--check_for_update`**: Check for a more recent version of SoCo-CLI.
- **`--actions`**: Print the list of available actions.
- **`--docs`**: Print the URL of this README documentation, for the version of SoCo-CLI being used.
- **`--log <level>`**: Turn on logging. Available levels are `NONE` (default), `CRITICAL`, `ERROR`, `WARN`, `INFO`, `DEBUG`, in order of increasing verbosity. `INFO` level logging tends to be the most useful when troubleshooting SoCo-CLI issues.

The following options are for use with the cached discovery mechanism:

- **`--use-local-speaker-list, -l`**: Use the local speaker list instead of SoCo discovery. The speaker list will first be created and saved if it doesn't already exist.
- **`--refresh-local-speaker-list, -r`**: In conjunction with the `-l` option, the speaker list will be regenerated and saved.
- **`--network_discovery_threads, -t`**: The maximum number of parallel threads used to scan the local network.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up).
- **`--min_netmask, -m`**: The minimum netmask to use when scanning networks. Used to constrain the IP search space.

Note that the `sonos-discover` utility (discussed below) can also be used to manage the local speaker list. This is the recommended way of using cached discovery: first run `sonos-discover` to create the local speaker database, then use `sonos` with the `-l` option to use the local database when invoking `sonos` actions.

If you set the environment variable **`USE_LOCAL_CACHE=TRUE`**, the `--use_local_speaker_list` option will always be used.

### Firewall Rules

If you're running on a host with its firewall enabled, note that some SoCo-CLI actions require the following incoming ports to be open: **TCP 1400-1499**, **TCP 54000-54099**.

The TCP/1400 range is used to receive notification events from Sonos players (used in the `wait_stop` action, etc.), the TCP/54000 range is used for the built-in Python HTTP server when playing files from the local filesystem (used in the `play_file` action).

When opening ports, SoCo-CLI will try port numbers starting at the beginning of the range and incrementing by one until a free port is found, up to the limit of the range. This allows multiple invocations of SoCo-CLI to run in parallel on the same host.

The standard speaker discovery mechanism uses SSDP multicast (multicast address 239.255.255.250 on UDP port 1900). The outgoing port chosen for the multicast request is variable and OS-dependent, e.g., for most Linux distributions it's in the ephemeral port range 32768–60999. Multicast responses are returned to the outgoing port, so if the firewall blocks incoming UDP traffic on the relevant port range, then standard discovery will fail. SoCo-CLI will automatically fall back to using network scan discovery if standard discovery fails, but this is slower, so either adjust your firewall to open the relevant ports or consider using SoCo-CLI [Cached Discovery](#cached-discovery).

If using the HTTP API Server functionality, its listen port must be open to incoming TCP requests. The default port is 8000.

### Operating on All Speakers: Using `_all_`

There is a limited set of operations where it can be desirable to operate on all speakers, e.g., muting every speaker in the house. This is done by using **`_all_`** as the speaker name. Operations will be performed on all visible devices.

**Examples**: `sonos _all_ mute on` and `sonos _all_ relative_volume -10`.

Note that `_all_` can be used with every `sonos` operation: no checking is performed to ensure that the use of `all` is appropriate, so use with caution.

### Redirection of Actions to Coordinator Devices

If an action is applied to a non-coordinator device, there are some cases where the action is automatically redirected to the coordinator. For example, if `lounge` is the coordinator speaker and `kitchen` is a grouped speaker:

- `sonos kitchen queue` will be redirected to the `lounge` speaker, because that's the queue in use
- `sonos kitchen volume 40` will remain directed to the `kitchen` speaker

## Guidelines on Playing Content

SoCo-CLI enables playback of content from the **Sonos Favourites** and **Sonos Playlists** collections, from **local libraries**, and from the **TuneIn 'My Radio Stations'** list. It also allows playback of **audio files from the local filesystem**, and can add **sharelinks** from the Spotify, Tidal, Apple Music, and Deezer music services to the Sonos queue. On macOS, the contents of physical CDs can be played direct to Sonos.

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
sonos <speaker_name> play_from_queue last_added
```

To add imported playlists from local libraries to the queue, use the `add_library_playlist_to_queue` action.

Albums from local music libraries can also be added to the queue using `sonos <speaker> queue_album <album_name>`. The action returns the queue position of the first track in the album, which can then be played as in the example above:

### Audio Files on the Local Filesystem

It's possible to play local audio files in **MP3, M4A, MP4, FLAC, OGG, WMA, WAV, and AIFF** formats directly on your Sonos speakers using the `play_file` (or `play_local_file`) action.

**Example**: `sonos Lounge play_file mozart.mp3`

SoCo-CLI establishes a temporary internal HTTP server from which the specified audio file can be streamed, and then instructs the speaker to play it. The `play_file` action will terminate once playback stops. Note that playback can be paused using a Sonos app (or SoCo-CLI), and the HTTP server will remain active so that playback can be resumed.

Unfortunately, one can pause but not fully stop playback when using the Sonos apps. Hence, stop playback by playing something else on Sonos, by issuing a 'CTRL-C' to the active `play_file` action, or by issuing `sonos <SPEAKER> stop` from another command line. Alternatively, use the `_end_on_pause_` option to terminate the `play_file` action if playback is paused.

The host running SoCo-CLI must remain on and connected to the network during playback, in order to serve the file to the speaker. The internal HTTP server is active only for the duration of the `play_file` action. For security reasons, it will only serve the specified audio file, and only to the IP addresses of the Sonos speakers in the system.

Multiple files can be played in sequence by providing multiple audio file names as parameters.

**Example**: `sonos Lounge play_file one.mp3 two.mp3 three.mp3`

### Local Playlists (M3U Files)

The `play_m3u` (or `play_local_m3u`) action will play a local filesystem playlist in M3U (or M3U8) format. Files in the playlist should be available on the local filesystem; any that are not will be skipped. Simple lists of audio files in non-M3U format can also be supplied. Comments can be inserted in the file by prefixing each comment line with `#`.

There are options to print the track filenames as they are played, to shuffle the playlist, and to select a single random track from the playlist. There is also an **interactive mode** option, which allows (N)ext track, (P)ause playback, and (R)esume playback, while the playlist is being played.

**Example**: `sonos Lounge play_m3u my_playlist.m3u`, or, to print filenames and invoke interactive mode: `sonos Lounge play_m3u my_playlist.m3u pi`.

This feature works by invoking the `play_file` action for each file in the playlist in sequence, so the same rules apply as for `play_file`. Note that `play_m3u` does not create a Sonos queue on the speaker -- the 'queue' is managed locally by SoCo-CLI -- so it's not possible to skip forward or back using a Sonos app.

### Directories of Audio Files

To play every audio file in a local directory, use the `play_directory` (or `play_dir`) action. As with the `play_m3u` action this invokes `play_file` for each valid audio file in the directory. It does not traverse into subdirectories. 

**Example**: `sonos Lounge play_directory "Music/Mozart/The Magic Flute/CD 1"`

On macOS (but not on Windows or Linux), if you have an attached CD drive, this action can be used to play a CD directly to your Sonos speakers, e.g.: 

`sonos Lounge play_dir "/Volumes/Audio CD"`.

The `play_file` action can be used to play individual tracks on the CD, e.g.:

`sonos Lounge play_file "/Volumes/Audio CD/1 Audio Track.aiff"`.

### Spotify, Tidal, Deezer, and Apple Music Share Links

The `add_sharelink_to_queue` (or `sharelink`) action can be used to add share links from Spotify, Tidal, Deezer, or Apple Music to the queue, provided the Sonos system has a subscription to the required service.

Links can refer to tracks, albums, or playlists. The position of the first track added to the queue is returned, which can then be played using `play_from_queue`. Share links can be of the form:

- `https://open.spotify.com/track/6cpcorzV5cmVjBsuAXq4wD`
- `spotify:album:6wiUBliPe76YAVpNEdidpY`
- `https://tidal.com/browse/album/157273956`
- `https://www.deezer.com/en/playlist/5390258182`
- `https://music.apple.com/dk/album/black-velvet/217502930?i=217503142`

**Example**:
```
sonos Kitchen sharelink "https://open.spotify.com/track/6cpcorzV5cmVjBsuAXq4wD"
5 <-- Returns queue position of first track
sonos Kitchen play_from_queue 5
```

## Complete List of Available Actions

### Volume and EQ Control

- **`balance`**: Returns the balance setting of the speaker as a value between -100 and +100, where -100 is left channel only, 0 is left and right set to the same volume, and +100 is right channel only.
- **`balance <balance_setting>`**: Sets the balance of the speaker to a value between -100 and +100, where -100 is left channel only, 0 is left and right set to the same volume, and +100 is right channel only. Intermediate values produce a mix of right/left channels.
- **`bass`**: Returns the bass setting of the speaker, from -10 to 10.
- **`bass <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`dialog_mode`** (or **`dialog`**, **`dialogue_mode`**, **`dialogue`**): Returns the dialog mode setting of the speaker, 'on' or 'off' (if applicable).
- **`dialog_mode <on|off>`** (or **`dialog`**, **`dialogue_mode`**, **`dialogue`**): Sets the dialog mode setting of the speaker to 'on' of 'off' (if applicable).
- **`fixed_volume`**: Returns whether the speaker's Fixed Volume feature is enabled, 'on' or 'off'. (Applies to Sonos Connect and Port devices only.)
- **`fixed_volume <on|off>`**: Sets whether the speaker's Fixed Volume feature is enabled.   
- **`group_mute`**: Returns the group mute state of a group of speakers, 'on' or 'off'.
- **`group_mute <on|off>`**: Sets the group mute state of a group of speakers to 'on' or 'off'.
- **`group_relative_volume <adjustment>` (or `group_rel_vol`, `grv`)**: Raises or lowers the group volume by `<adjustment>` which must be a number from -100 to 100.
- **`group_volume` (or `group_vol`)**: Returns the current group volume setting of the speaker's group (0 to 100).
- **`group_volume <volume>` (or `group_vol`)**: Sets the group volume of the speaker's group to `<volume>` (0 to 100). This action operates in the same way as the group volume slider in the Sonos apps. The volume applied to each speaker in the group is scaled by the speaker's current volume.
- **`group_volume_equalize <volume>` (or `group_volume_equalise`, `gve`)**: Sets the volume of all speakers in a group to the same absolute `<volume>` (0-100).
- **`loudness`**: Returns the loudness setting of the speaker, 'on' or 'off'.
- **`loudness <on|off>`**: Sets the loudness setting of the speaker to 'on' or 'off'.
- **`mute`**: Returns the mute setting of the speaker, 'on' or 'off'.
- **`mute <on|off>`**: Sets the mute setting of the speaker to 'on' or 'off'.
- **`night_mode`** (or **`night`**): Returns the night mode setting of the speaker, 'on' or 'off' (if applicable).
- **`night_mode <on|off>`** (or **`night`**): Sets the night mode setting of the speaker to 'on' or 'off' (if applicable).
- **`playing_tv`** (or **`is_playing_tv`**): Returns whether the speaker is currently playing from its TV input source, 'yes' or 'no'.
- **`ramp_to_volume <volume>` (or `ramp`)**: Gently raise or reduce the volume to `<volume>`, which is between 0 and 100. Returns the number of seconds to complete the ramp.
- **`relative_bass <adjustment>` (or `rel_bass`, `rb`)** Increase or reduce the bass setting by `<adjustment>`, a value between -10 and 10.
- **`relative_sub_gain <adjustment>` (or `rel_sub_gain`, `rsg`)** Increase or reduce a Sub's gain setting by `<adjustment>`, a value between -15 and 15.
- **`relative_treble <adjustment>` (or `rel_treble`, `rt`)** Increase or reduce the treble setting by `<adjustment>`, a value between -10 and 10.
- **`relative_volume <adjustment>` (or `rel_vol`, `rv`)**: Raises or lowers the volume by `<adjustment>`, which must be a number from -100 to 100.
- **`sub_enabled`**: Returns `on` if the zone's subwoofer is enabled, otherwise `off`.
- **`sub_enabled <on|off>`**: Enables or disables a zone's subwoofer.
- **`sub_gain`**: Reports the value of a Sub's gain (for speaker groups with a bonded Sub), from `-15` to `+15`.
- **`sub_gain <gain>`**: Sets the value of a Sub's gain, from `-15` to `+15`.
- **`surround_enabled`**: Returns `on` if the zone's surround speakers are enabled, otherwise `off`.
- **`surround_enabled <on|off>`**: Enables or disables a zone's surround speakers.
- **`surround_full_volume_enabled`**: Reports whether surround speakers are in full volume mode (on) or ambient mode (off).
- **`surround_full_volume_enabled <on|off>`**: Sets surround speakers to full volume mode (on) or ambient mode (off).
- **`surround_volume_music`**: Reports the value of the volume level for surround speakers, when playing music sources, from `-15` to `+15`.
- **`surround_volume_music <level>`**: Sets the value of the volume level for surround speakers, when playing music sources, from `-15` to `+15`.
- **`surround_volume_tv`**: Reports the value of the volume level for surround speakers, when playing TV sources, from `-15` to `+15`.
- **`surround_volume_tv <level>`**: Sets the value of the volume level for surround speakers, when playing TV sources, from `-15` to `+15`.
- **`treble`**: Returns the treble setting of the speaker, from -10 to 10.
- **`treble <number>`**: Sets the bass setting of the speaker to `<number>`. Values must be between -10 and 10.
- **`trueplay`**: Returns whether a speaker's Trueplay profile is enabled, 'on' or 'off'.
- **`trueplay <on|off>`**: Sets whether a speaker's Trueplay profile is enabled. Can only be set to 'on' for speakers that have a current Trueplay tuning profile available.
- **`volume` (or `vol`)**: Returns the current volume setting of the speaker (0 to 100)
- **`volume <volume>` (or `vol`)**: Sets the volume of the speaker to `<volume>` (0 to 100).

### Playback Control

- **`album_art`**: Return a URL to the album art for the current stream, if there's one available.
- **`cross_fade`** (or **`crossfade`, `fade`**): Returns the cross fade setting of the speaker, 'on' or 'off'.
- **`cross_fade <on|off>`** (or **`crossfade`, `fade`**): Sets the cross fade setting of the speaker to 'on' or 'off'.
- **`cue_line_in <on | line_in_speaker | left_input, right_input | line_in_speaker right_input>`**: This functions in the same way as the `line_in` action below, but does not automatically start playback (and will stop playback if the speaker is currently playing from the selected Line In input). Can be used without supplying the `on` parameter.
- **`end_session`**: Ends a third-party controlled session, e.g. Spotify Connect.
- **`get_channel`** (or **`channel`**): Get the channel name of the current radio stream, if available.
- **`get_uri`**: Get the URI of the current track or stream. (Note: the output format is subject to change.)  
- **`line_in`**: Returns a speaker's Line-In state, 'on' if its input is set to a Line-In source, 'off' otherwise, plus the current playback state (e.g., `on (PAUSED_PLAYBACK)`).
- **`line_in <on | line_in_speaker | left_input, right_input | line_in_speaker right_input>`**: Switch a speaker to a Line-In input. Playback is started automatically. A speaker can be switched to its own Line-In input (`<on>`), **or** the Line-In input of another `<line_in_speaker>` (if applicable). For the case where there is a stereo pair of Play:5 or Five speakers, the left hand speaker's Line-In source is selected using `left_input` (default), and the right-hand speaker's Line-In input is selected using `right_input`. (Complicated example: `sonos Bedroom line_in Lounge right_input`, switches the Bedroom to the right-hand input of the stereo pair in the Lounge, and starts playback.)
- **`next`**: Move to the next track (if applicable for the current audio source).
- **`pause`**: Pause playback (if applicable for the audio source).
- **`pause_all`**: Pause playback on all speakers in the system. (Note: only pauses speakers that are in the same Sonos Household.)
- **`pauseplay`** (or **`playpause`**): Inverts a playing/paused state: if a speaker is currently playing, it will be paused or stopped; if a speaker is paused or stopped, playback will be started.
- **`play`** (or **`start`**): Start playback.
- **`play_directory <directory_name> <options>`** (or **`play_dir`**): Play all of the audio files in the specified local directory. Takes the same `<options>` as the `play_m3u` action. Does not traverse into subdirectories.
- **`play_file <filename> ...`** (or **`play_local_file`**): Play MP3, M4A, MP4, FLAC, OGG, WMA, WAV, or AIFF audio files from your computer. Multiple filenames can be provided and will be played in sequence. To configure termination of the command if playback is paused (as well as stopped), add `_end_on_pause_` to the command, i.e.: `play_file filename _end_on_pause_`.
- **`play_from_queue <track>`** (or **`play_queue`, `pfq`, `pq`**): Play track number `<track>` from the queue. Tracks begin at 1. If `<track>` is omitted, the first item in the queue is played.
- **`play_m3u <m3u_file> <options>`** (or **`play_local_m3u`**): Plays a local M3U/M3U8 playlist consisting of local audio files (in supported audio formats). Can be followed by options `p` to print each filename before it plays, and/or `s` to shuffle the playlist, or `r` to play a single, random track from the playlist. (If using multiple options, concatenate them: e.g., `ps`.) Example: `sonos Study play_m3u my_playlist.m3u ps`. Add the `i` option to invoke **interactive** mode, which allows use of the keyboard to go to the (N)ext track, to (P)ause, or to (R)esume playback.
- **`play_mode` (or `mode`)**: Returns the play mode of the speaker, one of `NORMAL`, `REPEAT_ONE`, `REPEAT_ALL`, `SHUFFLE`, `SHUFFLE_REPEAT_ONE`, or `SHUFFLE_NOREPEAT`.
- **`play_mode <mode>` (or `mode`)**: Sets the play mode of the speaker to `<mode>`, which is one of the values above.
- **`play_sharelink <sharelink>`**: Adds a sharelink to the end of the queue and starts playback.
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
- **`stop_all`**: Stop playback on all speakers in the system. (Note: only stops speakers that are in the same Sonos Household.)
- **`switch_to_tv`**: Switches to the TV input. Only applicable to soundbars and the Sonos Amp.
- **`track`**: Return information about the currently playing track.
- **`track_follow`** (or **`tf`**): Returns information about the currently playing track, and each subsequent track when the track changes. This action keeps running until cancelled using CTRL-C.
- **`track_follow_compact`** (or **`tfc`**): As `track_follow`, but with a more compact single line representation for each track.
- **`tv_audio_delay`**: Returns the current setting for the audio delay for TV sources, an integer from 0 to 5. (Sonos does not specify the units used for adjustment.) Only applicable to devices with TV inputs.
- **`tv_audio_delay <delay>`**: Sets the audio delay for TV sources; `delay` must be an integer from 0 to 5.

### Queue Actions

When adding items to the queue, the default is to add the items at the end of the queue unless an optional **`<position>`** parameter is supplied, which can take one of the following values:

- An **integer** queue position. If this is <= 0, the position will be set to 1; if greater than the end of the current queue, this will be set to the end of the queue.
- **`start`** or **`first`**: insert at the start of the queue (equivalent to `1`).
- **`play_next`** or **`next`**: Insert at the current queue playback position unless the queue is being used for playback, in which case the item is added directly after the currently playing track, and will play next.
- **`end`** or **`last`**: Insert at the end of the queue -- which is the default if the `position` parameter is not supplied.

Examples:

```shell
sonos lounge queue_search_results all start  <-- 'start' is equivalent to '1'
sonos lounge queue_search_results 1-5,9 next
sonos lounge queue_search_results 1,3,4 end  <-- Note: 'end' can be omitted
sonos kitchen queue_album zooropa next
```

When items are added to the queue successfully, the queue position of the first added track is returned. Use `play_from_queue` with this track number to commence playback of the added items.

The available actions are:

- **`add_playlist_to_queue <playlist_name> [<position>]`** (or **`queue_playlist`, `add_pl_to_queue`, `apq`**): Add `<playlist_name>` to the queue. Name matching is case-insensitive, and will work on partial matches.
- **`add_library_playlist_to_queue <playlist_name> ]<position>]`** (or **`alpq`**): As above, but targets local library imported playlists instead of Sonos playlists.
- **`add_sharelink_to_queue <sharelink> [<position>]`** (or **`sharelink`**): Add a **Spotify**, **Tidal**, **Deezer**, or **Apple Music** link (for a track, album, playlist, etc.) to the queue. Returns the queue position of the first track. Supported links formats are: `https://open.spotify.com/track/6cpcorzV5cmVjBsuAXq4wD`, `spotify:album:6wiUBliPe76YAVpNEdidpY`, `https://tidal.com/browse/album/157273956`, `https://www.deezer.com/en/playlist/5390258182`, `https://music.apple.com/dk/album/black-velvet/217502930?i=217503142`.
- **`add_uri_to_queue <uri> [<position>]`** Adds a URI to the queue.
- **`clear_queue`** (or **`cq`**): Clears the current queue
- **`list_queue`** (or **`lq`, `q`**): List the tracks in the queue
- **`list_queue <track_number>`** (or **`lq`, `q`**): List the track in the queue at position `<track_number>`
- **`play_from_queue <track_number, or 'current', or 'last_added', or 'last', or 'random'>`** (or **`pfq`, `pq`**): Play `<track_number>` from the queue. Track numbers start from 1. If no `<track_number>` is provided, play starts from the beginning of the queue. If `current` is provided, play starts at the current queue position. If `last_added` is provided, play starts from the queue position of the last added track or set of tracks. If `last` is provided, the last track in the queue is played. If `random` is provided, playback will start at a random queue position.
- **`queue_album <album_name> [<position>]`** (or **`qa`**): Add `<album_name>` from the local library to the queue. If multiple (fuzzy) matches are found for the album name, a random match will be chosen.
- **`queue_length`** (or **`ql`**): Return the length of the current queue.
- **`queue_position`** (or **`qp`**): Return the current queue position.
- **`queue_search_results <search_result_numbers> [<position>]`** (or **`qsr`**): Queue one or more items from the list of items returned by the last search performed, at the end of the queue by default. Search result numbers start from 1, and can be supplied as single integers, sequences (e.g., '4,7,3'), ranges (e.g., '5-10'), or 'all' (for all tracks). Note: do not use spaces either side of the commas and dashes. Sequences and ranges can be mixed, e.g., '1,3-6,10'.
- **`queue_track <track_name> [<position>]`** (or **`qt`**): Add `<track_name>` from the local library to the queue. If multiple (fuzzy) matches are found for the track name, a random match will be chosen. Optionally, `next` or `play_next` can be added to insert the track at the next_play position in the queue. The queue position of the track will be returned.
- **`remove_current_track_from_queue` (or `rctfq`)**: Remove from the queue the track at the current queue position. If the track is playing, this will have the effect of stopping playback and starting to play the next track. (If the last track in the queue is playing, playback will stop and the previous track will start to play.)
- **`remove_last_track_from_queue <count>` (or `rltfq`)**: Removes the last `<count>` tracks from the queue. If `<count>` is omitted, the last track is removed.
- **`remove_from_queue <track_number|sequence|range>`** (or **`rfq`, `rq`**): Remove tracks from the queue. Track numbers start from 1, and can be supplied as single integers, sequences (e.g., '4,7,3'), or ranges (e.g., '5-10'). Note: do not use spaces either side of the commas and dashes. Sequences and ranges can be mixed, e.g., '1,3-6,10'.
- **`save_queue <title>`** (or **`sq`, `create_playlist_from_queue`**): Save the current queue as a Sonos playlist called `<title>`.
- **`set_queue_position <track_number>`** (or **`sqp`**): Set the queue position to `track_number`, without commencing playback. Note that this will stop any current audio being played.

The following has issues and requires further development. For example, it's currently possible to add radio stations to the queue!

- **`add_favourite_to_queue <favourite> [<position>]` (or `add_favorite_to_queue`, `add_fav_to_queue`, `afq`)**: Add a Sonos Favourite to the queue. Optionally, `play_next` or `next` can be added to add the favourite as the next track or playlist to be played. Returns the queue position of the favourite.

### Favourites and Playlists

- **`clear_playlist <playlist>`**: Clear the Sonos playlist named `<playlist>`.
- **`create_playlist <playlist>`**: Create a Sonos playlist named `<playlist>`. (See also `save_queue` above).
- **`cue_favourite <favourite_name>`** (or **`cue_favorite`, `cue_fav`, `cf`**): Cues up a Sonos favourite for playback. This is a convenience action that issues the sequence: `mute, play_favourite, stop, unmute`. It's useful for silently setting a speaker to a state where it's ready to play the nominated favourite. Mute and group mute states are preserved. 
- **`delete_playlist <playlist>`** (or **`remove_playlist`**): Delete the Sonos playlist named `<playlist>`.
- **`list_all_playlist_tracks`** (or **`lapt`**): Lists all tracks in all Sonos Playlists.
- **`list_favs`** (or **`list_favorites`, `list_favourites`, `lf`**): Lists all Sonos favourites.
- **`list_library_playlists`** (or **`llp`**): List all local library imported playlists.
- **`list_playlists`** (or **`playlists`, `lp`**): Lists the Sonos playlists.
- **`list_library_playlist_tracks <playlist_name>`** (or **`llpt`**): List the tracks in a local library imported playlist.
- **`list_playlist_tracks <playlist_name>`** (or **`lpt`**): List the tracks in a given Sonos Playlist.
- **`play_favourite <favourite_name>` (or `play_favorite`, `favourite`, `favorite`, `fav`, `pf`, `play_fav`)**: Plays the Sonos favourite identified by `<favourite_name>`. The name is loosely matched; if `<favourite_name>` is a (case insensitive) substring of a Sonos favourite, it will match. In the case of duplicates, the first match encountered will be used. If a queueable item, the favourite will be added to the end of the current queue and played. **Note: this currently works only for certain types of favourite: local library tracks and playlists, radio stations, single Spotify tracks, etc.**
- **`play_favourite_number <number>`** (or **`play_favorite_number`**, **`pfn`**): Play a Sonos favourite by its index number in the list of favourites.  
- **`play_favourite_radio_station <station_name>`** (or **`play_favorite_radio_station`, `pfrs`**): Play a favourite radio station in TuneIn's 'My Stations' list.
- **`remove_from_playlist <playlist_name> <track_number>`** (or **`rfp`**): Remove a track from a Sonos playlist.

### TuneIn Radio Station Favourites

The following operate on the stations in TuneIn's 'My Radio Stations' list.

- **`cue_favourite_radio_station`** (or **`cue_favorite_radio_station`**, **`cfrs`**): Cue a favourite radio station for later playback. This is a convenience action that issues the sequence: `mute, play_favourite_radio_station, stop, unmute`. It's useful for silently setting a speaker to a state where it's ready to play the nominated favourite. Mute and group mute states are preserved.
- **`favourite_radio_stations`** (or **`favorite_radio_stations`**, **`lfrs`**, **`frs`**): List the favourite radio stations.
- **`play_favourite_radio_station <station_name>`** (or **`play_favorite_radio_station`, `pfrs`**): Play a favourite radio station.
- **`play_fav_radio_station_no <station_number>`** (or **`pfrsn`**): Play a favourite radio station by its number.

### Grouping and Stereo Pairing

- **`group <master_speaker>`(or `g`)**: Groups the speaker with `<master_speaker>`, which acts as the coordinator.
- **`multi_group <slave_speaker> [<slave_speaker> ...]`**: Groups one or more speakers with the target speaker, which acts as the coordinator.
- **`pair <right_hand_speaker>`**: Creates a stereo pair, where the target speaker becomes the left-hand speaker of the pair and `<right_hand_speaker>` becomes the right-hand of the pair. Can be used to pair dissimilar Sonos devices (e.g., to stereo-pair a Play:1 with a One). The left-hand speaker becomes the coordinator speaker, and the stereo pair will adopt its name.
- **`party_mode` (or `party`)**: Adds all speakers in the system into a single group. The target speaker becomes the group coordinator. Remove speakers individually using `ungroup`, or use `ungroup_all`.
- **`transfer_playback <target_speaker>` (or `transfer_to`, `transfer`)**: Transfers playback to <target_speaker>. This is achieved by grouping and ungrouping the speakers, and swapping the group coordinator. It's a convenience shortcut for `speaker1 group speaker2 : speaker1 ungroup`.
- **`ungroup` (or `ug`, `u`)**: Removes the speaker from a group.
- **`ungroup_all`**: Removes all speakers in the target speaker's household from all groups.
- **`ungroup_all_in_group` (or `ugaig`)**: Ungroups all speakers in a group.
- **`unpair`**: Separate a stereo pair. Can be applied to either speaker in the pair.

### Alarms

Some SoCo-CLI alarm actions below require an **alarm specification** (`alarm_spec`), a comma-separated list of exactly **eight** parameters (without spaces next to the commas), which defines all the properties of an alarm. The parameters are as follows:

  1. Alarm start time, in hours and minutes using the 24hr clock: HH:MM
  2. Alarm duration in hours and minutes: HH:MM
  3. Recurrence: A valid recurrence string is  `DAILY`, `ONCE`, `WEEKDAYS`,
     `WEEKENDS` or of the form `ON_DDDDDD` where `D` is a number from 0-6
     representing a day of the week (Sunday is 0, Monday is 1, etc.), e.g., `ON_034` means
     Sunday, Wednesday and Thursday
  4. Whether the alarm is enabled: `ON` or `OFF` (or `YES`, `NO`)
  5. What to play: `CHIME` (or `chime`) for the standard Sonos alarm sound, or a choice from your Sonos Favourites. Sonos Favourite matching will use case-insensitive, partial matches. 
  6. Play mode: one of `NORMAL`, `SHUFFLE_NOREPEAT`, `SHUFFLE`, `REPEAT_ALL`, `REPEAT_ONE`, `SHUFFLE_REPEAT_ONE` (note that `SHUFFLE` means SHUFFLE *and* REPEAT)
  7. The volume to play at: `0`-`100`
  8. Whether to include grouped speakers: `ON` or `OFF` (or `YES`, `NO`)
 
  Examples of alarm specifications:
  - `07:00,01:30,WEEKDAYS,ON,"Radio 4",NORMAL,50,OFF`
  - `06:30,00:01,WEEKDAYS,ON,CHIME,NORMAL,50,OFF`

In actions which **modify** (or copy and modify) an existing alarm, values that are to be left unchanged are denoted by an underscore in the `alarm_spec`. E.g., to change only the duration and volume of an alarm, use an alarm spec such as: `_,01:00,_,_,_,_,60,_`.

The **alarm actions** are as follows:

  - **`alarms`** (or **`list_alarms`**): List all of the alarms in the Sonos system. Each alarm has a unique integer `alarm_id` that can be used in the other alarm actions.
  - **`alarms_zone`**: List the alarms for the target zone (speaker) only.
  - **`copy_alarm <alarm_id>`**: Copies the alarm with ID `alarm_id` to the target speaker. Note that alarms cannot be copied back to the same speaker (instead, use `copy_modify_alarm` to do this).
  - **`copy_modify_alarm <alarm_id> <alarm_spec>`**: Copies an existing alarm to the target speaker and modifies it according to an alarm specification. Can be used to copy an alarm on the same speaker, but in that case note that the copied alarm **must** have its start time modified.
  - **`create_alarm <alarm_spec>`** (or **`add_alarm`**): Creates a new alarm for the target speaker, according to the `alarm_spec`. 
  - **`disable_alarm <alarm_id,[alarm_id]|all>`** (or **`disable_alarms`**): Disables an existing alarm or alarms. If multiple IDs are supplied, separate them by commas without spaces, e.g., `1,5,6`. To disable all alarms, use `all` as the `alarm_id`.
  - **`enable_alarm <alarm_id,[alarm_id]|all>`** (or **`enable_alarms`**): Enables an existing alarm or alarms. If multiple IDs are supplied, separate them by commas without spaces, e.g., `1,5,6`. To enable all alarms, use `all` as the `alarm_id`.
  - **`modify_alarm <alarm_id,[alarm_id]|all> <alarm_spec>`** (or **`modify_alarms`**): Modifies an existing alarm or alarms, according to the `alarm_spec` format described above (with underscores for values to be left unchanged). To modify all alarms, use `all` as the `alarm_id`.
  - **`move_alarm <alarm_id>`**: Move the alarm with ID `alarm_id` to the target speaker.
  - **`remove_alarm <alarm_id[,alarm_id]|all>`** (or **`remove_alarms`**): Removes one or more alarms by their alarm IDs. If multiple IDs are supplied, separate them by commas without spaces, e.g., `1,5,6`. To remove all alarms, use `all` as the `alarm_id`.
  - **`snooze_alarm <snooze_duration>`**: Snooze an alarm that's already playing on the target speaker. Snooze duration can be `Nm` to snooze for `N` minutes (or just `N`). Alternatively, the duration can be expressed as `HH:MM:SS`. E.g., `sonos bedroom snooze_alarm 10m`, `sonos bedroom snooze_alarm 90`, or `sonos bedroom snooze_alarm 01:20:00`.

### Music Library Search Functions

The actions below search the Sonos Music library.

- **`list_albums`** (or **`albums`**): Lists all the albums in the music library.
- **`list_artists`** (or **`artists`**): Lists all the artists in the music library.
- **`last_search`** (or **`ls`**): Prints the results of the last album, track or artist search performed, or the last use of `tracks_in_album`, `list_albums`, or `list_playlist_tracks`. Use with `queue_search_results` to add specific items to the queue.
- **`search_albums <album_name> <strict>`** (or **`search_album`**, **`salb`**): Searches the albums in your music library for a fuzzy match with `<album_name>`. Prints out the list of matching albums. Use `strict` to require an exact (case-insensitive) match.
-  **`search_artists <artist_name> <strict>`** (or **`search_artist`**, **`sart`**): Searches the artists in your music library for a fuzzy match with `<artist_name>`. Prints out the list of albums featuring any artists that match the search. Use `strict` to require an exact (case-insensitive) match.
- **`search_library <name> <strict>`** (or **`sl`**): Searches the titles in your music library for a fuzzy match with `<name>` against artists, albums and tracks. Prints out the lists of matches. This action is a superset of `search_artists`, `search_albums`, and `search_tracks`, i.e., it searches across all categories. Note: only the last populated search is saved.
- **`search_tracks <track_name> <strict>`** (or **`search_track`**, **`st`**): Searches the tracks in your music library for a fuzzy match with `<track_name>`. Prints out the list of matching tracks. Use `strict` to require an exact (case-insensitive) match.
- **`tracks_in_album <album_name> <strict>`** (or **`tia`**, **`lta`**): Searches the albums in your music library for a fuzzy match with `<album_name>`. Prints out the list of tracks in each matching album. Use `strict` to require an exact (case-insensitive) match.

### Speaker and Sonos System Information

- **`audio_format`**: Soundbars only: report the audio format currently being played.
- **`available_actions`**: List the currently available speaker actions (play, pause, seek, next, etc.).  
- **`battery`**: Shows the battery status for Sonos speakers that contain batteries.
- **`buttons`**: Returns whether the speaker's control buttons are enabled, 'on' or 'off'.
- **`buttons <on|off>`**: Sets whether the speaker's control buttons are on or off.
- **`groups`**: Lists all groups in the Sonos system. Also includes single speakers as groups of one, and paired/bonded sets as groups.
- **`groupstatus`**: Indicates whether the speaker is part of a group, and whether it's part of a stereo pair or bonded home theatre configuration. Note that first can override the second: if a paired/bonded coordinator speaker is also part of a group, the group will be reported but not the paired/bonded status.
- **`has_satellites`**: Returns `yes` if the zone/room has satellite (surround) speakers bonded, otherwise `no`.
- **`has_subwoofer`**: Returns `yes` if the zone/room has a subwoofer bonded, otherwise `no`.
- **`info`**: Provides detailed information on the speaker's settings, current state, software version, IP address, etc.
- **`is_indexing`**: Reports on whether the system is currently in the process of reindexing its local libraries: possible responses are `yes` or `no`.
- **`is_satellite`**: Returns `yes` if the target device is a satellite (surround) speaker, otherwise `no`.
- **`is_subwoofer`**: Returns `yes` if the target device is a subwoofer, otherwise `no`.
- **`libraries`** (or **`shares`**): List the local music library shares.
- **`mic_enabled`**: Reports whether a voice-enabled speaker's microphone is active. Returns `True` or `False`. If the speaker does not have a microphone, or if voice services are not enabled, an error will be reported. (Note that the microphone state is not under software control, so this action can only be used to inspect its state, not to change it.)
- **`reindex`**: Start a reindex of the local music libraries. Will not proceed if a reindex is already underway.
- **`reboot_count`**: Returns the number of times a speaker has been rebooted.
- **`rename <new_name>`**: Rename the speaker.
- **`state`** (or **`status`, `playback`**): Returns the current playback state for the speaker, one of: `PAUSED_PLAYBACK`, `PLAYING`, `STOPPED`, or `TRANSITIONING`.
- **`status_light` (or `light`)**: Returns the state of the speaker's status light, 'on' or 'off'.
- **`status_light <on|off>` (or `light`)**: Switch the speaker's status light on or off.
- **`sysinfo`**: Prints a table of information about all speakers in the system.
- **`zones` (or `visible_zones`, `rooms`, `visible_rooms`)**: Prints a simple list of comma separated visible zone/room names, each in double quotes. Use **`all_zones` (or `all_rooms`)** to return all devices including ones not visible in the Sonos controller apps.

## Multiple Sequential Commands

### Chaining Commands Using the `:` Separator

Multiple commands can be run as part of the same `sonos` invocation by using the `:` separator to add multiple `SPEAKER ACTION <parameters>` sequences to the command line. **The `:` separator must be surrounded by spaces** to disambiguate from other uses of `:` in sonos actions.

The benefit of using this approach instead of multiple separate `sonos` commands is that the cost of starting the program is only incurred once. In addition, it allows for the introduction of wait states and loops.

An arbitrary number of commands can be supplied as part of a single `sonos` invocation. If a failure is encountered with any command, `sonos` will report the error, but will generally attempt to execute subsequent commands.

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

### Waiting Until Playback has Started/Stopped: `wait_start`, `wait_stop` and `wait_end_track`

```
sonos <speaker> wait_start
sonos <speaker> wait_stop
sonos <speaker> wait_stop_not_pause
sonos <speaker> wait_end_track
```

The **`<speaker> wait_start`** and **`<speaker> wait_stop`** actions are used to pause execution of the sequence of `sonos` commands until a speaker has either started or stopped/paused playback. The **`wait_stop_not_pause`** (or **`wsnp`**) action is the same as `wait_stop` but ignores the 'paused' state, i.e., it only resumes when a speaker enters the stopped state.

For example, to reset the volume back to `25` only after the `Bedroom` speaker has stopped playing, use the following command sequence:

`sonos Bedroom wait_stop : Bedroom volume 25`

Note that if a speaker is already playing, `wait_start` will proceed immediately, and if a speaker is already stopped, `wait_stop` will proceed immediately. If the behaviour you want is to continue **after** the **next** piece of audio ends, then you can chain commands as shown in the following example:

`sonos <speaker> wait_start : <speaker> wait_stop : <speaker> vol 50`

The **`wait_end_track`** action will pause execution of `sonos` commands until the current track has ended, or until playback has otherwise paused or stopped. This is useful, for example, when one want to stop playback after the current track has ended:

`sonos <speaker> wait_end_track : <speaker> stop`

### The `wait_stopped_for <duration>` Action

```
sonos <speaker> wait_stopped_for <duration>
sonos <speaker> wait_stopped_for_not_pause <duration>
```

The **`<speaker> wait_stopped_for <duration>`** (or **`wsf`**) action will wait until a speaker has stopped playback for `<duration>` (which uses the same time parameter formats as the `wait` action). If the speaker stops playback, but then restarts (any number of times) during `<duration>`, the timer will be reset to zero each time. Processing continues once the speaker has been stopped for a continuous period equalling the `<duration>`.

The **`<speaker> wait_stopped_for_not_pause <duration>`** (or **`wsfnp`**) action is the same, but ignores the 'paused' state.

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

The following modifiers are available that will invoke or suppress an action depending on the state of the target speaker:

```
sonos <speaker> if_stopped <action> <parameters>
sonos <speaker> if_playing <action> <parameters>
sonos <speaker> if_coordinator <action> <parameters>
sonos <speaker> if_not_coordinator <action> <parameters>
sonos <speaker> if_queue <action> <parameters>
sonos <speaker> if_no_queue <action> <parameters>
```

The `if_stopped` modifier will execute the action that follows it only if the speaker is not currently playing. If the speaker is playing, the action will be skipped, and the next command in the sequence (if applicable) will be executed immediately. For example, to set the volume of a speaker back to a default value only if the speaker is not playing, use:

`sonos <speaker> if_stopped volume 25`

No action will be taken if the speaker is playing, and the command will terminate immediately.

Similarly, the `if_playing` modifier will execute the action that follows it only if the speaker is currently playing.

The `if_coordinator` modifier will execute the action that follows only if the target speaker is a coordinator. The `if_not_coordinator` modifier will execute the action that follows only if the target speaker is not a coordinator. Note that many actions are automatically redirected to the coordinator speaker, so this modifier may not be required, depending on your use case.

The `if_queue` modifier will execute the action that follows it only if the speaker's queue has one or more items in it. Similarly, the `if_no_queue` modifier will execute the following action only if the speaker's queue is empty.

Modifiers can be combined and will be evaluated in left to right sequence. All modifiers must be true for the action to be invoked. E.g.:

`sonos <speaker> if_no_queue if_stopped <action> <parameters>`

## Interactive Shell Mode

```
sonos -i <speaker_name>
sonos --interactive <speaker_name>
sonos -i
```

### Description

Interactive shell mode creates a SoCo-CLI command line session for entering `sonos` commands. Compared to using individual `sonos` invocations, using the shell is faster to perform operations, and requires less typing.

Most `sonos` actions are accepted. Multiple actions can be submitted on a single command line using the ` : ` separator. Command **aliases** can be created for commonly used actions and sequences of actions. A **single-keystroke** mode allows action invocations using one touch of the keyboard. 

### Usage

Interactive mode is started with the `-i` or `--interactive` command line option. Optionally, a speaker name can be given, in which case all commands will be directed to that speaker (until changed in the shell).

Type `help` or `?` at the sonos command line for more information on using interactive shell mode:

```
$ sonos -i

Entering SoCo-CLI interactive shell.
Type 'help' for available shell commands.

Sonos [] > help

This is SoCo-CLI interactive mode. Interactive commands are as follows:

    '1', ...     :  Set the active speaker. Use the numbers shown by the
                    'speakers' command. E.g., to set to speaker number 4
                    in the list, just type '4'.
                    '0' will unset the active speaker.
    'actions'    :  Show the complete list of SoCo-CLI actions.
    'alias'      :  Add an alias: alias <alias_name> <actions>
                    Remove an alias: alias <alias_name>
                    Update an alias by creating a new alias with the same name.
                    Using 'alias' without parameters shows the current list of
                    aliases.
                    Aliases override existing actions and can contain
                    sequences of actions.
    'cd'         :  Change the working directory of the shell, e.g. 'cd ..'.
                    Note that on Windows, backslashes must be doubled, e.g.:
                    'cd C:\\'
    'check_for_update' : Check whether an update is available
    'docs'       :  Print a link to the online documentation.
    'exec'       :  Run a shell command, e.g.: 'exec ls -l'.
    'exit'       :  Exit the shell.
    'help'       :  Show this help message (available shell commands).
    'pop'        :  Restore saved active speaker state.
    'push'       :  Save the current active speaker, and unset the active
                    speaker.
    'rescan'     :  If your speaker doesn't appear in the 'speakers' list,
                    use this to perform a more comprehensive scan.
    'rescan_max' :  Try this if you're still having trouble finding all your
                    speakers.
    'set <spkr>' :  Set the active speaker using its name.
                    Use quotes when needed for the speaker name, e.g.,
                    'set "Front Reception"'. Unambiguous, partial,
                    case-insensitive matches are supported, e.g., 'set front'.
                    To unset the active speaker, omit the speaker name,
                    or just enter '0'.
    'sk'         :  Enters 'single keystroke' mode. (Also 'single-keystroke'.)
    'speakers'   :  List the names of all available speakers.
    'version'    :  Print the versions of SoCo-CLI, SoCo, and Python in use.
    
    The action syntax is the same as when using 'sonos' from the command line.
    If a speaker has been set in the shell, omit the speaker name from the
    action.

    Use the arrow keys for command history and command editing.
    
    [Not Available on Windows] Use the TAB key for autocompletion of shell
    commands, SoCo-CLI actions, aliases, and speaker names.

Sonos [] > 

```

### Shell History and Auto-Completion

Commands in the shell history can be scrolled through by using the up/down arrows, and commands can be edited using the left/right arrows to position the cursor.

(*Not available on Windows*) Shell commands can be auto-completed using the TAB key. The shell history is saved between shell sessions in `~/.soco-cli/shell-history.txt`.

### Shell Aliases

Shell aliases allow the creation of shortcuts for individual actions or sequences of actions. Aliases are created using:

`> alias <alias_name> <alias_action> [ : <alias_action>]`

For example, to **create** an alias action sequence `go` that sets the volume of the active speaker to '50', starts playback, and then shows the track name, use:

`> alias go volume 50 : play : track`

Aliases are **run** by using the alias name, e.g.: `> go`.

Aliases are included in **autocompletion** results, and they **override** built-in commands and actions of the same name (so they can be used to remap commands and actions).

- **List** your aliases using the command `alias` without parameters.
- **Remove** an alias by using `alias <alias_name>` without additional parameters.
- **Update** an alias by creating a new action sequence with the same alias name (the previous alias is overwritten).

Aliases are **saved** between sessions, using a file in the `~/.soco-cli` directory.

#### Push and Pop

The **`push`** and **`pop`** commands are useful in alias actions when one wants to target actions at other speakers, but keep the current active speaker when the action sequence ends. `push` saves the current speaker and unsets it, and `pop` reselects the saved speaker, e.g.:

`> alias fv push : set "Front Reception" : volume 50 : pfrs "Jazz 24" : pop`

This command sequence targets the 'Front Reception' speaker, but first saves the current active speaker, restoring it at the end. (This will, of course, still work if the current active speaker is 'Front Reception'.)

#### Alias Subroutines

Aliases can include other aliases in their sequences of actions, e.g.:

```
> alias alias_1 vol 30 : play
> alias alias_2 push : set Kitchen : alias_1 : pop 
> alias_2
```

Alias subroutines can be nested to an arbitrary depth. **Loops** are detected and prevented when an alias with a loop is invoked. 

#### Alias Arguments

Aliases accept arguments when invoked, which is helpful in remapping existing actions to new alias names. Arguments are specified positionally using `%1`, `%2`, etc. For example:

```
> alias a1 pfq %1
> a1 5          <- Invokes 'pfq 5'
>
> alias a2 push : Kitchen volume %1 : Bathroom volume %1 : pop
>
> a2 30         <- Invokes 'Kitchen volume 30 : Bathroom volume 30'
                   (surrounded by a push/pop to save the current target
                   speaker).
```

If positional arguments are not specified, values will not be passed through. Unsatisfied positional arguments are ignored. For example:

```
> alias a1 vol %1 %2
>
> a1            <- Invokes 'vol'
> a1 50         <- Invokes 'vol 50'
> a1 50 50      <- Invokes 'vol 50 50' (and generates an error).
```

Positional arguments can be used multiple times within an action (unlikely to be useful) or within a sequence of actions.

#### Saving and Loading Aliases

```
sonos --save_aliases <filename>
sonos --load_aliases <filename>
sonos --overwrite_aliases <filename>
```

Aliases can be exported to, and loaded from, plain text files using the command line options above. The command will terminate once the file operation is complete. Option `save_aliases` will export the current aliases to the supplied filename; `load_aliases` will load a list of aliases and merge them with the current list (overwriting any duplicate alias names); `overwrite_aliases` will overwrite all current aliases with the list from the file.

The alias file format consists of lines containing `<alias_name> = <alias actions>`, e.g:

```
# This is a comment line
my_alias = vol 30 : play_fav "Radio 4"
p = pauseplay

# Blank lines are OK
m = mute on
```

### Single Keystroke Mode

Single keystroke mode allows the shell to be controlled by single character presses on the keyboard, without requiring the return key to be pressed. This is useful for some headless automation use cases, as well as sometimes being convenient for interactive use. All single character actions are available, including aliases. 

Enable by using the action `sk` or `single-keystroke` at the shell prompt. Type `x` to exit back to the normal shell.

To start SoCo-CLI in single keystroke mode, use the command line option `--sk`, along with the interactive (`-i` or `--interactive`) option.

## Cached Discovery

SoCo-CLI uses the full range of speaker discovery mechanisms in SoCo to look up speakers by their names to determine their IP addresses.

First, the native Sonos SSDP multicast discovery process is tried.

If this fails, SoCo-CLI will try scanning every IP address on your local network(s) to find the speaker; it's likely to be doing this some of the time if your network contains multiple Sonos systems (multiple 'households'), or if the network has problems with multicast forwarding. This can be slower than is desirable, so SoCo-CLI also provides an alternative process that scans the complete local network for Sonos devices as a one-off process, and then caches the results in a local file for use in future operations.

It's often faster and more convenient to use the local cached speaker list. The disadvantage of using the cached discovery mechanism is that the speaker list can become stale due to speakers being added/removed/renamed, or IP addresses having changed, meaning the cached list must be refreshed. The `sonos-discover` command, discussed below, is a convenient way of doing this.

### Usage

To use the cached discovery mechanism with `sonos`, use the `--use-local-speaker-list` or `-l` flag. The first time this flag is used, the discovery process will be initiated. This will take a few seconds to complete, after which the `sonos` command will execute. A local speaker list is stored in `<your_home_directory>/.soco-cli/` for use with future invocations of the `sonos` command.

**Example:** `sonos -l "living room" volume 50` uses the local speaker database to look up the "living room" speaker.

When executing a sequence of commands, supply the `-l` option only for the first speaker and it will be used for all speaker lookups, e.g.:
 
 `sonos -l kitchen wait_stop : kitchen vol 25 : study play_favourite "Radio 4"`

### Speaker Naming

Speaker naming does not need to be exact. Matching is case-insensitive, and works on substrings. For example, if you have a speaker named `Front Reception`, then `"front reception"` or just `front` will match, as will any unambiguous substring. If an ambiguously matchable name is supplied then an error will be returned.

Note that if you have speakers with the same names in multiple Sonos systems (Households), SoCo-CLI will fail because it cannot disambiguate the speakers. Speakers should have unique names within a network (or fall back on using IP addresses instead of speaker names).

### Refreshing the Local Speaker List

If your speakers change in some way (e.g., they are renamed, are assigned different IP addresses, or you add/remove speakers), you can refresh the discovery cache using the `--refresh-speaker-list` or `-r` option. Note that this option only has an effect when combined with the `-l` option. You can also use the `sonos-discover` command (below).

**Example:** `sonos -lr "living room" volume 50` will refresh the discovery cache before executing the `sonos` command.

### Discovery Options

The following flags can be used to adjust network discovery behaviour if the discovery process is failing:

- **`--network_discovery_threads, -t`**: The number of parallel threads used to scan the local network.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up).

These options only have an effect when combined with the `-l` **and** `-r` options.

**Example:** `sonos -lr -t 256 -n 1.0 "living room" volume 50`

### The `sonos-discover` Command

**`sonos-discover`** is a separate command for creating/updating the local speaker cache, and for seeing the results of the discovery process. It's an alternative to using the `sonos -r` command. It accepts the same `-t`, `-n` and `-m` options as the `sonos` command. 

**Example:** `sonos-discover -t 256 -n 1.0 -m 24` will run `sonos-discover` with a maximum of 256 threads, a network timeout of 1.0s, a minimum netmask of 24 bits, and will print the result.

### Options for the `sonos-discover` Command

Without options, `sonos-discover` will execute the discovery process and print out its results. It will create a speaker cache file, or replace it if already present.

Discovery works by interrogating all network adapters on the device running SoCo-CLI, to build a list of the IP addresses to search for Sonos speakers. If your speakers reside on a subnet that is not directly attached (e.g., they're on a separate VLAN), then use the `--subnets` option to specify manually which networks to search.

**Options**:

- **`--print, -p`**: Print the the current contents of the speaker cache file
- **`--delete-local-speaker-cache, -d`**: Delete the local speaker cache file.
- **`--network_discovery_threads, -t`**: The maximum number of parallel threads used to scan the local network.
- **`--network_discovery_timeout, -n`**: The timeout used when scanning each host on the local network (how long to wait for a socket connection on port 1400 before giving up). Use this if `sonos-discover` is not finding all of your Sonos devices.
- **`--min_netmask, -m`**: The minimum netmask to use when scanning networks. Used to constrain the IP search space. (Note that this option will never **increase** the search space, e.g., if one of the attached networks is 192.168.0.0/24, supplying a `--min_netmask` value of 16 will not increase the search space to 192.168.0.0/16.)
- **`--version, -v`**: Print the versions of SoCo-CLI, SoCo, Python, and exit.
- **`--check_for_update`**: Check for a more recent version of SoCo-CLI.  
- **`--docs`**: Print the URL of this README documentation, for the version of SoCo-CLI being used.
- **`--log <level>`**: Turn on logging. Available levels are NONE (default), CRITICAL, ERROR, WARN, INFO, DEBUG, in order of increasing verbosity.
- **`--subnets <subnets_list>`**: Specify which subnet(s) to search, as a comma separated list (without spaces). E.g.: `--subnets 192.168.0.0/24,192.168.1.0/24` or `--subnets 192.168.0.30`. When this option is used, only the specified subnet(s) will be searched, and the `--min_netmask` option (if supplied) is ignored.

## The SoCo-CLI HTTP API Server

(Note that this functionality requires Python 3.7 or above.)

```
sonos-http-api-server
soco-http-api-server
```

SoCo-CLI can be run as a simple HTTP API server, allowing most of its features to be accessed via HTTP requests. It's very simple to run the server and to construct HTTP requests that invoke it.

### Server Usage

The server is started using the `sonos-http-api-server` or `soco-http-api-server` commands:

```
% sonos-http-api-server
SoCo-CLI: Starting SoCo-CLI HTTP API Server v0.4.41
SoCo-CLI: Finding speakers ... ['Bedroom', 'Front Reception', 'Kitchen', 'Study']
SoCo-CLI: Macro: Attempting to (re)load macros from '/Users/pwt/macros.txt'
SoCo-CLI: Macro: Loaded macros:
          ...
INFO:     Started server process [52137]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

By default, the server listens for incoming requests on **port 8000**. This can be changed using the **`--port (or -p)`** command line option (e.g., `sonos-http-api-server -p 51000`). The listen port must be available, otherwise the server will terminate with an error.

If accessing the HTTP server from another machine on the network, make sure that your firewall allows incoming TCP requests on your chosen port.

For each request, the server will report the equivalent `sonos` command line (if applicable), execute the sonos command, and report the exit code/error, followed by the URL requested and the HTTP response code, e.g.:

```
SoCo-CLI: Command = 'sonos Study volume', exit code = 0
INFO:     127.0.0.1:51017 - "GET /study/volume HTTP/1.1" 200 OK
SoCo-CLI: Command = 'sonos Study volume 30', exit code = 0
INFO:     127.0.0.1:64948 - "GET /Study/volume/30 HTTP/1.1" 200 OK
```

The server will continue running until stopped using CTRL-C (etc.).

### Using the Local Speaker Cache

To use the local speaker cache file instead of speaker discovery, start the HTTP API server with the `--use-local-speaker-list` or `-l` command line option.

When using this option, it's also possible to supply a `--subnets` command line specification, which will be used in the event of a `/rediscover` operation. The use of this option is described in the usage guide for `sonos-discover`.

The `--subnets` option **only** has an effect when using the local speaker cache, and the results of any `/rediscover` operations will overwrite the existing local speaker cache file.

Example of use with both options:

```
sonos-http-api-server -l --subnets=192.168.0.1/24
```

### HTTP Request Structure

All requests are simple HTTP `GET` requests. Request URLs have the form:

```
http://<server>:<port>/<speaker_name>/<action>[/parameter_1/parameter_2/parameter_3]
```

- **`<server>`** is the IP address or hostname of the server on which the HTTP API server is running.
- **`<port>`** is the TCP port on which the server is listening.
- **`<speaker_name>`** is the target speaker for the action. Use the same naming conventions as for other forms of SoCo-CLI usage; unambiguous partial names can be used, as can IP addresses.
- **`<action>`** is the SoCo-CLI action to perform. Almost all of the main SoCo-CLI actions are available for use.
- **`<parameter_1>`** (etc.) are the parameter(s) required by the action, if any.

Strings with characters that are invalid within URLs should be substituted by their URL-friendly replacements  (e.g., space should be replaced by `%20`, comma by `%2C`, apostrophe by `%27`, and colon by `%3A`).

Usage examples:

```
http://192.168.0.100:8000/Study/volume
http://192.168.0.100:8000/Study/volume/50
http://192.168.0.100:8000/Front%20Reception/pause
http://192.168.0.100:8000/Kitchen/group/Hallway
http://192.168.0.100:8000/Kitchen/line_in/Lounge/right_input
```

### Return Values

Return values are supplied in JSON format, and always contain the same fields. A formatted example is shown below:

```
{
  "speaker": "Study",
  "action": "volume",
  "args": [],
  "exit_code": 0,
  "result": "35",
  "error_msg": ""
}
```

The **`speaker`**, **`action`**, and **`args`** fields confirm the data that was sent in the HTTP request, with the speaker's name replaced by its full Sonos name if a shortened version was used in the invocation URL.

The **`exit_code`** field is an integer. This will be zero if the command completed successfully, and non-zero otherwise. (Note that the HTTP response code will indicate success (200) even if the SoCo-CLI action fails, so inspect the `exit_code` for failure detection.)

If the command is successful, the **`result`** field contains the result string, which is exactly the string that would have been printed if the action had been performed on the command line.

If the command is unsuccessful, the **`error_msg`** field contains an error message describing the error.

### Asynchronous Actions (Experimental)

It's sometimes useful for the HTTP API server to respond immediately while its invoked action continues to run in the background. For example, if one wants to invoke a `play_file` action, and have the server respond immediately while the file is played in separate process.

This can be achieved by prefixing the action with `async_`. For example:

```commandline
http://192.168.0.100:8000/Kitchen/async_play_file/my_file.mp3
```

Note that the data returned in this case is probably not useful: it will simply indicate whether the background command was invoked successfully, not whether the command was successful.

Async actions are mutually exclusive for a given speaker: any running async action will be cancelled if a new async action is invoked.

The `async_` functionality does not (yet) apply to the Macros feature described below.

### Macros: Defining Custom HTTP API Server Actions

The **macros** feature allows the creation of custom actions or sequences of actions to be executed by the HTTP API server, and available at the `/macro/<macro_name>` endpoint. Macros are defined in a text file that is loaded when the server starts, and which can subsequently be reloaded using the `/macros/reload` endpoint.

#### Macro Definition and Usage

Macro definitions take the form of the macro name followed by an equals sign (`=`), then the action(s) to be performed. Comments can be included by using `#` as the first character of a line, and blank lines are ignored. For example, the contents of a macro definition file might be:

```
# SoCo-CLI HTTP API Server Macros file
# Format is:
#   macro_name = speaker <action> <parameters> [: speaker <action> <parameters> ...]

# Play the doorbell sound on all speakers
doorbell = Hallway party_mode : Hallway play_file doorbell.mp3 : Hallway ungroup_all

# Group speakers in the morning, and start a favourite radio station
morning = Bathroom group Bedroom : Kitchen group Bedroom : Bedroom play_favourite "Radio 4"

# Set the volume and start playback of a favourite
front_R3 = "Front Reception" volume 50 : "Front Reception" play_favourite "Radio 3"
```

The macros above would be invoked using URLs of the form:
```
http://192.168.0.100:8000/macro/doorbell
http://192.168.0.100:8000/macro/morning
http://192.168.0.100:8000/macro/front_R3
```

**Macro names** are case-sensitive, and should not contain spaces or special characters except for underscores (`_`) and dashes (`-`).

**Speaker names** should ideally use the **exact** speaker name, including capitalisation, and using enclosing quotes where necessary. Shortened names will work, but will be less efficient. (Note: this does not apply when using the local speaker cache option.)

#### Macro Arguments

Macros can be parameterised using up to **twelve** positional arguments, specified in macro definitions by the terms **`%1`** to **`%12`**. The general form for supplying the arguments when the macro is invoked is:

`http://192.168.0.100:8000/macro/<macro_name>/<arg_1>/<arg_2>/<arg_3>/<arg_4>/...` etc.

For example, a macro definition to set all the speakers on one floor to a specified volume could be defined as:

`lower_floor_volume = Kitchen volume %1 : Hallway volume %1 : "Living Room" volume %1`

The macro is then invoked using:

`http://192.168.0.100:8000/macro/lower_floor_volume/30`

Or to use different volumes for each speaker, the macro definition might be:

`lower_floor_volume = Kitchen volume %1 : Hallway volume %2 : "Living Room" volume %3`

and the macro invocation would take the form:

`http://192.168.0.100:8000/macro/lower_floor_volume/30/40/25`

If a macro argument needs to be supplied, but should be ignored during macro processing, then use an underscore `_` as the argument to be ignored. E.g. to ignore `%2` when processing a macro, use a URL of the form:

`http://192.168.0.100:8000/macro/lower_floor_volume/30/_/25`

#### Using the Generic Macro

There's a built-in *generic* macro called `__` that simply maps to `%1 %2 %3 %4 %5 %6 %7 %8 %9 %10 %11 %12`. This can be used to create arbitrary command sequences. For example, to run the equivalent of:
```shell
sonos diner volume 30 : diner play_favourite "radio 4"
```
use the following HTTP request (replacing the `:` command sequence separator with `%3A`):
```shell
http://192.168.0.100:8000/macro/__/diner/volume/30/%3A/diner/play_favourite/radio%204
```

#### Troubleshooting

There is comprehensive server-side logging that reports the macro being invoked, the arguments supplied, the substitutions performed, and the `sonos` command line that is assembled and executed. This is helpful for troubleshooting. E.g., processing the following URL:

`http://192.168.0.100:8000/macro/test_1/Study/volume/_/Peter%27s%20Room/volume`

might generate the following server-side output:

```
SoCo-CLI: Macro: Processing macro 'test_1' = '%1 %2 %3 : %4 %5'
SoCo-CLI: Macro: Parameter variables supplied: ['Study', 'volume', '_', "Peter's Room", 'volume']
SoCo-CLI: Macro: Parameter variables used: ['%1', '%2', '%4', '%5'] -> ['Study', 'volume', '"Peter\'s Room"', 'volume']
SoCo-CLI: Macro: Parameter variables ignored or not supplied for: ['%3']
SoCo-CLI: Macro: Parameter variables supplied but ignored or not used: ['%3'] -> ['_']
SoCo-CLI: Macro: Substituting speaker name 'Study' by IP address '192.168.0.39'
SoCo-CLI: Macro: Substituting speaker name 'Peter's Room' by IP address '192.168.0.42'
SoCo-CLI: Macro: Executing: 'sonos 192.168.0.39 volume : 192.168.0.42 volume' in a subprocess
SoCo-CLI: Macro: Exit code = 0
INFO:     192.168.0.100:61548 - "GET /macro/test_1/Study/volume/_/Peter%27s%20Room/volume HTTP/1.1" 200 OK
```

#### Specifying the Macro Definition File

By default, the HTTP API server will look for a file named `macros.txt` in the directory from which it's invoked (the presence of the file is optional).  If instead you wish to use a specific macros file, use the `--macros` or `-m` option when starting the server, followed by the name of the macros file, e.g.:

```
sonos-http-api-server --macros my_macros.txt
```

#### Reloading the Macro Definition File

The macro file can be reloaded using the `/macros/reload` endpoint (e.g.: `http://192.168.0.100:8000/macros/reload`). This will reload the macros from the original macros file, and overwrite any that are already installed. The new list of macros will be returned in JSON format.

#### Return Values

Successful invocation of a macro will return the sonos command that was executed, and the result(s) of the actions that were performed (or the error output(s) in the case of a failure), in JSON format, e.g.:

```
{"command": "sonos Kitchen volume", result": "30"}
```

#### Listing Macros

The `macros/list` endpoint (e.g.: `http://192.168.0.100:8000/macros/list`) will return a JSON list of the macros installed in the server.

### Listing Speakers

To list the available speakers, use the `/speakers` endpoint, e.g.: `http://192.168.0.100:8000/speakers`. The returned JSON string will list the speakers.

### Rediscovering Speakers

If the configuration of your speakers changes in some way (e.g., if speakers are renamed or if there are IP address changes), the server can be instructed to reload its speaker data using the `/rediscover` endpoint, e.g.: `http://192.168.0.100:8000/rediscover`. The returned JSON string will list the speakers discovered.

If using the local speaker cache option, the speaker cache file will be overwritten with the new discovery results.

### Inspecting the HTTP API

The HTTP API can be inspected and tested using its OpenAPI live documentation, at the `/docs` endpoint, e.g.:`http://192.168.0.100:8000/docs`

## Using SoCo-CLI as a Python Library

If you'd like to use SoCo-CLI as a high-level library in another Python program, it's simple to do so using its API capability. The goal is to provide the same added value, abstractions, and command structure as when using SoCo-CLI directly from the command line. Essentially, there is a single entry point that accepts exactly the same commands that would be used on the command line.

Using the SoCo-CLI API means that the expense of loading SoCo-CLI is incurred only once during the operation of your program, and speaker discovery results are cached for efficiency.

Note that the native SoCo library can be used alongside the SoCo-CLI API, as needed.

### Importing the API

Import SoCo-CLI in your Python code as follows:

```
from soco_cli import api
```

### Using the API

The API entry point is **`api.run_command(speaker_name, action, *args, use_local_speaker_list)`**, which takes exactly the same parameters as would be provided on the command line:

**Parameters:**

- **`speaker_name (str)`**: The speaker name or speaker IP address supplied as a string. Partial, case-insensitive names will be matched, but the match must be unambiguous. A `SoCo` object may be passed in place of the speaker name.
- **`action (str)`**: The action to perform, supplied as a string. Almost all of the SoCo-CLI actions are available for use, with the exception of the `loop` actions, the `wait_until` and `wait_for` actions, and the `track_follow` action.
- **`*args (tuple)`**: The arguments for the action, supplied as strings. There can be zero or more arguments, depending on the action.
- **`use_local_speaker_list (bool)`**: Whether to use the local speaker cache for speaker discovery. Optional, defaults to `False`.

**Return Values:**

Each `run_command()` invocation returns a three tuple consisting of `exit_code (int)`, `output_string (str)`, and `error_msg (str)`. If the exit code is `0`, the command completed successfully, and the command output (if any) is contained in the `output_string`. If the exit code is non-zero, the command did not complete successfully and `error_msg` will be populated while `output_string` will not.

The `output_string` return value contains exactly what would have been printed to the console if the command had been run from the command line.

The public API function definitions include type annotations, to enable type checking with the utility of your choice (e.g., mypy).

**Examples of use:**

```
exit_code, output, error = api.run_command("Kitchen", "volume")
exit_code, output, error = api.run_command("Study", "mute", "on")
exit_code, output, error = api.run_command("Study", "group", "Kitchen")
exit_code, output, error = api.run_command("Front Reception", "play_favourite", "Radio 6")
```

### Convenience Functions

There are some simple additional convenience functions provided by SoCo-CLI. The use of these functions is optional.

- **`api.set_log_level(log_level)`**: This function sets up Python logging for the whole program. `log_level` is a string which can take one of the following values: `None, Critical, Error, Warn, Info, Debug`. The default value is `None`.
- **`api.handle_sigint()`**: This function sets up a signal handler for SIGINT, providing a tidier exit than a stack trace in the event of a CTRL-C interrupt.
- **`api.get_soco_object(speaker_name, use_local_speaker_list=False)`**: Returns a two-tuple of the SoCo object for a given speaker name (or None), and an error message string. Uses the complete set of SoCo-CLI strategies for speaker discovery.

## Known Issues

Please report any problems you find using GitHub Issues [3].

## Uninstalling

1. Use the normal Pip approach to uninstall the SoCo-CLI package: `pip uninstall soco-cli`. 
2. As usual, Pip will not remove dependencies. If you'd like to perform an exhaustive removal, inspect the `requirements.txt` files for `soco-cli`, and for `SoCo`. Take care not to remove packages that may also be required by other installed packages.
3. You may also need to remove the directory `.soco-cli` and its contents from your home directory.

## Acknowledgments

Developed with **[PyCharm](https://www.jetbrains.com/pycharm/)**. Earlier versions benefited from a free Professional licence for open source development from JetBrains.

All trademarks acknowledged. Avantrec Ltd has no connection with Sonos Inc.

## Resources

[1] https://github.com/SoCo/SoCo \
[2] https://pypi.org/project/soco-cli \
[3] https://github.com/avantrec/soco-cli/issues
