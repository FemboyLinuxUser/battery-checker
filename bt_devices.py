"""Список сопряжённых Bluetooth-устройств Windows (без внешних зависимостей)."""

import subprocess


_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
Get-PnpDevice -Class Bluetooth -Status OK |
    Where-Object {
        $_.InstanceId -like 'BTHENUM\*' -or
        $_.InstanceId -like 'BTHLE\*'
    } |
    Select-Object -ExpandProperty FriendlyName
"""


def _run_powershell(script: str, timeout: int = 15):
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=creationflags,
    )


def list_bluetooth_devices() -> list[str]:
    """
    Возвращает список FriendlyName сопряжённых Bluetooth-устройств.
    При любой ошибке (нет PowerShell, таймаут, пустой вывод) — [].
    """
    try:
        res = _run_powershell(_PS_SCRIPT)
    except Exception as e:
        print(f"[bt_devices] ошибка: {e}")
        return []

    names: list[str] = []
    seen: set[str] = set()
    for line in (res.stdout or "").splitlines():
        name = line.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)

    return names