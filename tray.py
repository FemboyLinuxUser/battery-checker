from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor


def make_tray_pixmap(level, low_threshold, full_threshold):
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)                         # type: ignore
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    if level is None:
        color = QColor(120, 120, 120)
    elif level <= low_threshold:
        color = QColor(220, 60, 60)
    elif level >= full_threshold:
        color = QColor(60, 200, 90)
    else:
        color = QColor(76, 175, 80)
    p.setPen(Qt.NoPen); p.setBrush(color)           # type: ignore
    p.drawEllipse(2, 2, 60, 60)
    p.setBrush(Qt.white)                            # type: ignore
    p.drawRoundedRect(14, 24, 32, 16, 3, 3)
    p.setBrush(color)
    p.drawRect(16, 26, 28, 12)
    p.setBrush(Qt.white)                            # type: ignore
    p.drawRect(46, 28, 4, 8)
    p.end()
    return pm
