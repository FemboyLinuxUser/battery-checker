"""Доступ к заряду Bluetooth-устройств через Windows SetupAPI."""

import ctypes
from ctypes import wintypes
import logging
import os
import uuid

log = logging.getLogger(__name__)

DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004

SPDRP_DEVICEDESC = 0x00000000
SPDRP_FRIENDLYNAME = 0x0000000C

DEVPROP_TYPE_BYTE = 0x00000003
DEVPROP_TYPE_UINT16 = 0x00000005
DEVPROP_TYPE_UINT32 = 0x00000007

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
BLUETOOTH_CLASS_GUID = "{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}"

if os.name == "nt":
    setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
else:
    setupapi = None


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, s):
        u = uuid.UUID(s)
        g = cls()
        g.Data1 = u.time_low
        g.Data2 = u.time_mid
        g.Data3 = u.time_hi_version
        g.Data4 = (ctypes.c_ubyte * 8)(*u.bytes[8:])
        return g


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [
        ("fmtid", GUID),
        ("pid", wintypes.DWORD),
    ]


if setupapi is not None:
    setupapi.SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.LPCWSTR,
        wintypes.HWND,
        wintypes.DWORD,
    ]
    setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE

    setupapi.SetupDiEnumDeviceInfo.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(SP_DEVINFO_DATA),
    ]
    setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL

    setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVINFO_DATA),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    setupapi.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

    setupapi.SetupDiGetDevicePropertyW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVINFO_DATA),
        ctypes.POINTER(DEVPROPKEY),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    setupapi.SetupDiGetDevicePropertyW.restype = wintypes.BOOL

    setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVINFO_DATA),
        ctypes.POINTER(ctypes.c_wchar),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL

    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL


BATTERY_DEVPKEY = DEVPROPKEY(
    fmtid=GUID.from_string("{104EA319-6EE2-4701-BD47-8DDBF425BBE5}"),
    pid=2,
)


def _get_registry_string(h, did, prop):
    buf = ctypes.create_unicode_buffer(1024)
    required = wintypes.DWORD(0)
    ptype = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDeviceRegistryPropertyW(
        h,
        ctypes.byref(did),
        prop,
        ctypes.byref(ptype),
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
        ctypes.sizeof(buf),
        ctypes.byref(required),
    )
    return buf.value if ok else None


def _get_friendly_name(h, did):
    return _get_registry_string(h, did, SPDRP_FRIENDLYNAME) or _get_registry_string(
        h, did, SPDRP_DEVICEDESC
    )


def _get_instance_id(h, did):
    buf = ctypes.create_unicode_buffer(1024)
    required = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDeviceInstanceIdW(
        h,
        ctypes.byref(did),
        buf,
        1024,
        ctypes.byref(required),
    )
    return buf.value if ok else ""


def _get_battery_prop(h, did):
    ptype = wintypes.DWORD(0)
    buf = (ctypes.c_ubyte * 8)()
    required = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDevicePropertyW(
        h,
        ctypes.byref(did),
        ctypes.byref(BATTERY_DEVPKEY),
        ctypes.byref(ptype),
        buf,
        ctypes.sizeof(buf),
        ctypes.byref(required),
        0,
    )
    if not ok:
        return None
    if ptype.value == DEVPROP_TYPE_BYTE:
        return buf[0]
    if ptype.value == DEVPROP_TYPE_UINT16:
        return int.from_bytes(bytes(buf[:2]), "little")
    if ptype.value == DEVPROP_TYPE_UINT32:
        return int.from_bytes(bytes(buf[:4]), "little")
    return None


def _open_devices(class_guid=None, flags=DIGCF_PRESENT | DIGCF_ALLCLASSES):
    if setupapi is None:
        return None
    guid = GUID.from_string(class_guid) if class_guid else None
    guid_ptr = ctypes.byref(guid) if guid is not None else None
    h = setupapi.SetupDiGetClassDevsW(guid_ptr, None, None, flags)
    if not h or h == INVALID_HANDLE_VALUE:
        return None
    return h


def _iter_devices(h):
    idx = 0
    while True:
        did = SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        if not setupapi.SetupDiEnumDeviceInfo(h, idx, ctypes.byref(did)):
            break
        yield did
        idx += 1


def scan_present_devices(class_guid=None, flags=DIGCF_PRESENT | DIGCF_ALLCLASSES):
    """Один проход по present-устройствам: имя, InstanceId и battery property."""
    h = _open_devices(class_guid, flags)
    if h is None:
        return []
    result = []
    try:
        for did in _iter_devices(h):
            result.append(
                {
                    "name": _get_friendly_name(h, did),
                    "instance_id": _get_instance_id(h, did),
                    "level": _get_battery_prop(h, did),
                }
            )
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(h)
    return result


def _matches(part, name):
    return bool(part and name) and part.lower() in name.lower()


def match_scanned_devices(names, scanned_devices):
    """Сопоставляет имена с уже полученным списком; точное совпадение важнее substring."""
    names = [str(n) for n in names if n]
    candidates = {
        name: {"present": False, "exact_level": None, "substring_level": None}
        for name in names
    }
    for dev in scanned_devices:
        fname = dev.get("name")
        if not fname:
            continue
        for name in names:
            if not _matches(name, fname):
                continue
            data = candidates[name]
            data["present"] = True
            level = dev.get("level")
            if level is None:
                continue
            if fname.lower() == name.lower():
                if data["exact_level"] is None:
                    data["exact_level"] = level
            elif data["substring_level"] is None:
                data["substring_level"] = level

    result = {}
    for name, data in candidates.items():
        level = data["exact_level"]
        if level is None:
            level = data["substring_level"]
        result[name] = {"present": data["present"], "level": level}
    return result


def match_devices(names):
    """
    Для каждого имени возвращает {'present': bool, 'level': int|None}.
    Все имена матчатся за один проход SetupAPI substring-match без учёта регистра.
    """
    return match_scanned_devices(names, scan_present_devices())


def get_battery_levels(names):
    """Уровни заряда для списка имён за один проход SetupAPI."""
    matches = match_devices(names)
    return {name: data["level"] for name, data in matches.items()}


def get_bluetooth_battery_level(device_name_part):
    """
    Возвращает уровень заряда (0-100) для Bluetooth-устройства,
    FriendlyName которого содержит `device_name_part` (без учёта регистра).
    None — если не найдено или свойства нет.
    """
    return get_battery_levels([device_name_part]).get(device_name_part)


def list_all_battery_devices():
    """Список (FriendlyName, battery%) для устройств со свойством батареи."""
    result = []
    for dev in scan_present_devices():
        if dev.get("level") is not None:
            result.append((dev.get("name") or "<no friendly name>", dev["level"]))
    return result


def list_bluetooth_devices():
    """FriendlyName сопряжённых Bluetooth-устройств через SetupAPI."""
    names = []
    seen = set()
    for dev in scan_present_devices(
        BLUETOOTH_CLASS_GUID,
        flags=DIGCF_PRESENT,
    ):
        instance_id = (dev.get("instance_id") or "").upper()
        if not (instance_id.startswith("BTHENUM\\") or instance_id.startswith("BTHLE\\")):
            continue
        name = (dev.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for name, lvl in list_all_battery_devices():
        log.info("%s: %s%%", name, lvl)
    log.info("MOMENTUM 4: %s", get_bluetooth_battery_level("MOMENTUM 4"))
