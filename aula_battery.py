"""Чтение уровня заряда AULA F108 Pro (USB-донгл 2.4G, MI_03)."""
import ctypes
from ctypes import wintypes
import hid
import time

# --- Windows API константы ---
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0

# --- Параметры устройства ---
TARGET_VID = 0x05AC
TARGET_PID = 0x024F
TARGET_MI = 3
BATTERY_INDEX = 4

# --- Команда запроса заряда (33 байта: Report ID + payload) ---
COMMAND = b'\x00' + bytes([0x20, 0x01, 0x00] + [0x00] * 28 + [0x21])

# --- Префикс ответа, в котором лежит заряд: 00 20 01 00 XX ---
BATTERY_PREFIX = bytes([0x00, 0x20, 0x01, 0x00])

# --- Windows API ---
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]

CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
CreateFileW.restype = wintypes.HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]

CreateEventW = kernel32.CreateEventW
CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
CreateEventW.restype = wintypes.HANDLE

WaitForSingleObject = kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
WaitForSingleObject.restype = wintypes.DWORD

GetOverlappedResult = kernel32.GetOverlappedResult
GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED),
                                wintypes.LPDWORD, wintypes.BOOL]
GetOverlappedResult.restype = wintypes.BOOL

CancelIoEx = kernel32.CancelIoEx
CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
CancelIoEx.restype = wintypes.BOOL

WriteFile = kernel32.WriteFile
WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                      wintypes.LPDWORD, ctypes.POINTER(OVERLAPPED)]
WriteFile.restype = wintypes.BOOL

ReadFile = kernel32.ReadFile
ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                     wintypes.LPDWORD, ctypes.POINTER(OVERLAPPED)]
ReadFile.restype = wintypes.BOOL

# --- Внутренние хелперы ---
def _find_path():
    for dev in hid.enumerate(TARGET_VID, TARGET_PID):
        if dev.get('interface_number') == TARGET_MI:
            return dev['path']
    return None

def _write(handle, data, timeout_ms=500):
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    written = wintypes.DWORD(0)
    event = CreateEventW(None, True, False, None)
    ov = OVERLAPPED(); ov.hEvent = event
    try:
        ctypes.set_last_error(0)
        ok = WriteFile(handle, buf, len(data), ctypes.byref(written), ctypes.byref(ov))
        if not ok and ctypes.get_last_error() != ERROR_IO_PENDING:
            return False
        if not ok and WaitForSingleObject(event, timeout_ms) != WAIT_OBJECT_0:
            CancelIoEx(handle, ctypes.byref(ov))
            return False
        GetOverlappedResult(handle, ctypes.byref(ov), ctypes.byref(written), False)
        return written.value == len(data)
    finally:
        CloseHandle(event)

def _read(handle, size=64, timeout_ms=700):
    buf = (ctypes.c_ubyte * size)()
    bytes_read = wintypes.DWORD(0)
    event = CreateEventW(None, True, False, None)
    ov = OVERLAPPED(); ov.hEvent = event
    try:
        ctypes.set_last_error(0)
        ok = ReadFile(handle, buf, size, ctypes.byref(bytes_read), ctypes.byref(ov))
        if not ok and ctypes.get_last_error() != ERROR_IO_PENDING:
            return None
        if not ok and WaitForSingleObject(event, timeout_ms) != WAIT_OBJECT_0:
            CancelIoEx(handle, ctypes.byref(ov))
            WaitForSingleObject(event, 1000)
            return None
        GetOverlappedResult(handle, ctypes.byref(ov), ctypes.byref(bytes_read), False)
        return bytes(buf[:bytes_read.value]) if bytes_read.value else None
    finally:
        CloseHandle(event)

# --- Публичный API ---
def get_battery_level(attempts=3):
    """Возвращает уровень заряда (0-100) или None, если устройство не отвечает."""
    path = _find_path()
    if not path:
        return None
    path_str = path.decode('utf-8', errors='ignore') if isinstance(path, bytes) else path

    handle = CreateFileW(path_str, GENERIC_READ | GENERIC_WRITE,
                         FILE_SHARE_READ | FILE_SHARE_WRITE,
                         None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if handle == INVALID_HANDLE_VALUE:
        return None

    try:
        # Дренируем очередь от «мусорных» отчётов
        for _ in range(5):
            if _read(handle, 64, 50) is None:
                break

        for _ in range(attempts):
            if not _write(handle, COMMAND):
                continue
            time.sleep(0.05)

            deadline = time.time() + 1.0
            while time.time() < deadline:
                r = _read(handle, 64, 400)
                if r and len(r) > BATTERY_INDEX and r.startswith(BATTERY_PREFIX):
                    b = r[BATTERY_INDEX]
                    if 0 <= b <= 100:
                        return b
        return None
    finally:
        CloseHandle(handle)


if __name__ == "__main__":
    import sys

    if "--loop" in sys.argv:
        # Мониторинг: опрос раз в минуту
        while True:
            level = get_battery_level()
            ts = time.strftime("%H:%M:%S")
            if level is not None:
                print(f"{ts} 🔋 {level}%", flush=True)
            else:
                print(f"{ts} ⚠️  не удалось прочитать", flush=True)
            time.sleep(60)
    else:
        level = get_battery_level()
        if level is not None:
            print(f"🔋 {level}%")
        else:
            print("Не удалось получить заряд")
            sys.exit(1)