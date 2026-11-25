"""Автозапуск через HKCU\\...\\Run."""

import logging
import os
import sys

from config import __application_path

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "BatteryChecker"


def _command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    python = pythonw if os.path.exists(pythonw) else sys.executable
    main_py = os.path.join(__application_path, "main.py")
    return f'"{python}" "{main_py}"'


def is_enabled():
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(value)
    except FileNotFoundError:
        return False
    except Exception as exc:
        log.warning("Не удалось проверить автозапуск: %s", exc)
        return False


def set_enabled(enabled):
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as exc:
        log.warning("Не удалось изменить автозапуск: %s", exc)
        return False
