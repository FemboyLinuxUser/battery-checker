import copy
import logging
import os
import shutil
import sys
from logging.handlers import RotatingFileHandler

import yaml

APP_NAME = "battery-checker"

if getattr(sys, "frozen", False):
    __application_path = os.path.dirname(sys.executable)
    __BUILD = "1.0.0"
else:
    __application_path = os.path.dirname(os.path.abspath(__file__))
    __BUILD = "test"


def _config_root():
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if not base:
            base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(base, APP_NAME)


CONFIG_DIR = _config_root()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.yaml")
LOG_PATH = os.path.join(CONFIG_DIR, "battery-checker.log")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.db")
LEGACY_CONFIG_PATH = os.path.join(__application_path, "config.yaml")

DEFAULT_CONFIG = {
    "show_overlay": True,
    "overlay_opacity": 1.0,
    "autostart": False,
    "sounds": {
        "low_aula": {"freq": 500, "dur_ms": 30, "count": 5, "gap_ms": 60},
        "full_aula": {"freq": 1000, "dur_ms": 100, "count": 2, "gap_ms": 0},
        "low_bt": {"freq": 500, "dur_ms": 30, "count": 5, "gap_ms": 60},
        "full_bt": {"freq": 1000, "dur_ms": 100, "count": 2, "gap_ms": 0},
        "exit": {"freq": 1500, "dur_ms": 100, "count": 3, "gap_ms": 0},
    },
    "battery": {
        "low_threshold": 20,
        "full_threshold": 100,
        "poll_interval": 60,
        "low_repeat_step": 5,
        "overlay_pos": [20, 20],
        "devices": [],
    },
    "history": {
        "retention_days": 90,
        "unchanged_write_minutes": 5,
    },
}

log = logging.getLogger(__name__)


def _deep_merge(base, override):
    result = dict(base)
    for k, v in (override or {}).items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _merge_sound_specs(default_sounds, user_sounds):
    """Tone-дефолты не должны маскировать явно выбранный WAV-файл."""
    merged = _deep_merge(default_sounds, user_sounds)
    if not isinstance(user_sounds, dict):
        return merged
    for key, spec in user_sounds.items():
        if isinstance(spec, dict) and "file" in spec:
            merged[key] = dict(spec)
    return merged


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _migrate_legacy_config():
    if os.path.exists(CONFIG_PATH) or not os.path.exists(LEGACY_CONFIG_PATH):
        return
    if os.path.abspath(LEGACY_CONFIG_PATH) == os.path.abspath(CONFIG_PATH):
        return
    try:
        shutil.copy2(LEGACY_CONFIG_PATH, CONFIG_PATH)
        log.info("Перенесён старый конфиг %s -> %s", LEGACY_CONFIG_PATH, CONFIG_PATH)
    except Exception as exc:
        log.warning("Не удалось перенести старый конфиг: %s", exc)


def sanitize_config_sections(cfg):
    """Заменяет malformed top-level секции дефолтами, не трогая валидные значения."""
    sanitized = copy.deepcopy(cfg)
    for section in ("battery", "sounds", "history"):
        if not isinstance(sanitized.get(section), dict):
            sanitized[section] = copy.deepcopy(DEFAULT_CONFIG[section])
    return sanitized


def load_config():
    ensure_config_dir()
    _migrate_legacy_config()
    if not os.path.exists(CONFIG_PATH):
        try:
            save_config(DEFAULT_CONFIG)
            log.info("Создан конфиг %s", CONFIG_PATH)
        except Exception as exc:
            log.warning("Не смог создать %s: %s", CONFIG_PATH, exc)
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    except Exception as exc:
        log.warning("Ошибка чтения %s: %s. Используются дефолты.", CONFIG_PATH, exc)
        return copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(user, dict):
        log.warning("Конфиг %s должен содержать YAML-объект. Используются дефолты.", CONFIG_PATH)
        return copy.deepcopy(DEFAULT_CONFIG)
    merged = _deep_merge(DEFAULT_CONFIG, user)
    if isinstance(user.get("sounds"), dict):
        merged["sounds"] = _merge_sound_specs(DEFAULT_CONFIG["sounds"], user["sounds"])
    errors = validate_config(merged)
    if errors:
        log.warning("Конфиг содержит ошибки: %s", "; ".join(errors))
    return sanitize_config_sections(merged)


