import copy

from config import DEFAULT_CONFIG, _deep_merge, _merge_sound_specs, sanitize_config_sections, validate_config
from devices import _normalize_devices_list, build_devices
from logic import _normalize_sound_spec, evaluate_device_update


def test_deep_merge_preserves_nested_defaults():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    assert _deep_merge(base, {"a": {"x": 10}}) == {"a": {"x": 10, "y": 2}, "b": 3}


def test_default_config_is_valid():
    assert validate_config(copy.deepcopy(DEFAULT_CONFIG)) == []


def test_validate_config_ranges_and_threshold_order():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["battery"]["low_threshold"] = 100
    cfg["battery"]["full_threshold"] = 20
    cfg["battery"]["poll_interval"] = 2
    cfg["battery"]["overlay_pos"] = [0]
    errors = validate_config(cfg)
    assert any("low_threshold" in e for e in errors)
    assert any("poll_interval" in e for e in errors)
    assert any("overlay_pos" in e for e in errors)


def test_normalize_devices_list_legacy_dict():
    raw = {
        "aula": {},
        "headphones": {"bluetooth_name": "MOMENTUM 4"},
        "broken": None,
    }
    assert _normalize_devices_list(raw) == [
        {"source": "aula", "type": "keyboard", "enabled": True},
        {"source": "bluetooth", "bluetooth_name": "MOMENTUM 4", "type": "headphones", "enabled": True},
    ]


def test_normalize_sound_spec():
    assert _normalize_sound_spec("x.wav") == {"file": "x.wav"}
    spec = {"freq": 500, "dur_ms": 30, "count": 5, "gap_ms": 60}
    assert _normalize_sound_spec(spec) == spec
    assert _normalize_sound_spec(spec) is not spec


def test_build_devices_stable_keys():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["battery"]["devices"] = [
        {"source": "aula", "type": "keyboard", "enabled": True},
        {"source": "bluetooth", "type": "headphones", "enabled": True, "bluetooth_name": "MOMENTUM 4"},
    ]
    devices = build_devices(cfg)
    assert [d["key"] for d in devices] == ["aula", "bt:MOMENTUM 4"]
    assert devices[1]["label"] == "MOMENTUM 4"


def test_low_transition_and_repeat_step():
    state, event, last = evaluate_device_update("ok", 20, 20, 100, 5, None)
    assert (state, event, last) == ("low", "low", 20)

    state, event, last = evaluate_device_update("low", 16, 20, 100, 5, last)
    assert (state, event, last) == ("low", None, 20)

    state, event, last = evaluate_device_update("low", 15, 20, 100, 5, last)
    assert (state, event, last) == ("low", "low", 15)


def test_initial_unknown_does_not_beep_but_tracks_level():
    assert evaluate_device_update("unknown", 20, 20, 100, 5, None) == ("low", None, 20)
    assert evaluate_device_update("unknown", 100, 20, 100, 5, None) == ("full", None, None)


def test_full_transition_event():
    assert evaluate_device_update("ok", 100, 20, 100, 5, None) == ("full", "full", None)


def test_file_sound_spec_not_contaminated_by_tone_defaults():
    merged = _merge_sound_specs(
        {"low_bt": {"freq": 500, "dur_ms": 30}},
        {"low_bt": {"file": "sounds/low.wav"}},
    )
    assert merged["low_bt"] == {"file": "sounds/low.wav"}


def test_sanitize_config_sections_restores_defaults():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["battery"] = None
    cfg["sounds"] = None
    cfg["history"] = None
    sanitized = sanitize_config_sections(cfg)
    assert sanitized["battery"] == DEFAULT_CONFIG["battery"]
    assert sanitized["sounds"] == DEFAULT_CONFIG["sounds"]
    assert sanitized["history"] == DEFAULT_CONFIG["history"]


def test_validate_config_rejects_non_mapping_sounds():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["sounds"] = None
    assert any("sounds" in e for e in validate_config(cfg))
