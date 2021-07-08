"""Parse sequential command lines, using ':' as a command separator."""


class CLIParser:
    def __init__(self):
        self._args = None
        self._sequences = None
        self._separator = ":"

    def parse(self, args):

        self._args = args

        sequence = []  # A single command sequence
        sequences = []  # A list of command sequences
        for arg in args:
            # if len(arg) > 1 and self._separator in arg:
            #     # Catch special cases of colon use: HH:MM(:SS) time formats,
            #     # and URLs
            #     if not (
            #         sequence
            #         and sequence[-1]
            #         in [
            #             "wait",
            #             "wait_for",
            #             "wait_until",
            #             "seek",
            #             "seek_to",
            #             "seek_forward",
            #             "sf",
            #             "seek_back",
            #             "sb",
            #             "sleep",
            #             "sleep_timer",
            #             "sleep_at",
            #             "wait_stopped_for",
            #             "loop_for",
            #             "loop_until",
            #         ]
            #         or ":/" in arg
            #     ):
            #         error_and_exit(
            #             "Spaces are required each side of the ':' command separator"
            #         )
            if arg != self._separator:
                sequence.append(arg)
            else:
                sequences.append(sequence)
                sequence = []
        if sequence:
            sequences.append(sequence)

        self._sequences = sequences

    def get_sequences(self):
        return self._sequences
