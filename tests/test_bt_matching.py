from bt_battery_ctypes import match_scanned_devices


def test_exact_match_wins_over_longer_substring():
    scanned = [
        {"name": "AVRCP MOMENTUM 4", "level": 30},
        {"name": "MOMENTUM 4", "level": 80},
    ]
    assert match_scanned_devices(["MOMENTUM 4"], scanned) == {
        "MOMENTUM 4": {"present": True, "level": 80}
    }


def test_substring_battery_used_without_exact_battery():
    scanned = [
        {"name": "MOMENTUM 4", "level": None},
        {"name": "AVRCP MOMENTUM 4", "level": 30},
    ]
    assert match_scanned_devices(["MOMENTUM 4"], scanned) == {
        "MOMENTUM 4": {"present": True, "level": 30}
    }
