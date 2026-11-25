import sys
from copy import deepcopy

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QSpinBox, QCheckBox,
    QComboBox, QPushButton, QToolButton, QGroupBox, QFormLayout,
    QHBoxLayout, QVBoxLayout, QSystemTrayIcon, QMenu, QAction,
    QMessageBox, QScrollArea, QSlider, QStackedWidget,
)

from aula_battery import get_battery_level
from bt_battery_ctypes import get_bluetooth_battery_level
from config import __application_path, load_config, save_config
from bt_devices import list_bluetooth_devices
import beep_sound as snd


# ------------------------------ Константы / утилиты ------------------------------
DEVICE_TYPE_LABELS = {
    "keyboard": "Клавиатура",
    "headphones": "Наушники",
    "mouse": "Мышь",
    "speaker": "Колонка",
    "generic": "Другое",
    "gamepad": "Геймпад",
}


def _normalize_devices_list(raw):
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []
    out = []
    for key, dcfg in raw.items():
        if not isinstance(dcfg, dict):
            continue
        if "bluetooth_name" in dcfg:
            out.append({
                "source": "bluetooth",
                "bluetooth_name": dcfg["bluetooth_name"],
                "type": "headphones",
                "enabled": True,
            })
        elif key == "aula":
            out.append({"source": "aula", "type": "keyboard", "enabled": True})
    return out


CFG = load_config()


def build_devices(cfg):
    devices = []
    raw = cfg.get("battery", {}).get("devices", [])
    for i, dcfg in enumerate(_normalize_devices_list(raw)):
        if not dcfg.get("enabled", True):
            continue
        source = dcfg.get("source")
        dev_type = dcfg.get("type", "generic")
        key = f"dev_{i}"

        if source == "aula":
            getter = get_battery_level
            label = DEVICE_TYPE_LABELS.get(dev_type, "Устройство")
            low_s, full_s = "low_aula", "full_aula"
        elif source == "bluetooth":
            bt_name = dcfg.get("bluetooth_name", "")
            if not bt_name:
                continue
            def _bt_getter(n=bt_name):
                return get_bluetooth_battery_level(n)
            getter = _bt_getter
            label = bt_name
            low_s, full_s = "low_bt", "full_bt"
        else:
            continue

        devices.append({
            "key": key, "type": dev_type, "label": label,
            "getter": getter,
            "low_sound": low_s, "full_sound": full_s,
        })
    return devices


# ------------------------------ Строка батарей ------------------------------
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


# ------------------------------ Поток опроса ------------------------------
class BatteryPoller(QThread):
    updated = pyqtSignal(dict)

    def __init__(self, devices, interval_s: int, parent=None):
        super().__init__(parent)
        self._devices = devices
        self._interval_ms = int(interval_s) * 1000
        self._running = True

    def run(self):
        while self._running:
            result = {}
            for dev in self._devices:
                try:
                    result[dev["key"]] = dev["getter"]()
                except Exception as e:
                    print(f"[{dev['key']}] ошибка опроса: {e}")
                    result[dev["key"]] = None
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

