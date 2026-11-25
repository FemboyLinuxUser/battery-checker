from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget


class BatteryRowOverlay(QWidget):
    BATTERY_W = 32
    BATTERY_H = 14
    NUB_W = 2
    NUB_H = 7
    GAP = 6

    OVERLAY_FLAGS = (
    Qt.FramelessWindowHint          # type: ignore
    | Qt.WindowStaysOnTopHint       # type: ignore
    | Qt.Tool                       # type: ignore
    | Qt.WindowTransparentForInput  # type: ignore
    | Qt.WindowDoesNotAcceptFocus   # type: ignore
)

    def __init__(self, devices, pos, low_threshold, opacity=1.0):
        super().__init__()
        self._low_threshold = int(low_threshold)
        self.setWindowFlags(self.OVERLAY_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground, True)        # type: ignore
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)        # type: ignore
        self.set_devices(devices)
        self.move(*pos)
        self.set_opacity(opacity)

    def set_opacity(self, opacity: float):
        self.setWindowOpacity(max(0.05, min(1.0, float(opacity))))

    def set_devices(self, devices):
        self._devices = devices
        self._levels = {d["key"]: None for d in devices}
        n = len(devices)
        if n == 0:
            self.setFixedSize(1, 1)
        else:
            w = n * (self.BATTERY_W + self.NUB_W) + (n - 1) * self.GAP
            self.setFixedSize(w, self.BATTERY_H)
        self.update()

    def set_low_threshold(self, t):
        self._low_threshold = int(t)
        self.update()

    def update_levels(self, levels):
        self._levels = levels
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        x = 0
        for dev in self._devices:
            self._draw_battery(p, x, 0, self._levels.get(dev["key"]), dev["type"])
            x += self.BATTERY_W + self.NUB_W + self.GAP

    def _draw_battery(self, p, x, y, level, dev_type):
        bw, bh = self.BATTERY_W, self.BATTERY_H
        p.setPen(Qt.NoPen)                      # type: ignore
        p.setBrush(QColor(0, 0, 0, 170))
        p.drawRoundedRect(QRectF(x, y, bw, bh), 2, 2)
        if level is None:
            fill_color = QColor(130, 130, 130); ratio = 0.0
        else:
            ratio = max(0.0, min(1.0, level / 100.0))
            fill_color = (QColor(220, 60, 60) if level <= self._low_threshold
                          else QColor(76, 175, 80))
        pad = 2
        if ratio > 0:
            fw = (bw - pad * 2) * ratio
            fh = bh - pad * 2
            p.setBrush(fill_color)
            p.drawRoundedRect(QRectF(x + pad, y + pad, fw, fh), 1, 1)
        cx, cy = x + bw / 2, y + bh / 2
        self._draw_icon(p, dev_type, cx, cy, 8 if dev_type == "keyboard" else 9)
        p.setPen(QPen(QColor(230, 230, 230), 1))
        p.setBrush(Qt.NoBrush)                  # type: ignore
        p.drawRoundedRect(QRectF(x, y, bw, bh), 2, 2)
        p.setPen(Qt.NoPen)                      # type: ignore
        p.setBrush(QColor(230, 230, 230))
        p.drawRect(QRectF(x + bw, y + (bh - self.NUB_H) / 2, self.NUB_W, self.NUB_H))

    def _draw_icon(self, p, dev_type, cx, cy, size):
        if dev_type == "keyboard": self._draw_keyboard(p, cx, cy, size)
        elif dev_type == "headphones": self._draw_headphones(p, cx, cy, size)
        elif dev_type == "mouse": self._draw_mouse(p, cx, cy, size)
        elif dev_type == "speaker": self._draw_speaker(p, cx, cy, size)
        elif dev_type == "gamepad": self._draw_gamepad(p, cx, cy, size)
        else: self._draw_generic(p, cx, cy, size)

    def _draw_keyboard(self, p, cx, cy, size):
        w, h = size, size * 0.65
        x, y = cx - w / 2, cy - h / 2
        p.setPen(Qt.NoPen); p.setBrush(Qt.white)                    # type: ignore
        p.drawRoundedRect(QRectF(x, y, w, h), 1, 1)
        p.setBrush(QColor(30, 30, 30)); ip = 0.9
        for i in range(2):
            ky = y + ip + i * (h - ip * 2) * 0.55
            p.drawRect(QRectF(x + ip, ky, w - ip * 2, 0.8))

    def _draw_headphones(self, p, cx, cy, size):
        x, y = cx - size / 2, cy - size / 2
        p.setPen(QPen(Qt.white, 1.3)); p.setBrush(Qt.NoBrush)       # type: ignore
        p.drawArc(QRectF(x + size * 0.15, y, size * 0.7, size * 0.85), 0, 180 * 16)
        p.setPen(Qt.NoPen); p.setBrush(Qt.white)                    # type: ignore
        cw, ch = size * 0.22, size * 0.4
        cy_ = y + size * 0.5
        p.drawRoundedRect(QRectF(x + size * 0.02, cy_, cw, ch), 1, 1)
        p.drawRoundedRect(QRectF(x + size * 0.98 - cw, cy_, cw, ch), 1, 1)

    def _draw_mouse(self, p, cx, cy, size):
        w, h = size * 0.55, size * 0.85
        x, y = cx - w / 2, cy - h / 2
        p.setPen(QPen(Qt.white, 1.2)); p.setBrush(Qt.NoBrush)       # type: ignore
        p.drawRoundedRect(QRectF(x, y, w, h), w / 2, w / 2)
        p.drawLine(int(cx), int(y + 1), int(cx), int(y + h * 0.45))

    def _draw_speaker(self, p, cx, cy, size):
        w, h = size * 0.62, size * 0.85
        x, y = cx - w / 2, cy - h / 2
        p.setPen(Qt.NoPen); p.setBrush(Qt.white)                    # type: ignore
        p.drawRoundedRect(QRectF(x, y, w, h), 1, 1)
        p.setBrush(QColor(30, 30, 30))
        r = size * 0.16
        p.drawEllipse(QRectF(cx - r, y + h * 0.55, r * 2, r * 2))
        p.setBrush(Qt.white)                                        # type: ignore
        p.drawEllipse(QRectF(cx - r * 0.5, y + h * 0.12, r, r))

    def _draw_gamepad(self, p, cx, cy, size):
        w, h = size, size * 0.55
        x, y = cx - w / 2, cy - h / 2
        p.setPen(QPen(Qt.white, 1.2))                               # type: ignore
        p.setBrush(Qt.NoBrush)                                      # type: ignore
        p.drawRoundedRect(QRectF(x, y, w, h), h * 0.4, h * 0.4)
        p.drawLine(int(x + w * 0.22), int(cy), int(x + w * 0.42), int(cy))
        p.setPen(Qt.NoPen); p.setBrush(Qt.white)                    # type: ignore
        p.drawEllipse(QRectF(x + w * 0.68, cy - 1, 2, 2))
        p.drawEllipse(QRectF(x + w * 0.78, cy - 1, 2, 2))

    def _draw_generic(self, p, cx, cy, size):
        p.setPen(Qt.NoPen); p.setBrush(Qt.white)                    # type: ignore
        r = size * 0.28
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
