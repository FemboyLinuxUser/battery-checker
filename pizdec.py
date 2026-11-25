# -*- coding: utf-8 -*-
"""
Neon Interactive Presentation — PyQt5 (v2, 10 приколов)
pip install PyQt5

Секреты:
  • Клик по фону — гравитационная воронка
  • Быстрые клики — комбо
  • ↑↑↓↓←→←→BA — Matrix mode
  • Ctrl+Shift+H — «взлом»
  • Тяни голубую пилюлю
  • Кнопка «Салют» рассыпается на осколки
  • Заголовок периодически «взламывается»
  • Поймай убегающую кнопку — получишь ачивку
"""
import sys
import math
import random
import time

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QSlider, QLabel, QVBoxLayout,
    QHBoxLayout, QGraphicsDropShadowEffect, QDialog, QFrame,
    QGraphicsOpacityEffect
)
from PyQt5.QtCore import (
    Qt, QTimer, QPointF, QPoint, QRectF, QPropertyAnimation, QEasingCurve,
    pyqtProperty
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient,
    QFont, QCursor
)


def rgba(hex_color, alpha):
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


# ---------------------------------------------------------------- частицы
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "r", "hue", "alpha")

    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.vx = random.uniform(-0.6, 0.6)
        self.vy = random.uniform(-0.6, 0.6)
        self.r = random.uniform(0.9, 3.0)
        self.hue = random.choice([185, 200, 280, 300, 320, 45, 160])
        self.alpha = random.uniform(0.35, 1.0)

    def step(self, w, h):
        self.x += self.vx
        self.y += self.vy
        if self.x < -12:
            self.x = w + 12
        elif self.x > w + 12:
            self.x = -12
        if self.y < -12:
            self.y = h + 12
        elif self.y > h + 12:
            self.y = -12


class Burst:
    __slots__ = ("x", "y", "vx", "vy", "r", "hue", "life", "decay")

    def __init__(self, x, y):
        ang = random.uniform(0, 2 * math.pi)
        spd = random.uniform(2, 13)
        self.x, self.y = x, y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd
        self.r = random.uniform(2, 5)
        self.hue = random.randint(0, 359)
        self.life = 1.0
        self.decay = random.uniform(0.008, 0.02)


class Shard:
    __slots__ = ("x", "y", "vx", "vy", "size", "rot", "vrot", "color", "life")

    def __init__(self, x, y, color):
        ang = random.uniform(0, 2 * math.pi)
        spd = random.uniform(4, 18)
        self.x, self.y = x, y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd
        self.size = random.uniform(3, 9)
        self.rot = random.uniform(0, 360)
        self.vrot = random.uniform(-25, 25)
        self.color = QColor(color)
        self.life = 1.0