def save_config(cfg, path=None):
    ensure_config_dir()
    if path is None:
        path = CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            cfg,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_config(cfg):
    """Возвращает список понятных ошибок конфигурации."""
    errors = []
    if not isinstance(cfg, dict):
        return ["конфиг должен быть объектом"]

    battery = cfg.get("battery")
    if not isinstance(battery, dict):
        errors.append("battery должен быть объектом")
        battery = {}

    low = battery.get("low_threshold")
    full = battery.get("full_threshold")
    interval = battery.get("poll_interval")
    repeat_step = battery.get("low_repeat_step", 5)
    pos = battery.get("overlay_pos")

    if not _is_number(low) or not 0 <= low <= 100:
        errors.append("battery.low_threshold должен быть числом от 0 до 100")
    if not _is_number(full) or not 0 <= full <= 100:
        errors.append("battery.full_threshold должен быть числом от 0 до 100")
    if _is_number(low) and _is_number(full) and low >= full:
        errors.append("battery.low_threshold должен быть меньше battery.full_threshold")
    if not _is_number(interval) or interval < 5:
        errors.append("battery.poll_interval должен быть числом не меньше 5")
    if not _is_number(repeat_step) or not 1 <= repeat_step <= 100:
        errors.append("battery.low_repeat_step должен быть числом от 1 до 100")
    if (
        not isinstance(pos, (list, tuple))
        or len(pos) != 2
        or not all(_is_number(v) for v in pos)
    ):
        errors.append("battery.overlay_pos должен быть списком из двух чисел")

    devices = battery.get("devices", [])
    if not isinstance(devices, list):
        errors.append("battery.devices должен быть списком")
    else:
        for i, dev in enumerate(devices):
            if not isinstance(dev, dict):
                errors.append(f"battery.devices[{i}] должен быть объектом")
                continue
            if dev.get("source") not in ("aula", "bluetooth"):
                errors.append(f"battery.devices[{i}].source должен быть aula или bluetooth")
            if dev.get("source") == "bluetooth" and not dev.get("bluetooth_name"):
                errors.append(f"battery.devices[{i}].bluetooth_name не должен быть пустым")

    sounds = cfg.get("sounds", {})
    if not isinstance(sounds, dict):
        errors.append("sounds должен быть объектом")
    else:
        for key, spec in sounds.items():
            if not isinstance(spec, (dict, str)):
                errors.append(f"sounds.{key} должен быть объектом или именем файла")

    opacity = cfg.get("overlay_opacity", 1.0)
    if not _is_number(opacity) or not 0.05 <= opacity <= 1.0:
        errors.append("overlay_opacity должен быть числом от 0.05 до 1.0")

    history = cfg.get("history", {})
    if not isinstance(history, dict):
        errors.append("history должен быть объектом")
    else:
        retention = history.get("retention_days", 90)
        unchanged = history.get("unchanged_write_minutes", 5)
        if not _is_number(retention) or retention < 1:
            errors.append("history.retention_days должен быть числом не меньше 1")
        if not _is_number(unchanged) or unchanged < 1:
            errors.append("history.unchanged_write_minutes должен быть числом не меньше 1")

    return errors


def assert_valid_config(cfg):
    errors = validate_config(cfg)
    if errors:
        raise ValueError("Некорректный конфиг:\n" + "\n".join(f"• {e}" for e in errors))


def setup_logging():
    ensure_config_dir()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(fmt)
    root.addHandler(stderr_handler)
    return LOG_PATH
