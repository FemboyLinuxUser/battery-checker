"""SQLite-история разряда устройств."""

import logging
import os
import sqlite3
import threading
import time

from config import HISTORY_PATH, ensure_config_dir

log = logging.getLogger(__name__)


class BatteryHistory:
    def __init__(self, path=None, retention_days=90, unchanged_write_minutes=5):
        ensure_config_dir()
        self.path = path or HISTORY_PATH
        self.retention_days = int(retention_days)
        self.unchanged_write_seconds = int(unchanged_write_minutes) * 60
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                device_key TEXT NOT NULL,
                device_label TEXT NOT NULL,
                level INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_samples_device_time ON samples(device_key, timestamp)"
        )
        self._conn.commit()

    def record(self, device_key, device_label, level):
        if level is None:
            return
        now = time.time()
        level = int(level)
        with self._lock:
            row = self._conn.execute(
                "SELECT timestamp, level FROM samples WHERE device_key=? ORDER BY timestamp DESC LIMIT 1",
                (device_key,),
            ).fetchone()
            if row and row[1] == level and now - row[0] < self.unchanged_write_seconds:
                return
            self._conn.execute(
                "INSERT INTO samples(timestamp, device_key, device_label, level) VALUES (?, ?, ?, ?)",
                (now, device_key, device_label, level),
            )
            cutoff = now - self.retention_days * 86400
            self._conn.execute("DELETE FROM samples WHERE timestamp < ?", (cutoff,))
            self._conn.commit()

    def samples(self, device_key, since_ts):
        with self._lock:
            return self._conn.execute(
                """
                SELECT timestamp, level FROM samples
                WHERE device_key=? AND timestamp>=?
                ORDER BY timestamp ASC
                """,
                (device_key, since_ts),
            ).fetchall()

    def close(self):
        with self._lock:
            self._conn.close()
