import ctypes
from ctypes import wintypes
import uuid

# --- Константы ---
DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004

SPDRP_DEVICEDESC = 0x00000000
SPDRP_FRIENDLYNAME = 0x0000000C

DEVPROP_TYPE_BYTE = 0x00000003
DEVPROP_TYPE_UINT16 = 0x00000005
DEVPROP_TYPE_UINT32 = 0x00000007

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)


# --- Структуры ---
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
        ("Reserved", ctypes.c_size_t),  # ULONG_PTR
    ]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [
        ("fmtid", GUID),
        ("pid", wintypes.DWORD),
    ]


# --- Прототипы функций ---
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

setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL


BATTERY_DEVPKEY = DEVPROPKEY(
    fmtid=GUID.from_string("{104EA319-6EE2-4701-BD47-8DDBF425BBE5}"),
    pid=2,
)


# --- Вспомогательные функции ---
def _get_friendly_name(h, did):
    buf = ctypes.create_unicode_buffer(1024)
    required = wintypes.DWORD(0)
    ptype = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDeviceRegistryPropertyW(
        h,
        ctypes.byref(did),
        SPDRP_FRIENDLYNAME,
        ctypes.byref(ptype),
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
        ctypes.sizeof(buf),
        ctypes.byref(required),
    )
    return buf.value if ok else None


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


# --- Публичный API ---
def get_bluetooth_battery_level(device_name_part):
    """
    Возвращает уровень заряда (0-100) для Bluetooth-устройства,
    FriendlyName которого содержит `device_name_part` (без учёта регистра).
    None — если не найдено или свойства нет.
    """
    h = setupapi.SetupDiGetClassDevsW(
        None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES
    )
    if not h or h == INVALID_HANDLE_VALUE:
        return None

    try:
        did = SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        idx = 0
        while setupapi.SetupDiEnumDeviceInfo(h, idx, ctypes.byref(did)):
            fname = _get_friendly_name(h, did)
            if fname and device_name_part.lower() == fname.lower():
                level = _get_battery_prop(h, did)
                if level is not None:
                    return level
            idx += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(h)
    return None


def list_all_battery_devices():
    """
    Диагностическая функция: возвращает список (FriendlyName, battery%) для
    всех устройств, у которых вообще есть свойство батареи.
    """
    result = []
    h = setupapi.SetupDiGetClassDevsW(
        None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES
    )
    if not h or h == INVALID_HANDLE_VALUE:
        return result
    try:
        did = SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        idx = 0
        while setupapi.SetupDiEnumDeviceInfo(h, idx, ctypes.byref(did)):
            level = _get_battery_prop(h, did)
            if level is not None:
                fname = _get_friendly_name(h, did) or "<no friendly name>"
                result.append((fname, level))
            idx += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(h)
    return result


if __name__ == "__main__":
    # 1. Сначала диагностика — покажет, у каких устройств Windows вообще
    #    хранит свойство батареи. Здесь должны появиться ваши наушники.
    print("Устройства с известным уровнем заряда:")
    for name, lvl in list_all_battery_devices():
        print(f"  {name}: {lvl}%")

    # 2. Затем — целевой запрос.
    level = get_bluetooth_battery_level("MOMENTUM 4")
    if level is not None:
        print(f"\n🔋 Sennheiser Momentum 4: {level}%")
    else:
        print("\nMomentum 4 не найдены среди устройств с battery-свойством.")