class SoundEditor(QWidget):
    """Редактор одного звука: файл ИЛИ тон (freq/dur/count/gap)."""

    def __init__(self, name, spec, parent=None):
        super().__init__(parent)
        spec = _normalize_sound_spec(spec)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # header: имя + выбор режима
        header = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setMinimumWidth(90)
        name_lbl.setStyleSheet("font-weight: 600;")
        header.addWidget(name_lbl)
        self.mode = QComboBox()
        self.mode.addItem("Файл", "file")
        self.mode.addItem("Тон", "tone")
        header.addWidget(self.mode)
        header.addStretch()
        layout.addLayout(header)

        # file editor
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("напр. sounds/low_aula.wav")

        # tone editor
        tone_w = QWidget()
        tone_l = QHBoxLayout(tone_w)
        tone_l.setContentsMargins(0, 0, 0, 0)
        tone_l.setSpacing(6)

        self.freq_spin = QSpinBox(); self.freq_spin.setRange(50, 8000); self.freq_spin.setSuffix(" Hz"); self.freq_spin.setFixedWidth(90)
        self.dur_spin = QSpinBox(); self.dur_spin.setRange(10, 5000); self.dur_spin.setSuffix(" ms"); self.dur_spin.setFixedWidth(90)
        self.count_spin = QSpinBox(); self.count_spin.setRange(1, 20); self.count_spin.setFixedWidth(60)
        self.gap_spin = QSpinBox(); self.gap_spin.setRange(0, 2000); self.gap_spin.setSuffix(" ms"); self.gap_spin.setFixedWidth(90)

        tone_l.addWidget(QLabel("Частота:")); tone_l.addWidget(self.freq_spin)
        tone_l.addWidget(QLabel("Длит.:")); tone_l.addWidget(self.dur_spin)
        tone_l.addWidget(QLabel("×")); tone_l.addWidget(self.count_spin)
        tone_l.addWidget(QLabel("Пауза:")); tone_l.addWidget(self.gap_spin)
        tone_l.addStretch()

        # stack: 0 = file, 1 = tone
        self.stack = QStackedWidget()
        self.stack.addWidget(self.file_edit)
        self.stack.addWidget(tone_w)
        layout.addWidget(self.stack)

        # mode combo → stack index (совпадают 0/1)
        self.mode.currentIndexChanged.connect(self.stack.setCurrentIndex)

        self.set_spec(spec)

    def set_spec(self, spec):
        spec = _normalize_sound_spec(spec)
        is_tone = any(k in spec for k in ("freq", "dur_ms", "count", "gap_ms"))
        self.file_edit.setText(spec.get("file", ""))
        self.freq_spin.setValue(int(spec.get("freq", 800)))
        self.dur_spin.setValue(int(spec.get("dur_ms", 100)))
        self.count_spin.setValue(int(spec.get("count", 1)))
        self.gap_spin.setValue(int(spec.get("gap_ms", 0)))
        self.mode.setCurrentIndex(1 if is_tone else 0)
        self.stack.setCurrentIndex(1 if is_tone else 0)

    def get_spec(self, old_spec=None):
        spec = dict(old_spec) if isinstance(old_spec, dict) else {}
        mode = self.mode.currentData()
        if mode == "file":
            for k in ("freq", "dur_ms", "count", "gap_ms"):
                spec.pop(k, None)
            spec["file"] = self.file_edit.text().strip()
        else:
            spec.pop("file", None)
            spec["freq"] = self.freq_spin.value()
            spec["dur_ms"] = self.dur_spin.value()
            spec["count"] = self.count_spin.value()
            spec["gap_ms"] = self.gap_spin.value()
        return spec

