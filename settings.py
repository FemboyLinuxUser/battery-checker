import logging
import time
from copy import deepcopy
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QSpinBox, QCheckBox,
    QComboBox, QPushButton, QToolButton, QGroupBox, QFormLayout,
    QHBoxLayout, QVBoxLayout, QMessageBox, QScrollArea, QSlider,
    QStackedWidget,
)

from bt_battery_ctypes import list_all_battery_devices, list_bluetooth_devices
from devices import DEVICE_TYPE_LABELS, _normalize_devices_list
from logic import _normalize_sound_spec, as_mapping

log = logging.getLogger(__name__)


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

class HistoryGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self._start = 0
        self._end = 1
        self.setMinimumHeight(220)

    def set_points(self, points, start, end):
        self._points = list(points)
        self._start = start
        self._end = max(end, start + 1)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        left, top, right, bottom = 36, 12, 12, 24
        pw = max(1, w - left - right)
        ph = max(1, h - top - bottom)

        p.fillRect(self.rect(), QColor(35, 35, 35))
        p.setPen(QPen(QColor(90, 90, 90), 1))
        for level in (0, 25, 50, 75, 100):
            y = top + ph - ph * level / 100.0
            p.drawLine(left, int(y), left + pw, int(y))
            p.setPen(QPen(QColor(180, 180, 180), 1))
            p.drawText(4, int(y + 4), f"{level}%")
            p.setPen(QPen(QColor(90, 90, 90), 1))

        if len(self._points) < 2:
            p.setPen(QPen(QColor(220, 220, 220), 1))
            p.drawText(QRectF(left, top, pw, ph), Qt.AlignCenter, "Недостаточно данных")
            return

        def xy(ts, level):
            x = left + pw * (ts - self._start) / (self._end - self._start)
            y = top + ph - ph * level / 100.0
            return int(x), int(y)

        p.setPen(QPen(QColor(80, 170, 255), 2))
        last_x, last_y = xy(*self._points[0])
        for ts, level in self._points[1:]:
            x, y = xy(ts, level)
            p.drawLine(last_x, last_y, x, y)
            last_x, last_y = x, y

        p.setPen(QPen(QColor(180, 180, 180), 1))
        fmt = "%d.%m %H:%M"
        p.drawText(left, h - 6, datetime.fromtimestamp(self._start).strftime(fmt))
        end_text = datetime.fromtimestamp(self._end).strftime(fmt)
        p.drawText(left + pw - 90, h - 6, end_text)


