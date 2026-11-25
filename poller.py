import logging

from PyQt5.QtCore import QThread, pyqtSignal

from devices import read_devices

log = logging.getLogger(__name__)


class BatteryPoller(QThread):
    updated = pyqtSignal(dict)

    def __init__(self, devices, interval_s: int, parent=None):
        super().__init__(parent)
        self._devices = devices
        self._interval_ms = int(interval_s) * 1000
        self._running = True

    def run(self):
        while self._running:
            try:
                result = read_devices(self._devices)
            except Exception as exc:
                log.exception("Ошибка цикла опроса: %s", exc)
                result = {d["key"]: {"level": None, "present": False} for d in self._devices}
            if not self._running:
                break
            self.updated.emit(result)
            slept = 0
            while slept < self._interval_ms and self._running:
                self.msleep(100)
                slept += 100

    def stop(self):
        self._running = False
        self.wait(3000)