# ------------------------------ Окно настроек ------------------------------
class SettingsWindow(QWidget):
    def __init__(self, cfg, on_save, on_preview_pos, on_preview_opacity, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Battery Monitor — Настройки")
        self.setMinimumWidth(600)
        self._on_save = on_save
        self._on_preview_pos = on_preview_pos
        self._on_preview_opacity = on_preview_opacity
        self._cfg = deepcopy(cfg)
        self._device_rows = []
        self._bt_devices_cache = []
        self._initial_bt_refresh_done = False
        self._saved_pos = (20, 20)
        self._build_ui()
        self.reload(cfg)

    # ------- UI -------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- battery ---
        bat_box = QGroupBox("Батареи")
        bat_form = QFormLayout(bat_box)

        self.low_spin = QSpinBox(); self.low_spin.setRange(0, 100); self.low_spin.setSuffix(" %")
        self.full_spin = QSpinBox(); self.full_spin.setRange(0, 100); self.full_spin.setSuffix(" %")
        self.interval_spin = QSpinBox(); self.interval_spin.setRange(5, 3600); self.interval_spin.setSuffix(" с")

        # диапазон позиции — по виртуальному рабочему столу
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.virtualGeometry()
            xmin, xmax = geo.left(), geo.right()
            ymin, ymax = geo.top(), geo.bottom()
        else:
            xmin, xmax, ymin, ymax = -10000, 10000, -10000, 10000

        # --- позиция X: слайдер + спинбокс ---
        self.pos_x_slider = QSlider(Qt.Horizontal); self.pos_x_slider.setRange(xmin, xmax)          # type: ignore
        self.pos_x = QSpinBox(); self.pos_x.setRange(xmin, xmax); self.pos_x.setFixedWidth(80)
        self.pos_x_slider.valueChanged.connect(self._on_x_slider)
        self.pos_x.valueChanged.connect(self._on_x_spin)
        pos_x_row = QHBoxLayout()
        pos_x_row.addWidget(self.pos_x_slider, 1)
        pos_x_row.addWidget(self.pos_x)

        # --- позиция Y: слайдер + спинбокс ---
        self.pos_y_slider = QSlider(Qt.Horizontal); self.pos_y_slider.setRange(ymin, ymax)          # type: ignore
        self.pos_y = QSpinBox(); self.pos_y.setRange(ymin, ymax); self.pos_y.setFixedWidth(80)
        self.pos_y_slider.valueChanged.connect(self._on_y_slider)
        self.pos_y.valueChanged.connect(self._on_y_spin)
        pos_y_row = QHBoxLayout()
        pos_y_row.addWidget(self.pos_y_slider, 1)
        pos_y_row.addWidget(self.pos_y)

        # --- прозрачность ---
        self.opacity_slider = QSlider(Qt.Horizontal); self.opacity_slider.setRange(5, 100)          # type: ignore
        self.opacity_spin = QSpinBox(); self.opacity_spin.setRange(5, 100)
        self.opacity_spin.setSuffix(" %"); self.opacity_spin.setFixedWidth(70)
        self.opacity_slider.valueChanged.connect(self._on_op_slider)
        self.opacity_spin.valueChanged.connect(self._on_op_spin)
        op_row = QHBoxLayout()
        op_row.addWidget(self.opacity_slider, 1)
        op_row.addWidget(self.opacity_spin)

        self.show_overlay_cb = QCheckBox("Показывать батареи при запуске")

        bat_form.addRow("Нижний порог (красный):", self.low_spin)
        bat_form.addRow("Верхний порог (полный):", self.full_spin)
        bat_form.addRow("Интервал опроса:", self.interval_spin)
        bat_form.addRow("Позиция X:", pos_x_row)
        bat_form.addRow("Позиция Y:", pos_y_row)
        bat_form.addRow("Прозрачность:", op_row)
        bat_form.addRow(self.show_overlay_cb)
        root.addWidget(bat_box)

        # --- devices ---
        dev_box = QGroupBox("Устройства")
        dev_v = QVBoxLayout(dev_box)
        top = QHBoxLayout()
        top.addWidget(QLabel("Отметьте устройства для отображения и выберите иконку."))
        top.addStretch()
        refresh_btn = QPushButton("Обновить список BT")
        refresh_btn.clicked.connect(self._refresh_bt_clicked)
        top.addWidget(refresh_btn)
        dev_v.addLayout(top)

        self._dev_scroll = QScrollArea()
        self._dev_scroll.setWidgetResizable(True)
        self._dev_scroll.setMaximumHeight(440)
        container = QWidget()
        self._dev_layout = QVBoxLayout(container)
        self._dev_layout.setAlignment(Qt.AlignTop)                                  # type: ignore
        self._dev_layout.setSpacing(2)
        self._dev_scroll.setWidget(container)
        dev_v.addWidget(self._dev_scroll)
        root.addWidget(dev_box)

        # --- sounds (сворачиваемые) ---
        snd_box = QGroupBox("Звуки")
        snd_v = QVBoxLayout(snd_box)
        self.sounds_toggle = QToolButton()
        self.sounds_toggle.setText("Настройки звуков")
        self.sounds_toggle.setCheckable(True)
        self.sounds_toggle.setChecked(False)
        self.sounds_toggle.setArrowType(Qt.RightArrow)                              # type: ignore
        self.sounds_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)          # type: ignore
        self.sounds_toggle.setAutoRaise(True)
        self.sounds_toggle.toggled.connect(self._toggle_sounds)
        snd_v.addWidget(self.sounds_toggle, 0, Qt.AlignLeft)                        # type: ignore

        self._sounds_container = QWidget()
        snd_form = QFormLayout(self._sounds_container)
        snd_form.setContentsMargins(12, 4, 0, 0)
        desc = QLabel(
            "Имя файла относительно папки приложения (base_dir).\n"
            "Можно указать подпапку, например: sounds/low_aula.wav"
        )
        desc.setStyleSheet("color: #888; font-size: 11px;")
        snd_form.addRow(desc)
        self._sound_editors = {}
        for key, spec in self._cfg.get("sounds", {}).items():
            ed = SoundEditor(key, spec)
            self._sound_editors[key] = ed
            snd_form.addRow(ed)
        self._sounds_container.setVisible(False)
        snd_v.addWidget(self._sounds_container)
        root.addWidget(snd_box)

        # --- buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Закрыть")
        cancel_btn.clicked.connect(self._close)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        root.addLayout(btn_row)

    # ------- синхронизация слайдер <-> спинбокс -------
    def _on_x_slider(self, v):
        if self.pos_x.value() != v:
            self.pos_x.blockSignals(True)
            self.pos_x.setValue(v)
            self.pos_x.blockSignals(False)
        self._preview_pos()

    def _on_x_spin(self, v):
        if self.pos_x_slider.value() != v:
            self.pos_x_slider.blockSignals(True)
            self.pos_x_slider.setValue(v)
            self.pos_x_slider.blockSignals(False)
        self._preview_pos()

    def _on_y_slider(self, v):
        if self.pos_y.value() != v:
            self.pos_y.blockSignals(True)
            self.pos_y.setValue(v)
            self.pos_y.blockSignals(False)
        self._preview_pos()

    def _on_y_spin(self, v):
        if self.pos_y_slider.value() != v:
            self.pos_y_slider.blockSignals(True)
            self.pos_y_slider.setValue(v)
            self.pos_y_slider.blockSignals(False)
        self._preview_pos()

    def _on_op_slider(self, v):
        if self.opacity_spin.value() != v:
            self.opacity_spin.blockSignals(True)
            self.opacity_spin.setValue(v)
            self.opacity_spin.blockSignals(False)
        self._preview_opacity()

    def _on_op_spin(self, v):
        if self.opacity_slider.value() != v:
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(v)
            self.opacity_slider.blockSignals(False)
        self._preview_opacity()

    def _preview_pos(self):
        if self._on_preview_pos is not None:
            self._on_preview_pos(self.pos_x.value(), self.pos_y.value())

    def _preview_opacity(self):
        if self._on_preview_opacity is not None:
            self._on_preview_opacity(self.opacity_spin.value() / 100.0)

    def _toggle_sounds(self, checked):
        self._sounds_container.setVisible(checked)
        self.sounds_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)         # type: ignore

    # ------- загрузка состояния -------
    def reload(self, cfg):
        self._cfg = deepcopy(cfg)
        bat = self._cfg.setdefault("battery", {})
        bat["devices"] = _normalize_devices_list(bat.get("devices", []))

        self.low_spin.setValue(int(bat.get("low_threshold", 20)))
        self.full_spin.setValue(int(bat.get("full_threshold", 100)))
        self.interval_spin.setValue(int(bat.get("poll_interval", 60)))

        pos = bat.get("overlay_pos", [20, 20])
        self.pos_x_slider.setValue(int(pos[0]))
        self.pos_y_slider.setValue(int(pos[1]))
        self._saved_pos = (int(pos[0]), int(pos[1]))

        opacity = float(self._cfg.get("overlay_opacity", 1.0))
        op_pct = max(5, min(100, int(round(opacity * 100))))
        self.opacity_slider.setValue(op_pct)

        self.show_overlay_cb.setChecked(bool(self._cfg.get("show_overlay", True)))

        for key, ed in self._sound_editors.items():
            ed.set_spec(self._cfg.get("sounds", {}).get(key, {}))

        self._rebuild_rows()

        if not self._initial_bt_refresh_done:
            self._initial_bt_refresh_done = True
            QTimer.singleShot(50, self._do_bt_refresh)

    def _do_bt_refresh(self):
        snap = self._snapshot_devices()
        self._bt_devices_cache = list_bluetooth_devices()
        self._rebuild_rows(snap)

    def _refresh_bt_clicked(self):
        snap = self._snapshot_devices()
        self._bt_devices_cache = list_bluetooth_devices()
        self._rebuild_rows(snap)

    # ------- строки устройств -------
    def _snapshot_devices(self):
        snap = {}
        for row in self._device_rows:
            snap[row["id"]] = {
                "enabled": row["cb"].isChecked(),
                "type": row["type_combo"].currentData(),
            }
        return snap

    def _clear_rows(self):
        while self._dev_layout.count():
            item = self._dev_layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._device_rows = []

    def _rebuild_rows(self, snapshot=None):
        if snapshot is None:
            snapshot = self._snapshot_devices()
        self._clear_rows()
        cfg_devices = self._cfg.get("battery", {}).get("devices", [])

        aula_cfg = next((d for d in cfg_devices if d.get("source") == "aula"), None)
        if aula_cfg is not None:
            self._add_row(
                device_id="aula",
                source="aula",
                bluetooth_name=None,
                label="Клавиатура (AULA)",
                state=snapshot.get("aula", {
                    "enabled": aula_cfg.get("enabled", True),
                    "type": aula_cfg.get("type", "keyboard"),
                }),
            )

        seen = set()
        bt_items = []
        for d in cfg_devices:
            if d.get("source") == "bluetooth":
                bt = d.get("bluetooth_name", "")
                if bt and bt not in seen:
                    seen.add(bt)
                    bt_items.append((bt, d))
        for bt in self._bt_devices_cache:
            if bt not in seen:
                seen.add(bt)
                bt_items.append((bt, None))

        for bt, dcfg in bt_items:
            state = snapshot.get(f"bt:{bt}")
            if state is None and dcfg is not None:
                state = {
                    "enabled": dcfg.get("enabled", True),
                    "type": dcfg.get("type", "generic"),
                }
            if state is None:
                state = {"enabled": False, "type": "generic"}
            self._add_row(
                device_id=f"bt:{bt}",
                source="bluetooth",
                bluetooth_name=bt,
                label=bt,
                state=state,
            )

    def _add_row(self, device_id, source, bluetooth_name, label, state):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 1, 0, 1)
        cb = QCheckBox(label)
        cb.setChecked(bool(state.get("enabled", False)))
        h.addWidget(cb, 1)
        tc = QComboBox()
        for k, lbl in DEVICE_TYPE_LABELS.items():
            tc.addItem(lbl, k)
        idx = tc.findData(state.get("type", "generic"))
        if idx >= 0:
            tc.setCurrentIndex(idx)
        h.addWidget(tc)
        self._dev_layout.addWidget(w)
        self._device_rows.append({
            "id": device_id, "source": source,
            "bluetooth_name": bluetooth_name,
            "widget": w, "cb": cb, "type_combo": tc,
        })

    # ------- сбор/сохранение -------
    def _collect(self):
        cfg = deepcopy(self._cfg)
        bat = cfg.setdefault("battery", {})
        bat["low_threshold"] = self.low_spin.value()
        bat["full_threshold"] = self.full_spin.value()
        bat["poll_interval"] = self.interval_spin.value()
        bat["overlay_pos"] = [self.pos_x.value(), self.pos_y.value()]
        cfg["show_overlay"] = self.show_overlay_cb.isChecked()
        cfg["overlay_opacity"] = self.opacity_spin.value() / 100.0

        devices = []
        for row in self._device_rows:
            d = {
                "source": row["source"],
                "type": row["type_combo"].currentData(),
                "enabled": row["cb"].isChecked(),
            }
            if row["source"] == "bluetooth":
                d["bluetooth_name"] = row["bluetooth_name"]
            devices.append(d)
        bat["devices"] = devices

        # --- звуки: сохраняем dict-формат, не строки ---
        sounds = cfg.setdefault("sounds", {})
        old_sounds = self._cfg.get("sounds", {})
        for key, ed in self._sound_editors.items():
            sounds[key] = ed.get_spec(old_sounds.get(key))

        return cfg

    def _save(self):
        try:
            new_cfg = self._collect()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        if not self._on_save(new_cfg):
            return
        self._cfg = deepcopy(new_cfg)
        self._saved_pos = (self.pos_x.value(), self.pos_y.value())
        self.save_btn.setText("Сохранено ✓")
        QTimer.singleShot(1500, lambda: self.save_btn.setText("Сохранить"))

    def _close(self):
        if self._on_preview_pos is not None:
            self._on_preview_pos(int(self._saved_pos[0]), int(self._saved_pos[1]))
        self.hide()

    def closeEvent(self, e):
        e.ignore()
        self._close()