class HistoryWindow(QWidget):
    def __init__(self, devices, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История разряда")
        self.setMinimumSize(620, 300)
        self._devices = devices
        self._history = history

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Устройство:"))
        self.device_combo = QComboBox()
        for dev in devices:
            self.device_combo.addItem(dev["label"], dev["key"])
        controls.addWidget(self.device_combo, 1)
        controls.addWidget(QLabel("Диапазон:"))
        self.range_combo = QComboBox()
        self.range_combo.addItem("Сутки", 86400)
        self.range_combo.addItem("Неделя", 7 * 86400)
        self.range_combo.addItem("Месяц", 30 * 86400)
        controls.addWidget(self.range_combo)
        layout.addLayout(controls)

        self.graph = HistoryGraph()
        layout.addWidget(self.graph)

        self.device_combo.currentIndexChanged.connect(self._refresh)
        self.range_combo.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        key = self.device_combo.currentData()
        if not key:
            self.graph.set_points([], 0, 1)
            return
        seconds = int(self.range_combo.currentData())
        end = time.time()
        start = end - seconds
        rows = self._history.samples(key, start)
        self.graph.set_points([(float(ts), int(level)) for ts, level in rows], start, end)


class BluetoothDevicesWorker(QThread):
    scan_finished = pyqtSignal(object, object)

    def run(self):
        try:
            names = list_bluetooth_devices()
        except Exception as exc:
            log.warning("Не удалось получить список Bluetooth-устройств: %s", exc)
            names = []
        try:
            battery_devices = list_all_battery_devices()
        except Exception as exc:
            log.warning("Не удалось получить battery-свойства: %s", exc)
            battery_devices = []
        self.scan_finished.emit(names, battery_devices)


class SettingsWindow(QWidget):
    def __init__(self, cfg, on_save, on_preview_pos, on_preview_opacity, on_open_history=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Battery Monitor — Настройки")
        self.setMinimumWidth(600)
        self._on_save = on_save
        self._on_preview_pos = on_preview_pos
        self._on_preview_opacity = on_preview_opacity
        self._on_open_history = on_open_history
        self._cfg = deepcopy(cfg)
        self._cfg["battery"] = as_mapping(self._cfg.get("battery"))
        self._cfg["sounds"] = as_mapping(self._cfg.get("sounds"))
        self._device_rows = []
        self._bt_devices_cache = []
        self._bt_battery_names = set()
        self._bt_worker = None
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
        self.repeat_step_spin = QSpinBox(); self.repeat_step_spin.setRange(1, 100); self.repeat_step_spin.setSuffix(" %")

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
        self.autostart_cb = QCheckBox("Запускать с Windows")

        bat_form.addRow("Нижний порог (красный):", self.low_spin)
        bat_form.addRow("Верхний порог (полный):", self.full_spin)
        bat_form.addRow("Интервал опроса:", self.interval_spin)
        bat_form.addRow("Повтор low-звука через падение:", self.repeat_step_spin)
        bat_form.addRow("Позиция X:", pos_x_row)
        bat_form.addRow("Позиция Y:", pos_y_row)
        bat_form.addRow("Прозрачность:", op_row)
        bat_form.addRow(self.show_overlay_cb)
        bat_form.addRow(self.autostart_cb)
        root.addWidget(bat_box)

        # --- devices ---
        dev_box = QGroupBox("Устройства")
        dev_v = QVBoxLayout(dev_box)
        top = QHBoxLayout()
        top.addWidget(QLabel("Отметьте устройства для отображения и выберите иконку."))
        top.addStretch()
        self.refresh_btn = QPushButton("Обновить список BT")
        self.refresh_btn.clicked.connect(self._refresh_bt_clicked)
        top.addWidget(self.refresh_btn)
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
        history_btn = QPushButton("История…")
        history_btn.clicked.connect(self._open_history)
        btn_row.addWidget(history_btn)
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

    def _open_history(self):
        if self._on_open_history is not None:
            self._on_open_history()

    def _toggle_sounds(self, checked):
        self._sounds_container.setVisible(checked)
        self.sounds_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)         # type: ignore

    # ------- загрузка состояния -------
    def reload(self, cfg):
        self._cfg = deepcopy(cfg)
        self._cfg["battery"] = as_mapping(self._cfg.get("battery"))
        self._cfg["sounds"] = as_mapping(self._cfg.get("sounds"))
        bat = self._cfg["battery"]
        bat["devices"] = _normalize_devices_list(bat.get("devices", []))

        self.low_spin.setValue(int(bat.get("low_threshold", 20)))
        self.full_spin.setValue(int(bat.get("full_threshold", 100)))
        self.interval_spin.setValue(int(bat.get("poll_interval", 60)))
        self.repeat_step_spin.setValue(int(bat.get("low_repeat_step", 5)))

        pos = bat.get("overlay_pos", [20, 20])
        self.pos_x_slider.setValue(int(pos[0]))
        self.pos_y_slider.setValue(int(pos[1]))
        self._saved_pos = (int(pos[0]), int(pos[1]))

        opacity = float(self._cfg.get("overlay_opacity", 1.0))
        op_pct = max(5, min(100, int(round(opacity * 100))))
        self.opacity_slider.setValue(op_pct)

        self.show_overlay_cb.setChecked(bool(self._cfg.get("show_overlay", True)))
        self.autostart_cb.setChecked(bool(self._cfg.get("autostart", False)))

        for key, ed in self._sound_editors.items():
            ed.set_spec(self._cfg.get("sounds", {}).get(key, {}))

        self._rebuild_rows()

        if not self._initial_bt_refresh_done:
            self._initial_bt_refresh_done = True
            QTimer.singleShot(50, self._do_bt_refresh)

    def _do_bt_refresh(self):
        if self._bt_worker is not None and self._bt_worker.isRunning():
            return
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Обновление…")
        self._bt_worker = BluetoothDevicesWorker(self)
        self._bt_worker.scan_finished.connect(self._bt_scan_done)
        self._bt_worker.start()

    def _bt_scan_done(self, names, battery_devices):
        self._bt_devices_cache = list(names)
        self._bt_battery_names = {str(name).lower() for name, _level in battery_devices}
        self._rebuild_rows(self._snapshot_devices())
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Обновить список BT")

    def _refresh_bt_clicked(self):
        self._do_bt_refresh()

    def _has_battery_property(self, bt_name):
        needle = bt_name.lower()
        return any(needle in name or name in needle for name in self._bt_battery_names)

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
        default_aula_state = (
            {
                "enabled": aula_cfg.get("enabled", True),
                "type": aula_cfg.get("type", "keyboard"),
            }
            if aula_cfg is not None
            else {"enabled": False, "type": "keyboard"}
        )
        self._add_row(
            device_id="aula",
            source="aula",
            bluetooth_name=None,
            label="Клавиатура (AULA)",
            state=snapshot.get("aula", default_aula_state),
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
            suffix = " — заряд доступен" if self._has_battery_property(bt) else " — заряд не найден"
            self._add_row(
                device_id=f"bt:{bt}",
                source="bluetooth",
                bluetooth_name=bt,
                label=bt + suffix,
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
        bat["low_repeat_step"] = self.repeat_step_spin.value()
        bat["overlay_pos"] = [self.pos_x.value(), self.pos_y.value()]
        cfg["show_overlay"] = self.show_overlay_cb.isChecked()
        cfg["autostart"] = self.autostart_cb.isChecked()
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
