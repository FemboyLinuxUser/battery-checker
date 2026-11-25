"""Сборка описаний устройств и эффективный цикл их опроса."""

import logging

log = logging.getLogger(__name__)

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
            out.append(
                {
                    "source": "bluetooth",
                    "bluetooth_name": dcfg["bluetooth_name"],
                    "type": "headphones",
                    "enabled": True,
                }
            )
        elif key == "aula":
            out.append({"source": "aula", "type": "keyboard", "enabled": True})
    return out


def _aula_getter():
    from aula_battery import get_battery_level

    return get_battery_level()


def _bt_getter(name):
    def get():
        from bt_battery_ctypes import get_bluetooth_battery_level

        return get_bluetooth_battery_level(name)

    return get


def build_devices(cfg):
    devices = []
    used_keys = set()
    raw = cfg.get("battery", {}).get("devices", [])
    for dcfg in _normalize_devices_list(raw):
        if not isinstance(dcfg, dict) or not dcfg.get("enabled", True):
            continue
        source = dcfg.get("source")
        dev_type = dcfg.get("type", "generic")

        if source == "aula":
            key = "aula"
            getter = _aula_getter
            label = DEVICE_TYPE_LABELS.get(dev_type, "Устройство")
            low_s, full_s = "low_aula", "full_aula"
        elif source == "bluetooth":
            bt_name = dcfg.get("bluetooth_name", "")
            if not bt_name:
                continue
            key = f"bt:{bt_name}"
            getter = _bt_getter(bt_name)
            label = bt_name
            low_s, full_s = "low_bt", "full_bt"
        else:
            continue

        base_key = key
        suffix = 2
        while key in used_keys:
            key = f"{base_key}#{suffix}"
            suffix += 1
        used_keys.add(key)

        devices.append(
            {
                "key": key,
                "source": source,
                "bluetooth_name": dcfg.get("bluetooth_name"),
                "type": dev_type,
                "label": label,
                "getter": getter,
                "low_sound": low_s,
                "full_sound": full_s,
            }
        )
    return devices


def _read_aula():
    try:
        from aula_battery import _find_path, get_battery_level

        present = _find_path() is not None
        return {"level": get_battery_level() if present else None, "present": present}
    except Exception as exc:
        log.debug("AULA недоступна: %s", exc)
        return {"level": None, "present": False}


def read_devices(devices):
    """
    Один цикл опроса. Bluetooth-имена матчатся одним проходом SetupAPI,
    а не перечислением всех устройств для каждого сконфигурированного имени.
    """
    result = {}
    bt_devices = [d for d in devices if d.get("source") == "bluetooth"]
    bt_names = [d.get("bluetooth_name") for d in bt_devices]

    bt_matches = {}
    if bt_names:
        try:
            from bt_battery_ctypes import match_devices

            bt_matches = match_devices(bt_names)
        except Exception as exc:
            log.warning("Ошибка перечисления Bluetooth-устройств: %s", exc)

    for dev in devices:
        if dev.get("source") == "bluetooth":
            data = bt_matches.get(dev.get("bluetooth_name"), {"level": None, "present": False})
            result[dev["key"]] = dict(data)
        elif dev.get("source") == "aula":
            result[dev["key"]] = _read_aula()
        else:
            try:
                result[dev["key"]] = {"level": dev["getter"](), "present": True}
            except Exception as exc:
                log.warning("[%s] ошибка опроса: %s", dev["key"], exc)
                result[dev["key"]] = {"level": None, "present": False}
    return result
