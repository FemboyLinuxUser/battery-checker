import os, yaml, sys

if getattr(sys, 'frozen', False):
    __application_path = os.path.dirname(sys.executable)
    __BUILD='1.0.0'
else:
    __application_path = os.path.dirname(os.path.abspath(__file__))
    __BUILD='test'

_CONFIG_DIR = __application_path
CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.yaml")

DEFAULT_CONFIG = {}

def _deep_merge(base, override):
    result = dict(base)
    for k, v in (override or {}).items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_config():
    try:
        import yaml
    except ImportError:
        print("!!! PyYAML не установлен (pip install pyyaml). Дефолты.", flush=True)
        return DEFAULT_CONFIG
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
            print(f"[config] создан {CONFIG_PATH}", flush=True)
        except Exception as e:
            print(f"!!! Не смог создать {CONFIG_PATH}: {e}", flush=True)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"!!! Ошибка чтения {CONFIG_PATH}: {e}. Дефолты.", flush=True)
        return DEFAULT_CONFIG
    return _deep_merge(DEFAULT_CONFIG, user)

def save_config(cfg, path=None):
    """
    Сохраняет конфиг в YAML. Если путь не задан — пишет в config.yaml
    рядом с приложением (замените на реальный путь вашего load_config,
    если он читает другой файл).
    """
    if path is None:
        path = os.path.join(__application_path, "config.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            cfg, f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )