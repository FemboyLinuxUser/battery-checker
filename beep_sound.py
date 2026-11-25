"""beep_sound — универсальный асинхронный проигрыватель звуков (stdlib only).

Не привязан к конкретным звукам или путям. Всё настраивается через init().

    import beep_sound as snd

    snd.init({
        "ok":   {"freq": 880, "dur_ms": 60},
        "err":  {"file": "assets/error.wav"},   # относительно base_dir
        "ping": {"freq": 660, "dur_ms": 80, "count": 2, "gap_ms": 40},
    }, base_dir=os.path.dirname(__file__), volume=0.8)

    snd.play("ok")          # асинхронно
    snd.play_sync("err")    # с ожиданием
    snd.shutdown()          # остановить воркер (или автоматически при exit)

Спецификация звука (dict):
    file:     путь к .wav (абс. или относительно base_dir)
    иначе:
    freq:     Гц                (default 800)
    dur_ms:   длительность, мс  (default 100)
    count:    повторов          (default 1)
    gap_ms:   пауза между ними  (default 0)
"""

import atexit
import math
import os
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave

# ---------------------------------------------------------------- состояние
_initialized = False
_backend = None
_proc_player = []
_wav = {}
_queue = queue.Queue()
_worker = None
_enabled = True
_log = lambda msg: None   # no-op по умолчанию

def set_logger(fn):
    """Подключить логгер: fn(str). fn=None — отключить."""
    global _log
    _log = fn or (lambda msg: None)

# ---------------------------------------------------------------- синтез
def _tone_pcm(freq, dur_ms, sr, vol, fade_ms):
    n = int(sr * dur_ms / 1000)
    if n <= 0:
        return b""
    vol = max(0.0, min(1.0, vol))
    fade = max(1, min(int(sr * fade_ms / 1000), n // 4))
    buf = bytearray(n * 2)
    k = 2.0 * math.pi * freq / sr
    for i in range(n):
        v = math.sin(k * i) * vol
        if i < fade:
            v *= i / fade
        elif i >= n - fade:
            v *= (n - 1 - i) / fade
        struct.pack_into("<h", buf, i * 2, int(v * 32767))
    return bytes(buf)

def _silence(ms, sr):
    return b"\x00\x00" * int(sr * ms / 1000)

def _write_wav(name, pcm, sr):
    path = os.path.join(tempfile.gettempdir(), f"beep_{name}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    _wav[name] = path

def _prepare_sound(name, spec, sr, vol, fade_ms, lead_ms, tail_ms, base_dir):
    path = spec.get("file")
    if isinstance(path, str) and path:
        if not os.path.isabs(path):
            path = os.path.join(base_dir or os.getcwd(), path)
        if not os.path.exists(path):
            _log(f"[sound] file not found: {path} (skip '{name}')")
            return
        _wav[name] = path
        return
    tone  = _tone_pcm(int(spec.get("freq", 800)),
                      int(spec.get("dur_ms", 100)),
                      sr, vol, fade_ms)
    gap   = _silence(int(spec.get("gap_ms", 0)), sr)
    inner = gap.join([tone] * max(1, int(spec.get("count", 1))))
    pcm   = _silence(lead_ms, sr) + inner + _silence(tail_ms, sr)
    _write_wav(name, pcm, sr)

# ---------------------------------------------------------------- бэкенд
def _find_proc_player():
    cands = [["paplay"], ["pw-play"], ["aplay", "-q"],
             ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]]
    if sys.platform == "darwin":
        cands.insert(0, ["afplay"])
    for c in cands:
        if shutil.which(c[0]):
            return c
    return []

def _detect_backend():
    global _backend, _proc_player
    if not _enabled:
        _backend = "bell"
        return
    if sys.platform == "win32":
        try:
            import winsound  # noqa: F401
            _backend = "winsound"
            return
        except ImportError:
            pass
    _proc_player = _find_proc_player()
    _backend = "proc" if _proc_player else "bell"

def _warmup(sr):
    """Первый winsound.PlaySound может тормозить 50–200 мс."""
    if _backend != "winsound":
        return
    try:
        import winsound
        p = os.path.join(tempfile.gettempdir(), "beep_silent.wav")
        with wave.open(p, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00\x00" * int(sr * 0.01))
        winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except Exception:
        _log(f"[sound] warm-up FAIL:\n{traceback.format_exc()}")

# ---------------------------------------------------------------- воспроизведение
def _play_blocking(name):
    path = _wav.get(name)
    if path is None:
        return
    if _backend == "winsound":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    elif _backend == "proc":
        subprocess.Popen(_proc_player + [path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         start_new_session=True).wait()
    else:
        sys.stdout.write("\a")
        sys.stdout.flush()
        time.sleep(0.05)

def _worker_loop():
    while True:
        name = _queue.get()
        if name is None:
            _queue.task_done()
            break
        try:
            _play_blocking(name)
        except Exception:
            _log(f"[sound] play FAIL:\n{traceback.format_exc()}")
        finally:
            _queue.task_done()

# ---------------------------------------------------------------- публичный API
def init(sounds, *, base_dir=None, enabled=True, sample_rate=44100,
         volume=0.6, fade_ms=5, lead_ms=0, tail_ms=0,
         logger=None, at_exit=True):
    """Инициализация. sounds — {name: spec}, spec см. докстринг модуля."""
    global _initialized, _enabled, _worker
    if _initialized:
        return
    _enabled = enabled
    if logger is not None:
        set_logger(logger)

    _detect_backend()
    if _backend != "bell":
        for name, spec in sounds.items():
            try:
                _prepare_sound(name, spec, sample_rate, volume,
                               fade_ms, lead_ms, tail_ms, base_dir)
            except Exception:
                _log(f"[sound] prep FAIL ({name}):\n{traceback.format_exc()}")
    _log(f"[sound] backend={_backend} sounds={list(_wav)}")

    _warmup(sample_rate)

    _worker = threading.Thread(target=_worker_loop, name="sound-worker",
                               daemon=True)
    _worker.start()
    if at_exit:
        atexit.register(shutdown)
    _initialized = True

def play(name):
    """Асинхронно поставить в очередь."""
    if _enabled and name in _wav:
        _queue.put(name)

def play_sync(name):
    """Синхронно — дождаться окончания."""
    if _enabled and name in _wav:
        _queue.put(name)
        _queue.join()

def shutdown(timeout=None):
    """Остановить воркер. Идемпотентно."""
    global _initialized
    if not _initialized:
        return
    _queue.put(None)
    if _worker and _worker.is_alive():
        _worker.join(timeout=timeout)
    _initialized = False

def available():
    """Имена готовых к воспроизведению звуков."""
    return list(_wav)

def reset():
    """Полный сброс для повторной инициализации с новыми настройками."""
    global _initialized
    if _initialized:
        shutdown()
    _wav.clear()
    while True:
        try:
            _queue.get_nowait()
            _queue.task_done()
        except queue.Empty:
            break
    _initialized = False