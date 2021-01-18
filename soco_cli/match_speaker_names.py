import logging


def speaker_name_matches(name_supplied, name_stored):
    """Matches speaker names."""

    # Exact match
    name_supplied_original = name_supplied
    name_stored_original = name_stored
    if name_supplied == name_stored:
        logging.info(
            "Found exact speaker name match for '{}'".format(name_stored_original)
        )
        return True, True

    # Case insensitive match; treat as an exact match
    name_supplied = name_supplied.lower()
    name_stored = name_stored.lower()
    if name_supplied == name_stored:
        logging.info(
            "Found case-insensitive exact speaker name match for '{}' as '{}'".format(
                name_supplied_original, name_stored_original
            )
        )
        return True, True

    # Normalised apostrophe match; treat as an exact match
    name_supplied = name_supplied.replace("’", "'")
    name_stored = name_stored.replace("’", "'")
    if name_supplied == name_stored:
        logging.info(
            "Found apostrophe-normalised exact speaker name match for '{}' as '{}'".format(
                name_supplied_original, name_stored_original
            )
        )
        return True, True

    # Partial match with start of name
    if name_stored.startswith(name_supplied):
        logging.info(
            "Found partial, start-of-name match for '{}' as '{}'".format(
                name_supplied_original, name_stored_original
            )
        )
        return True, False

    # Partial match with any part of name
    if name_supplied in name_stored:
        logging.info(
            "Found partial, any-part-of-name match for '{}' as '{}'".format(
                name_supplied_original, name_stored_original
            )
        )
        return True, False

    # Not found
    return False, False