# ------------------------------------------------------- улетающая кнопка
class FlyingWidget(QWidget):
    def __init__(self, text, color, center, parent):
        super().__init__(parent)
        self.text = text
        self.color = QColor(color)
        self._t = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(280, 280)
        self.start = QPointF(center)
        self._place(center)
        self.show()
        self.raise_()

    def _place(self, c):
        self.move(int(c.x() - 140), int(c.y() - 140))

    def get_t(self):
        return self._t

    def set_t(self, v):
        self._t = v
        ex, ey = self.parent().width() + 420, -420
        x = self.start.x() + (ex - self.start.x()) * v
        y = (self.start.y() + (ey - self.start.y()) * v
             - math.sin(v * math.pi) * 220)
        self._place(QPointF(x, y))
        self.update()

    t = pyqtProperty(float, get_t, set_t)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(140, 140)
        p.rotate(self._t * 900)
        s = 1.0 + 0.6 * self._t
        p.scale(s, s)
        alpha = int(255 * max(0.0, 1 - self._t ** 2.2))
        for width, a in ((10, 35), (5, 70)):
            g = QColor(self.color)
            g.setAlpha(int(a * (1 - self._t)))
            pen = QPen(g)
            pen.setWidth(width)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(-90, -30, 180, 60), 30, 30)
        body = QColor(self.color)
        body.setAlpha(alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(body)
        p.drawRoundedRect(QRectF(-90, -28, 180, 56), 28, 28)
        p.setPen(QColor(255, 255, 255, alpha))
        p.setFont(QFont("Segoe UI", 13, QFont.Bold))
        p.drawText(QRectF(-90, -28, 180, 56), Qt.AlignCenter, self.text)


# ---------------------------------------------------- перетаскиваемая пилюля
class PillWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(140, 60)
        self.setCursor(Qt.OpenHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "background:rgba(0,229,255,0.18);"
            "border:2px solid #00e5ff; border-radius:30px;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lb = QLabel("💊 Тяни меня", self)
        lb.setAlignment(Qt.AlignCenter)
        lb.setStyleSheet(
            "color:#cfefff; font-weight:bold;"
            "background:transparent; border:none;")
        lay.addWidget(lb)
        self.vx = self.vy = 0.0
        self.dragging = False
        self.last = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.last = e.globalPos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self.dragging:
            g = e.globalPos()
            d = g - self.last
            self.move(self.pos() + d)
            self.vx = d.x() * 0.75
            self.vy = d.y() * 0.75
            self.last = g

    def mouseReleaseEvent(self, e):
        self.dragging = False
        self.setCursor(Qt.OpenHandCursor)

    def physics(self):
        if self.dragging:
            return
        self.vx *= 0.97
        self.vy *= 0.97
        nx = self.x() + self.vx
        ny = self.y() + self.vy
        par = self.parent()
        if nx < 0:
            nx, self.vx = 0, -self.vx * 0.7
        elif nx > par.width() - self.width():
            nx, self.vx = par.width() - self.width(), -self.vx * 0.7
        if ny < 0:
            ny, self.vy = 0, -self.vy * 0.7
        elif ny > par.height() - self.height():
            ny, self.vy = par.height() - self.height(), -self.vy * 0.7
        self.move(int(nx), int(ny))


# ------------------------------------------------------------ ачивка-тост
class Toast(QWidget):
    def __init__(self, parent, text, icon="🏆"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 rgba(20,30,60,240), stop:1 rgba(60,20,90,240));
            border: 2px solid #ffdd00; border-radius: 14px;
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 20, 10)
        ico = QLabel(icon)
        ico.setStyleSheet(
            "font-size:22px; background:transparent; border:none;")
        msg = QLabel(text)
        msg.setStyleSheet(
            "color:#ffe9a0; font-size:14px; font-weight:bold;"
            "background:transparent; border:none;")
        lay.addWidget(ico)
        lay.addWidget(msg)
        self.adjustSize()
        self.move(parent.width(), parent.height() - 110)
        self.show()
        self.raise_()
        target = parent.width() - self.width() - 20
        a = QPropertyAnimation(self, b"pos")
        a.setDuration(400)
        a.setEndValue(QPoint(target, self.y()))
        a.setEasingCurve(QEasingCurve.OutBack)
        a.start()
        self._a = a
        QTimer.singleShot(3200, self._slide_out)

    def _slide_out(self):
        a = QPropertyAnimation(self, b"pos")
        a.setDuration(400)
        a.setEndValue(QPoint(self.parent().width(), self.y()))
        a.start()
        a.finished.connect(self.deleteLater)
        self._a2 = a


# ------------------------------------------------------------ фейк-взлом
class HackOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0,0,0,235);")
        self.lines = [
            "$ sudo rm -rf / --no-preserve-root",
            "[!] WARNING: unauthorized access detected",
            "[*] Establishing backdoor 0.0.0.0:443 ...",
            "[*] Downloading user data ... 12% ... 45% ... 87%",
            "[!] Uploading to secret server ... [OK]",
            "[!] JUST KIDDING 😈",
            "[*] System restore in progress ...",
        ]
        self.shown = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(280)
        self.show()
        self.raise_()

    def _tick(self):
        self.shown += 1
        if self.shown > len(self.lines) + 3:
            self.timer.stop()
            self.hide()
            self.deleteLater()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont("Consolas", 16, QFont.Bold))
        p.setPen(QColor(0, 255, 80))
        y = 70
        for i in range(min(self.shown, len(self.lines))):
            p.drawText(50, y, self.lines[i])
            y += 34
        if self.shown % 2 == 0:
            p.fillRect(50, y - 24, 12, 24, QColor(0, 255, 80))


