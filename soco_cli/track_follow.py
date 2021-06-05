from time import sleep
from soco_cli.api import run_command


def track_follow(speaker, use_local_speaker_list=False, break_on_pause=True):
    first = True
    while True:
        # Print the track info
        exit_code, output, _ = run_command(
            speaker, "track", use_local_speaker_list=use_local_speaker_list
        )
        if exit_code == 0:
            output = output.replace("Playback state is 'PLAYING':\n", "")
            output = output.replace("Playback state is 'TRANSITIONING':\n", "")
            if not first:
                output = output.split("\n", 1)[1]
            else:
                first = False
            print(output)

        # Wait until the track changes
        run_command(
            speaker, "wait_end_track", use_local_speaker_list=use_local_speaker_list
        )

        # Allow speaker state to stabilise
        sleep(3)

        # Check to see if the speaker has stopped playing, and exit loop
        if break_on_pause and speaker.get_current_transport_info()[
            "current_transport_state"
        ] in [
            "STOPPED",
            "PAUSED_PLAYBACK",
        ]:
            break
