"""Whole-device profiles (DPI table, light/sleep, polling rate, button map + macros) as JSON files.

Report 8/9 (buttons, macros) cannot be read back, so the button map lives in buttons.json in the config dir
and is what snapshot() stores. Config dir: $ATTACKSHARK_X11_CONFIG, else $XDG_CONFIG_HOME/attackshark-x11, else ~/.config/attackshark-x11.
"""
import json
import os
import re

from . import factory
from .buttons import BUTTON_DEFAULTS, MACRO_FUNC, SLOTS, build_buttons, validate_codes
from .macros import macro_reports, validate_macro
from .protocol import STAGES, build_dpi, build_light, build_rate, parse_dpi, parse_light, parse_rate

VERSION = 1
_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_LIGHT_KEYS = ("mode", "rgb", "brightness", "breath_speed", "deep_sleep_s", "sleep_min", "debounce_ms")


def config_dir():
    env = os.environ.get("ATTACKSHARK_X11_CONFIG")
    if env:
        return env
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "attackshark-x11")


def _profile_path(name):
    if not _NAME.match(name):
        raise ValueError(f"bad profile name {name!r} (letters, digits, . _ - only)")
    return os.path.join(config_dir(), "profiles", name + ".json")


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# -- button state (write-only on the device, so remembered here)

def default_buttons():
    return {"codes": list(BUTTON_DEFAULTS), "keys": {}, "macros": {}}


def load_buttons():
    path = os.path.join(config_dir(), "buttons.json")
    try:
        with open(path) as f:
            s = json.load(f)
        return {"codes": s["codes"], "keys": s.get("keys", {}), "macros": s.get("macros", {})}
    except (OSError, ValueError, KeyError):
        pass
    try:  # legacy prototype file: plain list of codes
        with open(os.path.expanduser("~/.config/attackshark_buttons.json")) as f:
            codes = json.load(f)
        if isinstance(codes, list) and len(codes) == SLOTS:
            return {"codes": codes, "keys": {}, "macros": {}}
    except (OSError, ValueError):
        pass
    return default_buttons()


def save_buttons(state):
    validate_codes(state["codes"])
    _write_json(os.path.join(config_dir(), "buttons.json"), state)


def buttons_report(state):
    keys = {int(k): tuple(v) for k, v in state.get("keys", {}).items()}
    return build_buttons(state["codes"], keys)


def write_buttons(dev, state):
    """Send the macros then the button map."""
    for slot, m in sorted(state.get("macros", {}).items(), key=lambda kv: int(kv[0])):
        if state["codes"][int(slot) - 1] == MACRO_FUNC:
            for r in macro_reports(int(slot), m):
                dev.write(r)
    dev.write(buttons_report(state))


# -- device snapshot / apply

def snapshot(dev):
    """Read DPI, light and rate from the device + the remembered button state -> profile dict."""
    light = parse_light(dev.read(5))
    return {
        "version": VERSION,
        "dpi": parse_dpi(dev.read(4)),
        "light": {k: light[k] for k in _LIGHT_KEYS},
        "rate_hz": parse_rate(dev.read(6)),
        "buttons": load_buttons(),
    }


def validate_profile(p):
    if not isinstance(p, dict) or p.get("version") != VERSION:
        raise ValueError(f"not a version {VERSION} profile")
    d = p.get("dpi")
    if not isinstance(d, dict) or len(d.get("stages", [])) != STAGES or not 0 <= d.get("active", -1) < STAGES:
        raise ValueError("profile 'dpi' needs 8 stages and a valid 'active'")
    for s in d["stages"]:
        if not all(k in s for k in ("enabled", "dpi", "rgb")) or len(s["rgb"]) != 3:
            raise ValueError("bad DPI stage in profile")
    if "light" in p and not all(k in p["light"] for k in _LIGHT_KEYS):
        raise ValueError("profile 'light' is incomplete")
    if p.get("buttons"):
        validate_codes(p["buttons"]["codes"])
        for m in p["buttons"].get("macros", {}).values():
            validate_macro(m)
    return p


def apply_profile(dev, p):
    validate_profile(p)
    dev.write(build_dpi(dev.read(4), p["dpi"]))
    if "light" in p:
        l = p["light"]
        dev.write(build_light(dev.read(5), l["mode"], tuple(l["rgb"]), l["brightness"], l["breath_speed"],
                              l["deep_sleep_s"], l["sleep_min"], l["debounce_ms"]))
    if p.get("rate_hz"):
        dev.write(build_rate(dev.read(6), p["rate_hz"]))
    if p.get("buttons"):
        write_buttons(dev, p["buttons"])
        save_buttons(p["buttons"])


def reset_buttons(dev):
    """Default button map (forgets saved macros)."""
    state = default_buttons()
    dev.write(buttons_report(state))
    save_buttons(state)


def reset(dev, preset=factory.DEFAULT_PRESET):
    """Factory DPI/rate preset + default button map."""
    factory.apply_preset(dev, preset)
    reset_buttons(dev)


# -- stored profiles

def save(name, profile):
    _write_json(_profile_path(name), validate_profile(profile))


def load(name):
    try:
        with open(_profile_path(name)) as f:
            return validate_profile(json.load(f))
    except FileNotFoundError:
        raise ValueError(f"no profile named {name!r}") from None


def list_profiles():
    d = os.path.join(config_dir(), "profiles")
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def delete(name):
    try:
        os.remove(_profile_path(name))
    except FileNotFoundError:
        raise ValueError(f"no profile named {name!r}") from None


def export_profile(name, path):
    with open(path, "w") as f:
        json.dump(load(name), f, indent=2)
        f.write("\n")


def import_profile(path, name=None):
    """Validate a JSON file and store it; name defaults to the file's basename. Returns the name."""
    with open(path) as f:
        p = validate_profile(json.load(f))
    name = name or os.path.splitext(os.path.basename(path))[0]
    save(name, p)
    return name