# ------------------------------------------------------------- главное окно
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neon Interactive Presentation")
        self.resize(1020, 780)
        self.setMinimumSize(900, 720)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.particles = [Particle(1020, 780) for _ in range(120)]
        self.bursts = []
        self.shards = []
        self.wells = []
        self.trail = []
        self._trail_life = 0
        self.flying = []

        self.angle = 0.0
        self.rot_speed = 1.0
        self.glow = 1.0

        self.rvx = 0.0
        self.rvy = 0.0
        self.freeze_ticks = 0

        self.click_times = []

        self.konami_keys = ["Up", "Up", "Down", "Down",
                            "Left", "Right", "Left", "Right", "B", "A"]
        self.konami_pos = 0
        self.matrix_mode = False
        self.matrix_cols = []

        self.orig_title = "✦  ИНТЕРАКТИВНАЯ  ПРЕЗЕНТАЦИЯ  ✦"
        self.scramble_active = False
        self.scramble_ticks = 0

        self._achievements = set()

        self._build_ui()
        self._build_animations()

        self.pill = PillWidget(self)
        self.pill.move(60, 190)
        self.pill.show()
        self.pill.raise_()

        self.combo_label = QLabel(self)
        self.combo_label.setStyleSheet(
            "color:#ffdd00; font-size:36px; font-weight:900;"
            "background:transparent;")
        self.combo_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.combo_label.hide()

        self.scramble_timer = QTimer(self)
        self.scramble_timer.timeout.connect(self.start_scramble)
        self.scramble_timer.start(7000)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

        # ловим клавиши глобально — независимо от фокуса
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(10)

        self.title = QLabel(self.orig_title)
        self.title.setAlignment(Qt.AlignCenter)
        f = QFont("Segoe UI", 27, QFont.Black)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        self.title.setFont(f)
        self.title.setStyleSheet("color: #b6eeff;")
        self.title_glow = QGraphicsDropShadowEffect(self)
        self.title_glow.setColor(QColor(0, 220, 255))
        self.title_glow.setOffset(0, 0)
        self.title_glow.setBlurRadius(30)
        self.title.setGraphicsEffect(self.title_glow)
        root.addWidget(self.title)

        self.subtitle = QLabel(
            "Крутится  ·  Светится  ·  Мигает  ·  Убегает")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet(
            "color:#9ab4d8; font-size:14px; letter-spacing:4px;")
        self.sub_eff = QGraphicsOpacityEffect(self.subtitle)
        self.subtitle.setGraphicsEffect(self.sub_eff)
        root.addWidget(self.subtitle)

        root.addStretch(1)
        root.addStretch(1)

        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet("""
            #panel {
                background: rgba(12, 18, 40, 175);
                border: 1px solid rgba(90, 170, 255, 95);
                border-radius: 20px;
            }
        """)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(22, 18, 22, 18)
        pl.setSpacing(14)

        brow = QHBoxLayout()
        brow.setSpacing(16)
        self.btn_launch = self._make_button("🚀  Запустить кнопку", "#ff3d7f")
        self.btn_fireworks = self._make_button("🎆  Салют", "#ffb300")
        self.btn_about = self._make_button("ℹ️  О программе", "#00e5ff")
        brow.addStretch(1)
        brow.addWidget(self.btn_launch)
        brow.addWidget(self.btn_fireworks)
        brow.addWidget(self.btn_about)
        brow.addStretch(1)
        pl.addLayout(brow)

        pl.addLayout(self._make_slider_row(
            "Скорость вращения", 0, 300, 100, self._on_speed))
        pl.addLayout(self._make_slider_row(
            "Сила свечения", 20, 200, 100, self._on_glow))

        root.addWidget(panel)

        # убегающая кнопка
        self.runaway = QPushButton("😱  Поймай меня!", self)
        self.runaway.setCursor(Qt.PointingHandCursor)
        self.runaway.setFixedSize(195, 58)
        self.runaway.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                            stop:0 #7b2ff7, stop:1 #f107a3);
                border: 2px solid #ff8ae0;
                border-radius: 29px;
                color: white;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { border: 2px solid #ffffff; }
        """)
        rgl = QGraphicsDropShadowEffect(self)
        rgl.setColor(QColor(241, 7, 163))
        rgl.setOffset(0, 0)
        rgl.setBlurRadius(30)
        self.runaway.setGraphicsEffect(rgl)
        self.runaway.clicked.connect(self._on_runaway_clicked)
        self.runaway.move(self.width() - 300, self.height() - 320)
        self.runaway.raise_()

        self.btn_launch.clicked.connect(self._launch_button)
        self.btn_fireworks.clicked.connect(
            lambda: (self.shatter(self.btn_fireworks, "#ffb300"),
                     self._fireworks()))
        self.btn_about.clicked.connect(self._show_about)

    def _make_button(self, text, color):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(50)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {rgba(color, 0.10)};
                border: 2px solid {color};
                border-radius: 15px;
                padding: 8px 24px;
                font-size: 15px;
                font-weight: bold;
                color: #ffffff;
            }}
            QPushButton:hover  {{ background: {rgba(color, 0.28)}; }}
            QPushButton:pressed{{ background: {rgba(color, 0.50)}; }}
            QPushButton:disabled{{ color: #7b8ba0; border-color: #3a4560; }}
        """)
        eff = QGraphicsDropShadowEffect(b)
        eff.setColor(QColor(color))
        eff.setOffset(0, 0)
        eff.setBlurRadius(22)
        b.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"blurRadius", b)
        anim.setDuration(1600)
        anim.setKeyValueAt(0.0, 10)
        anim.setKeyValueAt(0.5, 38)
        anim.setKeyValueAt(1.0, 10)
        anim.setLoopCount(-1)
        anim.start()
        b._anim = anim
        return b

    def _make_slider_row(self, label, lo, hi, val, callback):
        row = QHBoxLayout()
        row.setSpacing(16)
        lb = QLabel(label)
        lb.setMinimumWidth(170)
        lb.setStyleSheet("color:#b8cdf0; font-size:14px;")
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setCursor(Qt.PointingHandCursor)
        s.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px; background: #16213f; border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                            stop:0 #00e5ff, stop:1 #b23bff);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #6fe3ff; width: 20px; height: 20px;
                margin: -8px 0; border-radius: 10px;
                border: 2px solid #00203a;
            }
        """)
        s.valueChanged.connect(callback)
        vl = QLabel(str(val))
        vl.setMinimumWidth(46)
        vl.setAlignment(Qt.AlignCenter)
        vl.setStyleSheet("color:#6fe3ff; font-weight:bold; font-size:14px;")
        s.valueChanged.connect(lambda v: vl.setText(str(v)))
        row.addWidget(lb)
        row.addWidget(s, 1)
        row.addWidget(vl)
        return row

    def _build_animations(self):
        a = QPropertyAnimation(self.title_glow, b"blurRadius", self)
        a.setDuration(2200)
        a.setKeyValueAt(0.0, 18)
        a.setKeyValueAt(0.5, 55)
        a.setKeyValueAt(1.0, 18)
        a.setLoopCount(-1)
        a.start()
        self._title_anim = a

        b = QPropertyAnimation(self.sub_eff, b"opacity", self)
        b.setDuration(1500)
        b.setKeyValueAt(0.0, 1.0)
        b.setKeyValueAt(0.5, 0.30)
        b.setKeyValueAt(1.0, 1.0)
        b.setLoopCount(-1)
        b.start()
        self._sub_anim = b

    # ---------------------------------------------------------- сервис
    def _on_speed(self, v):
        self.rot_speed = v / 100.0

    def _on_glow(self, v):
        self.glow = v / 100.0

    def _spawn_burst(self, x, y, n=50):
        for _ in range(n):
            self.bursts.append(Burst(x, y))

    def shake(self, amplitude=10, duration=350):
        orig = self.pos()
        t = QTimer(self)
        ticks = max(1, duration // 16)
        state = {"n": 0}

        def step():
            state["n"] += 1
            k = 1.0 - state["n"] / ticks
            self.move(
                orig.x() + int(random.uniform(-amplitude, amplitude) * k),
                orig.y() + int(random.uniform(-amplitude, amplitude) * k))
            if state["n"] >= ticks:
                self.move(orig)
                t.stop()

        t.timeout.connect(step)
        t.start(16)

    def unlock(self, key, text, icon="🏆"):
        if key in self._achievements:
            return
        self._achievements.add(key)
        Toast(self, text, icon)

    def register_click(self):
        now = time.time()
        self.click_times = [t for t in self.click_times if now - t < 1.2]
        self.click_times.append(now)
        n = len(self.click_times)
        if n >= 3:
            self.combo_label.setText(f"{n}x  COMBO!")
            self.combo_label.adjustSize()
            self.combo_label.move(
                (self.width() - self.combo_label.width()) // 2,
                self.height() // 2 - 40)
            self.combo_label.show()
            self.combo_label.raise_()
            QTimer.singleShot(700, self.combo_label.hide)
            if n >= 6:
                self.shake(9, 250)
                self._spawn_burst(self.width() / 2, self.height() / 2, 60)
                self.unlock("combo6", "Серия 6!", "🔥")

    def start_scramble(self):
        self.scramble_ticks = 42
        self.scramble_active = True

    def shatter(self, btn, color="#ff3d7f"):
        c = btn.mapTo(self, btn.rect().center())
        for _ in range(40):
            self.shards.append(Shard(c.x(), c.y(), color))
        btn.setVisible(False)
        self.shake(7, 220)
        self.unlock("shatter", "Деконструктор", "🔨")
        QTimer.singleShot(900, lambda: btn.setVisible(True))

    def toggle_matrix(self):
        self.matrix_mode = not self.matrix_mode
        if self.matrix_mode:
            cols = self.width() // 18
            self.matrix_cols = [
                {"y": random.uniform(-self.height(), 0),
                 "spd": random.uniform(3, 12)}
                for _ in range(cols)
            ]
            self.unlock("matrix", "Взломал матрицу", "🟢")

    # ---------------------------------------------------------- тик
    def _tick(self):
        self.angle = (self.angle + self.rot_speed * 0.9) % 360.0
        w, h = self.width(), self.height()

        # гравитационные воронки
        for wl in self.wells[:]:
            wl["life"] -= 0.018
            if wl["life"] <= 0:
                self.wells.remove(wl)
                continue
            for pt in self.particles:
                dx, dy = wl["x"] - pt.x, wl["y"] - pt.y
                d2 = dx * dx + dy * dy + 40
                if d2 < 45000:
                    f = wl["life"] * 2600 / d2
                    pt.vx += dx * f * 0.02
                    pt.vy += dy * f * 0.02
                pt.vx *= 0.985
                pt.vy *= 0.985

        for pt in self.particles:
            pt.step(w, h)

        for b in self.bursts[:]:
            b.x += b.vx
            b.y += b.vy
            b.vy += 0.28
            b.vx *= 0.99
            b.life -= b.decay
            if b.life <= 0:
                self.bursts.remove(b)

        for s in self.shards[:]:
            s.x += s.vx
            s.y += s.vy
            s.vy += 0.35
            s.vx *= 0.985
            s.rot += s.vrot
            s.life -= 0.012
            if s.life <= 0:
                self.shards.remove(s)

        if self.matrix_mode:
            for col in self.matrix_cols:
                col["y"] += col["spd"]
                if col["y"] > h + 40:
                    col["y"] = random.uniform(-200, -20)
                    col["spd"] = random.uniform(3, 12)

        if self.scramble_active:
            self.scramble_ticks -= 1
            chars = "!@#$%^&*()_+{}[]<>?/\\|~≋∆∎█▓▒░"
            src = self.orig_title
            if self.scramble_ticks > 26:
                self.title.setText("".join(
                    random.choice(chars) if c != " " else " "
                    for c in src))
            elif self.scramble_ticks > 0:
                prog = 1 - self.scramble_ticks / 26
                n_restore = int(len(src) * prog)
                self.title.setText("".join(
                    src[i] if i < n_restore or src[i] == " "
                    else random.choice(chars)
                    for i in range(len(src))))
            else:
                self.title.setText(src)
                self.scramble_active = False

        # угасание шлейфа, когда курсор не двигается
        if self._trail_life > 0:
            self._trail_life -= 1
        elif self.trail:
            self.trail.pop(0)

        self._update_runaway()
        self.pill.physics()
        self.update()

    def _update_runaway(self):
        b = self.runaway
        if self.freeze_ticks > 0:
            self.freeze_ticks -= 1
            return
        c = b.geometry().center()
        cursor = self.mapFromGlobal(QCursor.pos())
        dx, dy = c.x() - cursor.x(), c.y() - cursor.y()
        dist = math.hypot(dx, dy) or 0.001
        RADIUS = 175
        if dist < RADIUS:
            force = (RADIUS - dist) / RADIUS
            self.rvx += dx / dist * force * 19
            self.rvy += dy / dist * force * 19
        self.rvx *= 0.93
        self.rvy *= 0.93
        sp = math.hypot(self.rvx, self.rvy)
        if sp > 27:
            self.rvx *= 27 / sp
            self.rvy *= 27 / sp
        nx, ny = b.x() + self.rvx, b.y() + self.rvy
        m = 8
        maxx = self.width() - b.width() - m
        maxy = self.height() - b.height() - m
        if nx < m:
            nx, self.rvx = m, abs(self.rvx) * 0.75
        elif nx > maxx:
            nx, self.rvx = maxx, -abs(self.rvx) * 0.75
        if ny < m:
            ny, self.rvy = m, abs(self.rvy) * 0.75
        elif ny > maxy:
            ny, self.rvy = maxy, -abs(self.rvy) * 0.75
        b.move(int(nx), int(ny))

    def _on_runaway_clicked(self):
        c = self.runaway.geometry().center()
        self._spawn_burst(c.x(), c.y(), 60)
        self.freeze_ticks = 160
        self.rvx = self.rvy = 0.0
        self.runaway.setText("😅  Поймал!")
        self.register_click()
        self.shake(14, 420)
        self.unlock("catch", "Поймал неуловимого!", "🥷")
        QTimer.singleShot(
            2600, lambda: self.runaway.setText("😱  Поймай меня!"))

    def _launch_button(self):
        b = self.btn_launch
        center = QPointF(b.mapTo(self, b.rect().center()))
        fw = FlyingWidget("🚀  Улетаю!", "#ff3d7f", center, self)
        self.flying.append(fw)
        anim = QPropertyAnimation(fw, b"t", fw)
        anim.setDuration(1500)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.InCubic)

        def _done():
            if fw in self.flying:
                self.flying.remove(fw)
            fw.deleteLater()

        anim.finished.connect(_done)
        anim.start()
        fw._anim = anim
        self._spawn_burst(center.x(), center.y(), 70)
        b.setEnabled(False)
        QTimer.singleShot(2400, lambda: b.setEnabled(True))
        self.shake(8, 260)
        self.register_click()
        self.unlock("rocket", "Космонавт!", "🚀")

    def _fireworks(self):
        for _ in range(6):
            x = random.uniform(90, self.width() - 90)
            y = random.uniform(80, self.height() * 0.62)
            self._spawn_burst(x, y, 45)
        self.shake(6, 240)

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("О программе")
        dlg.setFixedSize(470, 380)
        dlg.setStyleSheet("""
            QDialog { background: #0b1024; border: 1px solid #3aa0ff; }
            QLabel { color: #cfe4ff; }
            QPushButton {
                background: rgba(0,229,255,0.12);
                border: 2px solid #00e5ff;
                border-radius: 12px;
                padding: 8px 28px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(0,229,255,0.32); }
        """)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 24, 24, 24)
        t = QLabel("✨  Neon Presentation  ✨")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(
            "font-size:21px; font-weight:bold; color:#6fe3ff;")
        lay.addWidget(t)
        info = QLabel(
            "PyQt5  ·  Qt5  ·  Python\n\n"
            "Секреты:\n"
            "•  Поймай убегающую кнопку 🥷\n"
            "•  Клик по фону — гравитационная воронка 🌌\n"
            "•  Быстрые клики — комбо 🔥\n"
            "•  ↑↑↓↓←→←→BA — Matrix mode 🟢\n"
            "•  Ctrl+Shift+H — «взлом» 💀\n"
            "•  Тяни голубую пилюлю 💊\n"
            "•  Салют разбивается на осколки 🔨")
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        lay.addWidget(info, 1)
        btn = QPushButton("Закрыть")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn, alignment=Qt.AlignCenter)
        eff = QGraphicsOpacityEffect(dlg)
        dlg.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", dlg)
        a.setDuration(380)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.start()
        dlg._anim = a
        dlg.exec_()

    # ------------------------------------------------------- события
    def mouseMoveEvent(self, e):
        self.trail.append(QPointF(e.pos()))
        if len(self.trail) > 24:
            self.trail.pop(0)
        self._trail_life = 30
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.wells.append({"x": e.x(), "y": e.y(), "life": 1.0})
            self.register_click()
        super().mousePressEvent(e)

    def eventFilter(self, obj, event):
        # ловим клавиши глобально, невзирая на фокус
        if event.type() == event.KeyPress:
            if self._handle_key(event):
                return True
        return super().eventFilter(obj, event)

    def _handle_key(self, e):
        # Ctrl+Shift+H — фейк-взлом
        if (e.key() == Qt.Key_H
                and e.modifiers() & Qt.ControlModifier
                and e.modifiers() & Qt.ShiftModifier):
            HackOverlay(self)
            self.shake(16, 500)
            return True
        # Konami
        mapping = {
            Qt.Key_Up: "Up", Qt.Key_Down: "Down",
            Qt.Key_Left: "Left", Qt.Key_Right: "Right",
            Qt.Key_B: "B", Qt.Key_A: "A",
        }
        k = mapping.get(e.key())
        if k:
            if k == self.konami_keys[self.konami_pos]:
                self.konami_pos += 1
                if self.konami_pos >= len(self.konami_keys):
                    self.konami_pos = 0
                    self.toggle_matrix()
            else:
                self.konami_pos = 1 if k == self.konami_keys[0] else 0
            return True
        return False

    # ------------------------------------------------------- отрисовка
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(8, 10, 26))
        g.setColorAt(0.5, QColor(14, 12, 42))
        g.setColorAt(1.0, QColor(4, 6, 18))
        p.fillRect(self.rect(), g)

        cx, cy = w / 2.0, h * 0.46

        rg = QRadialGradient(QPointF(cx, cy), min(w, h) * 0.6)
        rg.setColorAt(0.0, QColor(60, 120, 255, int(70 * self.glow)))
        rg.setColorAt(0.4, QColor(140, 40, 220, int(30 * self.glow)))
        rg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(rg))

        if self.matrix_mode:
            p.setFont(QFont("Consolas", 15, QFont.Bold))
            for i, col in enumerate(self.matrix_cols):
                x = i * 18 + 4
                for k in range(8):
                    a = int(230 * (1 - k / 8))
                    p.setPen(QColor(0, 255, 100, a))
                    p.drawText(x, int(col["y"] - k * 18),
                               chr(random.randint(0x30, 0x7E)))

        p.setPen(Qt.NoPen)
        for pt in self.particles:
            c = QColor.fromHsv(pt.hue, 220, 255,
                               int(200 * pt.alpha * self.glow))
            p.setBrush(c)
            p.drawEllipse(QPointF(pt.x, pt.y), pt.r, pt.r)

        p.save()
        p.translate(cx, cy)
        for i in range(5):
            p.save()
            p.rotate(self.angle * (1 + i * 0.35) + i * 42)
            pen = QPen(QColor.fromHsv((190 + i * 26) % 360, 200, 255, 130))
            pen.setWidthF(max(0.8, 2.8 - i * 0.35))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            rad = 92 + i * 30
            span = 55 + i * 14
            p.drawArc(QRectF(-rad, -rad, 2 * rad, 2 * rad),
                      0, int(span * 16))
            p.restore()
        p.restore()

        pulse = 1.0 + 0.09 * math.sin(self.angle * 0.12)
        rad = 62 * pulse
        rg2 = QRadialGradient(QPointF(cx, cy), rad * 3)
        rg2.setColorAt(0.00, QColor(190, 245, 255, 225))
        rg2.setColorAt(0.15, QColor(80, 180, 255, 165))
        rg2.setColorAt(0.50, QColor(120, 40, 220, 70))
        rg2.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(rg2))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), rad * 3, rad * 3)

        for i in range(14):
            a = math.radians(self.angle * 2 + i * (360 / 14))
            rr = 155 + 22 * math.sin(self.angle * 0.05 + i)
            x = cx + math.cos(a) * rr
            y = cy + math.sin(a) * rr
            c = QColor.fromHsv((i * 26 + int(self.angle)) % 360,
                               200, 255, 210)
            p.setBrush(c)
            p.drawEllipse(QPointF(x, y), 3.6, 3.6)

        for wl in self.wells:
            r = 18 + 34 * (1 - wl["life"])
            p.setBrush(QColor(120, 200, 255, int(90 * wl["life"])))
            p.drawEllipse(QPointF(wl["x"], wl["y"]), r, r)

        for b in self.bursts:
            c = QColor.fromHsv(b.hue, 240, 255, int(255 * b.life))
            p.setBrush(c)
            p.drawEllipse(QPointF(b.x, b.y),
                          b.r * b.life, b.r * b.life)

        for s in self.shards:
            p.save()
            p.translate(s.x, s.y)
            p.rotate(s.rot)
            c = QColor(s.color)
            c.setAlphaF(max(0, s.life))
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(-s.size / 2, -s.size / 2,
                              s.size, s.size * 0.6))
            p.restore()

        for i, tp in enumerate(self.trail):
            k = i / max(1, len(self.trail) - 1)
            p.setBrush(QColor(120, 220, 255, int(230 * k)))
            p.drawEllipse(tp, 1 + 7 * k, 1 + 7 * k)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "runaway"):
            x = min(self.runaway.x(),
                    self.width() - self.runaway.width() - 8)
            y = min(self.runaway.y(),
                    self.height() - self.runaway.height() - 8)
            self.runaway.move(max(8, x), max(8, y))


# ------------------------------------------------------------------ run
if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())