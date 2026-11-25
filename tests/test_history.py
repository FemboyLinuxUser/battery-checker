import time

from history import BatteryHistory


def test_history_writes_only_changed_or_old_samples(tmp_path):
    db = tmp_path / "history.db"
    history = BatteryHistory(str(db), retention_days=90, unchanged_write_minutes=5)
    history.record("dev", "Device", 90)
    history.record("dev", "Device", 90)
    history.record("dev", "Device", 89)
    rows = history.samples("dev", 0)
    assert [level for _ts, level in rows] == [90, 89]
    history.close()


def test_history_retention(tmp_path):
    db = tmp_path / "history.db"
    history = BatteryHistory(str(db), retention_days=1, unchanged_write_minutes=5)
    old = time.time() - 3 * 86400
    with history._lock:
        history._conn.execute(
            "INSERT INTO samples(timestamp, device_key, device_label, level) VALUES (?, ?, ?, ?)",
            (old, "dev", "Device", 50),
        )
        history._conn.commit()
    history.record("dev", "Device", 49)
    rows = history.samples("dev", 0)
    assert all(ts > old for ts, _level in rows)
    history.close()
