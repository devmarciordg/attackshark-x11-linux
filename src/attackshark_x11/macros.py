"""Macros (report 9, FUN_004a2430): 131 B sent as 3 feature reports. Decoded statically, not verified on hardware.

Macro dict / file format (JSON):
    {"mode": 0, "loop": 1, "events": ["+a:30", "-a:30"]}     # +key press, -key release, :delay in ms
"""
import json

from .buttons import MOUSE_KEYS, key_usage  # noqa: F401  (re-exported)

MAX_EVENTS = 46


def parse_event(text):
    """'+a:30' -> (usage, pressed, delay_ms)."""
    if text[:1] not in "+-" or ":" not in text:
        raise ValueError(f"bad macro event {text!r} (use +key:ms or -key:ms)")
    key, delay = text[1:].rsplit(":", 1)
    return key_usage(key), text[0] == "+", int(delay)


def parse_events(items):
    return [parse_event(e) for e in items]


def build_macro(slot, events, mode=0, loop=1, unknown=0):
    """events = [(key_usage, pressed, delay_ms)]; slot = button number 1..18. Returns the 3 reports to send."""
    if not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError(f"macro needs 1..{MAX_EVENTS} events")
    b = bytearray(131)
    b[0], b[1], b[2], b[3] = 9, 0x83, slot, mode
    b[4:7] = bytes([unknown]) * 3  # +0x43c in the app struct, meaning unknown
    b[7] = max(loop, 1)
    b[28] = len(events)
    for i, (key, pressed, delay) in enumerate(events):
        d = min(max(round(delay / 10), 1), 127)  # shortcut: delays over 1270 ms are clamped, the app splits them; add when needed
        b[29 + 2 * i:31 + 2 * i] = bytes((d | 1 if pressed else d | 0x81, key))
    s = sum(b[3:0x81]) & 0xFFFF
    b[0x81], b[0x82] = s >> 8, s & 0xFF
    body = b[3:131]
    return [bytes((9, 0x40, slot, 0)) + body[:60], bytes((9, 0x40, slot, 1)) + body[60:120], bytes((9, 0x0C, slot, 2)) + body[120:]]


def macro_reports(slot, macro):
    """Reports for a macro dict (see module doc)."""
    return build_macro(slot, parse_events(macro["events"]), macro.get("mode", 0), macro.get("loop", 1))


def validate_macro(macro):
    if not isinstance(macro, dict) or not isinstance(macro.get("events"), list):
        raise ValueError("macro must be an object with an 'events' list")
    parse_events(macro["events"])
    if macro.get("mode", 0) not in (0, 1, 2):
        raise ValueError("macro mode must be 0, 1 or 2")
    return {"mode": macro.get("mode", 0), "loop": int(macro.get("loop", 1)), "events": list(macro["events"])}


def load_macro_file(path):
    with open(path) as f:
        return validate_macro(json.load(f))


def save_macro_file(path, macro):
    with open(path, "w") as f:
        json.dump(validate_macro(macro), f, indent=2)
        f.write("\n")
