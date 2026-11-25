import logging

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu, QMessageBox, QSystemTrayIcon

import autostart
import beep_sound as snd
from config import __application_path as application_path, save_config, validate_config
from devices import build_devices
from history import BatteryHistory
from logic import as_mapping, evaluate_device_update, float_or, int_or, position_or
from overlay import BatteryRowOverlay
from poller import BatteryPoller
from settings import HistoryWindow, SettingsWindow
from tray import make_tray_pixmap

log = logging.getLogger(__name__)


def reload_sounds(sounds_cfg):
    try:
        if hasattr(snd, "reset"):
            snd.reset()
        else:
            snd.shutdown(timeout=2)
            if hasattr(snd, "_wav"):
                snd._wav.clear()
    except Exception as exc:
        log.warning("shutdown/reset звука: %s", exc)
    try:
        snd.init(sounds_cfg, base_dir=application_path, volume=1.0, logger=log.info)
    except Exception as exc:
        log.warning("init звука не удался: %s", exc)


class AppController:
    def __init__(self, app, cfg):
        self.app = app
        self.cfg = cfg
        battery_cfg = as_mapping(cfg.get("battery"))
        self.low = int_or(battery_cfg.get("low_threshold", 20), 20)
        self.full = int_or(battery_cfg.get("full_threshold", 100), 100)
        self.interval = int_or(battery_cfg.get("poll_interval", 60), 60)
        self.low_repeat_step = int_or(battery_cfg.get("low_repeat_step", 5), 5)
        self.devices = build_devices(cfg)
        self.levels = {d["key"]: None for d in self.devices}
        self.states = {d["key"]: "unknown" for d in self.devices}
        self.disconnected = {d["key"]: False for d in self.devices}
        self.last_notified_level = {d["key"]: None for d in self.devices}
        self.poller = None
        self.quitting = False
        self.history_window = None

        history_cfg = as_mapping(cfg.get("history"))
        self.history = BatteryHistory(
            retention_days=int_or(history_cfg.get("retention_days", 90), 90),
            unchanged_write_minutes=int_or(history_cfg.get("unchanged_write_minutes", 5), 5),
        )

        try:
            snd.init(as_mapping(cfg.get("sounds")), base_dir=application_path, volume=1, logger=log.info)
        except Exception as exc:
            log.warning("Не удалось инициализировать звук: %s", exc)

        pos0 = position_or(battery_cfg.get("overlay_pos", [20, 20]))
        opacity0 = float_or(cfg.get("overlay_opacity", 1.0), 1.0)
        self.overlay_state = {"visible": bool(cfg.get("show_overlay", True))}
        self.overlay = BatteryRowOverlay(
            self.devices,
            (pos0[0], pos0[1]),
            self.low,
            opacity0,
        )
        self.overlay.setVisible(self.overlay_state["visible"])

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon(make_tray_pixmap(None, self.low, self.full)))
        self.tray.setToolTip("Battery monitor")

        self.settings_window = SettingsWindow(
            cfg,
            self.apply_new_config,
            self.preview_pos,
            self.preview_opacity,
            self.open_history,
        )
        self.refresh_tray()

    def run(self):
        self.tray.show()
        self.start_poller()
        self.settings_window.show()
        return self.app.exec_()

    def start_poller(self):
        self.poller = BatteryPoller(self.devices, self.interval)
        self.poller.updated.connect(self.on_update)
        self.poller.start()

    def preview_pos(self, x, y):
        self.overlay.move(int(x), int(y))

    def preview_opacity(self, op):
        self.overlay.set_opacity(float(op))

    def quit_app(self):
        if self.quitting:
            return
        self.quitting = True
        if self.poller is not None:
            try:
                self.poller.stop()
            except Exception:
                log.exception("Ошибка остановки poller")
        self.overlay.hide()
        self.tray.hide()
        try:
            snd.play_sync("exit")
        except Exception:
            log.exception("Ошибка exit-звука")
        try:
            self.history.close()
        except Exception:
            pass
        self.app.quit()

    def toggle_overlay(self, checked: bool):
        self.overlay_state["visible"] = bool(checked)
        self.overlay.setVisible(bool(checked))
        self.tray.setContextMenu(self.build_menu())

    def open_settings(self):
        self.settings_window.reload(self.cfg)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def open_history(self):
        if self.history_window is None:
            self.history_window = HistoryWindow(self.devices, self.history)
        else:
            self.history_window._refresh()
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def _level_text(self, device):
        key = device["key"]
        if self.disconnected.get(key):
            return "отключено"
        lvl = self.levels.get(key)
        return "—" if lvl is None else f"{lvl}%"

    def build_menu(self):
        menu = QMenu()
        for device in self.devices:
            key = device["key"]
            state = self.states.get(key, "unknown")
            txt = f"{device['label']}: {self._level_text(device)}"
            if state == "low":
                txt += "  ⚠"
            elif state == "full":
                txt += "  ✓"
            action = QAction(txt, menu)
            action.setEnabled(False)
            menu.addAction(action)
        menu.addSeparator()
        show_action = QAction("Показывать батареи", menu)
        show_action.setCheckable(True)
        show_action.setChecked(self.overlay_state["visible"])
        show_action.toggled.connect(self.toggle_overlay)
        menu.addAction(show_action)
        settings_action = QAction("Настройки…", menu)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        quit_action = QAction("Выход", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        return menu

    def refresh_tray(self):
        vals = []
        for device in self.devices:
            lvl = self.levels.get(device["key"])
            if lvl is not None:
                vals.append(lvl)
        worst = min(vals) if vals else None
        self.tray.setIcon(QIcon(make_tray_pixmap(worst, self.low, self.full)))
        parts = [f"{d['label']}: {self._level_text(d)}" for d in self.devices]
        self.tray.setToolTip(" | ".join(parts))
        self.tray.setContextMenu(self.build_menu())

    def _notify_tray(self, device, state, level):
        if not self.tray.supportsMessages():
            return
        if state == "low":
            title = "Низкий заряд"
            icon = QSystemTrayIcon.Warning
        else:
            title = "Батарея заряжена"
            icon = QSystemTrayIcon.Information
        self.tray.showMessage(title, f"{device['label']}: {level}%", icon, 5000)

    def on_update(self, poll_result: dict):
        for device in self.devices:
            key = device["key"]
            data = poll_result.get(key)
            if isinstance(data, dict):
                lvl = data.get("level")
                present = bool(data.get("present", lvl is not None))
            else:
                lvl = data
                present = lvl is not None

            prev = self.states.get(key, "unknown")
            if lvl is None and not present:
                new_state = "disconnected"
                event = None
                new_last = None
            else:
                new_state, event, new_last = evaluate_device_update(
                    prev if prev != "disconnected" else "unknown",
                    lvl,
                    self.low,
                    self.full,
                    self.low_repeat_step,
                    self.last_notified_level.get(key),
                )

            if event in ("low", "full"):
                try:
                    sound_key = device["low_sound"] if event == "low" else device["full_sound"]
                    snd.play(sound_key)
                except Exception as exc:
                    log.warning("Ошибка звука (%s): %s", key, exc)
                if lvl is not None:
                    self._notify_tray(device, event, lvl)

            self.states[key] = new_state
            self.levels[key] = lvl
            self.disconnected[key] = lvl is None and not present
            self.last_notified_level[key] = new_last
            if lvl is not None:
                try:
                    self.history.record(key, device["label"], lvl)
                except Exception as exc:
                    log.warning("Не удалось записать историю %s: %s", key, exc)

        self.overlay.update_levels(self.levels)
        self.refresh_tray()

    def apply_new_config(self, new_cfg) -> bool:
        errors = validate_config(new_cfg)
        if errors:
            QMessageBox.warning(
                self.settings_window,
                "Некорректный конфиг",
                "\n".join(f"• {e}" for e in errors),
            )
            return False
        try:
            save_config(new_cfg)
        except Exception as exc:
            QMessageBox.warning(None, "Ошибка", f"Не удалось сохранить конфиг:\n{exc}")
            return False

        old_sounds = self.cfg.get("sounds", {})
        new_sounds = new_cfg.get("sounds", {})

        self.cfg = new_cfg
        battery = new_cfg.get("battery", {})
        self.low = int(battery.get("low_threshold", 20))
        self.full = int(battery.get("full_threshold", 100))
        self.interval = int(battery.get("poll_interval", 60))
        self.low_repeat_step = int(battery.get("low_repeat_step", 5))
        self.devices = build_devices(new_cfg)

        self.levels = {d["key"]: None for d in self.devices}
        self.states = {d["key"]: "unknown" for d in self.devices}
        self.disconnected = {d["key"]: False for d in self.devices}
        self.last_notified_level = {d["key"]: None for d in self.devices}

        pos = battery.get("overlay_pos", [20, 20])
        self.overlay.set_devices(self.devices)
        self.overlay.set_low_threshold(self.low)
        self.overlay.move(int(pos[0]), int(pos[1]))
        self.overlay.set_opacity(float(new_cfg.get("overlay_opacity", 1.0)))
        self.overlay_state["visible"] = bool(new_cfg.get("show_overlay", True))
        self.overlay.setVisible(self.overlay_state["visible"])

        if old_sounds != new_sounds:
            reload_sounds(new_sounds)

        if bool(new_cfg.get("autostart", False)) != autostart.is_enabled():
            if not autostart.set_enabled(bool(new_cfg.get("autostart", False))):
                log.warning("Автозапуск не удалось применить")

        if self.poller is not None:
            self.poller.stop()
        self.start_poller()

        if self.history_window is not None:
            self.history_window.close()
            self.history_window = None

        self.refresh_tray()
        return True
