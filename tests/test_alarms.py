"""Tests for alarms.py that don't need a live Sonos network."""

from unittest.mock import MagicMock

import pytest
from soco.alarms import Alarms
from soco.core import _ArgsSingleton

from soco_cli.alarms import _get_alarms

ALARM_XML = (
    '<Alarms><Alarm ID="{id}" StartTime="07:00:00" Duration="02:00:00"'
    ' Recurrence="DAILY" Enabled="1" RoomUUID="{room}"'
    ' ProgramURI="x-rincon-buzzer:0" ProgramMetaData=""'
    ' PlayMode="SHUFFLE_NOREPEAT" Volume="25" IncludeLinkedZones="0"/></Alarms>'
)


def _speaker(uid, household_id, alarm_id, alarm_list_id):
    speaker = MagicMock()
    speaker.uid = uid
    speaker.household_id = household_id
    speaker.all_zones = {speaker}
    speaker.alarmClock.ListAlarms.return_value = {
        "CurrentAlarmList": ALARM_XML.format(id=alarm_id, room=uid),
        # Each household's alarm list version is issued by one of its speakers
        "CurrentAlarmListVersion": "{}:{}".format(uid, alarm_list_id),
    }
    return speaker


@pytest.fixture(autouse=True)
def reset_alarms_singletons():
    """Ensure each test starts with empty SoCo alarm caches."""
    _ArgsSingleton._instances.pop(Alarms._class_group, None)
    yield
    _ArgsSingleton._instances.pop(Alarms._class_group, None)


def test_get_alarms_returns_speaker_household_alarms():
    speaker = _speaker("RINCON_A", "Sonos_A", "5", 10)
    alarms = _get_alarms(speaker)
    assert {alarm.alarm_id for alarm in alarms} == {"5"}
    assert all(alarm.zone is speaker for alarm in alarms)


def test_get_alarms_keeps_households_separate():
    # Household B's alarm list version (3) is lower than A's (10). With a
    # single shared cache, B's alarm list would be treated as stale and
    # household A's alarms returned instead.
    speaker_a = _speaker("RINCON_A", "Sonos_A", "5", 10)
    speaker_b = _speaker("RINCON_B", "Sonos_B", "7", 3)

    alarms_a = _get_alarms(speaker_a)
    alarms_b = _get_alarms(speaker_b)

    assert {alarm.alarm_id for alarm in alarms_a} == {"5"}
    assert {alarm.alarm_id for alarm in alarms_b} == {"7"}
    assert all(alarm.zone is speaker_b for alarm in alarms_b)

    # Re-querying household A still returns only A's alarms
    assert {alarm.alarm_id for alarm in _get_alarms(speaker_a)} == {"5"}
