"""Чистая логика состояний батареи, не зависящая от Qt/Win32."""


def classify_level(level, low_threshold, full_threshold):
    if level is None:
        return "unknown"
    if level <= low_threshold:
        return "low"
    if level >= full_threshold:
        return "full"
    return "ok"


def evaluate_device_update(
    prev_state,
    level,
    low_threshold,
    full_threshold,
    low_repeat_step=5,
    last_notified_level=None,
):
    """
    Возвращает (new_state, event, new_last_notified_level).
    event — None, 'low' или 'full'. Начальное unknown-наблюдение не звучит,
    но запоминает уровень как точку отсчёта для повторных low-уведомлений.
    """
    new_state = classify_level(level, low_threshold, full_threshold)
    event = None
    new_last = last_notified_level

    if new_state == "low":
        if prev_state == "unknown":
            new_last = level
        elif prev_state != "low":
            event = "low"
            new_last = level
        else:
            if new_last is None:
                new_last = level
            elif level is not None and new_last - level >= low_repeat_step:
                event = "low"
                new_last = level
    else:
        new_last = None
        if new_state == "full" and prev_state not in ("unknown", "full"):
            event = "full"

    return new_state, event, new_last


def _normalize_sound_spec(spec):
    """str → {file}; dict → копия как есть (не теряем freq/dur_ms/...)."""
    if isinstance(spec, dict):
        return dict(spec)
    return {"file": str(spec) if spec else ""}


def as_mapping(value):
    return value if isinstance(value, dict) else {}


def int_or(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def float_or(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def position_or(value, default=(20, 20)):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            pass
    return int(default[0]), int(default[1])