# ------------------------------ Иконка трея ------------------------------
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

def _normalize_sound_spec(spec):
    """str → {file}; dict → копия как есть (не теряем freq/dur_ms/...)."""
    if isinstance(spec, dict):
        return dict(spec)
    return {"file": str(spec) if spec else ""}

def reload_sounds(sounds_cfg):
    """Применить новые настройки звуков на лету."""
    try:
        if hasattr(snd, "reset"):
            snd.reset()
        else:
            snd.shutdown(timeout=2)
            if hasattr(snd, "_wav"):
                snd._wav.clear()
    except Exception as e:
        print(f"shutdown/reset звука: {e}")
    try:
        snd.init(sounds_cfg, base_dir=__application_path,
                volume=1.0, logger=print)
    except Exception as e:
        print(f"init звука не удался: {e}")

# ------------------------------ Приложение ------------------------------
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Ошибка", "Системный трей недоступен.")
        return 1

    # --- звук: инициализируем РОВНО ОДИН РАЗ ---
    # Внутри beep_sound.py обычно открывается аудио-устройство, и повторный
    # init() не идемпотентен (падает). Поэтому при сохранении конфига
    # мы НЕ вызываем init повторно — только если секция sounds реально
    # изменилась, и всегда в try/except.
    try:
        snd.init(CFG["sounds"], base_dir=__application_path, volume=1, logger=print)
    except Exception as e:
        print(f"Не удалось инициализировать звук: {e}")

    pos0 = CFG.get("battery", {}).get("overlay_pos", [20, 20])
    opacity0 = float(CFG.get("overlay_opacity", 1.0))

    runtime = {
        "cfg": CFG,
        "devices": build_devices(CFG),
        "low": int(CFG.get("battery", {}).get("low_threshold", 20)),
        "full": int(CFG.get("battery", {}).get("full_threshold", 100)),
        "interval": int(CFG.get("battery", {}).get("poll_interval", 60)),
        "poller": None,
    }

    levels = {d["key"]: None for d in runtime["devices"]}
    states = {d["key"]: "unknown" for d in runtime["devices"]}
    overlay_state = {"visible": bool(CFG.get("show_overlay", True))}
    quitting = {"flag": False}

    overlay = BatteryRowOverlay(
        runtime["devices"], (int(pos0[0]), int(pos0[1])),
        runtime["low"], opacity0,
    )
    overlay.setVisible(overlay_state["visible"])

    tray = QSystemTrayIcon()
    tray.setIcon(QIcon(make_tray_pixmap(None, runtime["low"], runtime["full"])))
    tray.setToolTip("Battery monitor")

    def preview_pos(x, y):
        overlay.move(int(x), int(y))

    def preview_opacity(op):
        overlay.set_opacity(float(op))

    def quit_app():
        if quitting["flag"]:
            return
        quitting["flag"] = True
        if runtime["poller"] is not None:
            try:
                runtime["poller"].stop()
            except Exception:
                pass
        overlay.hide()
        tray.hide()
        try:
            snd.play_sync("exit")
        except Exception:
            pass
        app.quit()

    def toggle_overlay(checked: bool):
        overlay_state["visible"] = bool(checked)
        overlay.setVisible(bool(checked))
        tray.setContextMenu(build_menu())

    def open_settings():
        settings_window.reload(runtime["cfg"])
        settings_window.show()
        settings_window.raise_()
        settings_window.activateWindow()

    def build_menu():
        m = QMenu()
        for d in runtime["devices"]:
            k = d["key"]
            lvl = levels.get(k)
            st = states.get(k, "unknown")
            if lvl is None:
                txt = f"{d['label']}: —"
            else:
                mark = "  ⚠" if st == "low" else ("  ✓" if st == "full" else "")
                txt = f"{d['label']}: {lvl}%{mark}"
            a = QAction(txt, m); a.setEnabled(False); m.addAction(a)
        m.addSeparator()
        show_a = QAction("Показывать батареи", m)
        show_a.setCheckable(True)
        show_a.setChecked(overlay_state["visible"])
        show_a.toggled.connect(toggle_overlay)
        m.addAction(show_a)
        settings_a = QAction("Настройки…", m)
        settings_a.triggered.connect(open_settings)
        m.addAction(settings_a)
        m.addSeparator()
        q = QAction("Выход", m); q.triggered.connect(quit_app); m.addAction(q)
        return m

    def refresh_tray():
        vals: list[int] = []
        for d in runtime["devices"]:
            lvl = levels.get(d["key"])
            if lvl is not None:
                vals.append(lvl)
        worst = min(vals) if vals else None
        tray.setIcon(QIcon(make_tray_pixmap(worst, runtime["low"], runtime["full"])))
        parts = [
            f"{d['label']}: " + ("—" if levels.get(d["key"]) is None
                                 else f"{levels[d['key']]}%")
            for d in runtime["devices"]
        ]
        tray.setToolTip(" | ".join(parts))
        tray.setContextMenu(build_menu())

    def on_update(new_levels: dict):
        for d in runtime["devices"]:
            k = d["key"]
            lvl = new_levels.get(k)
            prev = states.get(k, "unknown")
            if lvl is None: new_state = "unknown"
            elif lvl <= runtime["low"]: new_state = "low"
            elif lvl >= runtime["full"]: new_state = "full"
            else: new_state = "ok"
            if prev not in ("unknown", new_state):
                try:
                    if new_state == "low": snd.play(d["low_sound"])
                    elif new_state == "full": snd.play(d["full_sound"])
                except Exception as e:
                    print(f"Ошибка звука ({k}): {e}")
            states[k] = new_state
            levels[k] = lvl
        overlay.update_levels(levels)
        refresh_tray()

    def apply_new_config(new_cfg) -> bool:
        try:
            save_config(new_cfg)
        except Exception as e:
            QMessageBox.warning(None, "Ошибка",
                                f"Не удалось сохранить конфиг:\n{e}")
            return False

        old_sounds = runtime["cfg"].get("sounds", {})
        new_sounds = new_cfg.get("sounds", {})

        runtime["cfg"] = new_cfg
        runtime["low"] = int(new_cfg.get("battery", {}).get("low_threshold", 20))
        runtime["full"] = int(new_cfg.get("battery", {}).get("full_threshold", 100))
        runtime["interval"] = int(new_cfg.get("battery", {}).get("poll_interval", 60))
        runtime["devices"] = build_devices(new_cfg)

        levels.clear(); levels.update({d["key"]: None for d in runtime["devices"]})
        states.clear(); states.update({d["key"]: "unknown" for d in runtime["devices"]})

        pos = new_cfg.get("battery", {}).get("overlay_pos", [20, 20])
        overlay.set_devices(runtime["devices"])
        overlay.set_low_threshold(runtime["low"])
        overlay.move(int(pos[0]), int(pos[1]))
        overlay.set_opacity(float(new_cfg.get("overlay_opacity", 1.0)))
        overlay_state["visible"] = bool(new_cfg.get("show_overlay", True))
        overlay.setVisible(overlay_state["visible"])

        # Звук не переинициализируем — устройство уже открыто, повторный
        # snd.init() падает. Новые имена файлов подхватятся при следующем
        # запуске программы.
        if old_sounds != new_sounds:
            reload_sounds(new_sounds)

        if runtime["poller"] is not None:
            runtime["poller"].stop()
        runtime["poller"] = BatteryPoller(runtime["devices"], runtime["interval"])
        runtime["poller"].updated.connect(on_update)
        runtime["poller"].start()

        refresh_tray()
        return True

    settings_window = SettingsWindow(
        CFG, apply_new_config, preview_pos, preview_opacity,
    )

    runtime["poller"] = BatteryPoller(runtime["devices"], runtime["interval"])
    runtime["poller"].updated.connect(on_update)

    refresh_tray()
    tray.show()
    runtime["poller"].start()
    settings_window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())