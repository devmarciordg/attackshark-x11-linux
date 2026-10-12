"""GTK key events -> HID usage + modifiers, and macro text helpers. Pure Python: no GTK import, testable without a display."""
from ..buttons import KEY_USAGES, format_key_combo
from ..macros import MAX_EVENTS, parse_events

# Gdk.ModifierType bits (GTK4)
SHIFT, CTRL, ALT, SUPER = 1, 4, 8, 1 << 26
HID_MOD = ((CTRL, 1), (SHIFT, 2), (ALT, 4), (SUPER, 8))  # -> buttons.MODIFIERS bits

_NAMED = {0xFF0D: "enter", 0xFF8D: "enter", 0xFF1B: "esc", 0xFF08: "backspace", 0xFF09: "tab", 0xFE20: "tab",
          0x20: "space", 0x2D: "minus", 0x3D: "equal", 0xFF63: "insert", 0xFF50: "home", 0xFF55: "pageup",
          0xFFFF: "delete", 0xFF57: "end", 0xFF56: "pagedown", 0xFF53: "right", 0xFF51: "left",
          0xFF54: "down", 0xFF52: "up"}
_SHIFTED = dict(zip("!@#$%^&*()", "1234567890"), _="minus", **{"+": "equal"})
_MODIFIER_KEYVALS = set(range(0xFFE1, 0xFFEF)) | {0xFE03}  # Shift/Control/Caps/Meta/Alt/Super/Hyper, ISO_Level3


def is_modifier(keyval):
    return keyval in _MODIFIER_KEYVALS


def keyval_to_name(keyval):
    """Gdk keyval -> key name known to buttons.KEY_USAGES, or None."""
    if 0xFFBE <= keyval <= 0xFFC9:  # F1..F12
        return f"f{keyval - 0xFFBD}"
    if keyval in _NAMED:
        return _NAMED[keyval]
    if 0xFF80 <= keyval <= 0xFFB9 and keyval not in (0xFF8D,):  # keypad digits
        return str(keyval - 0xFFB0) if 0xFFB0 <= keyval <= 0xFFB9 else None
    if 0x20 <= keyval < 0x7F:
        c = chr(keyval).lower()
        c = _SHIFTED.get(c, c)
        return c if c in KEY_USAGES else None
    return None


def mods_from_state(state):
    return sum(bit for gdk, bit in HID_MOD if state & gdk)


def combo_from_event(keyval, state):
    """-> (modifier_mask, usage) for a keyboard-key button, None for a lone modifier / unsupported key."""
    name = keyval_to_name(keyval)
    if name is None:
        return None
    return mods_from_state(state), KEY_USAGES[name]


def combo_text(mods, usage):
    return format_key_combo(mods, usage)


class Recorder:
    """Turns timed key press/release events into macro lines '+a:30' (delay = ms since the previous event)."""

    def __init__(self):
        self.lines, self.down, self.last = [], set(), None

    def _add(self, sign, name, now):
        if len(self.lines) >= MAX_EVENTS:
            return
        delay = 10 if self.last is None else max(10, round((now - self.last) * 1000))
        self.last = now
        self.lines.append(f"{sign}{name}:{delay}")

    def press(self, keyval, now):
        name = keyval_to_name(keyval)
        if name and name not in self.down:  # ignore auto-repeat
            self.down.add(name)
            self._add("+", name, now)

    def release(self, keyval, now):
        name = keyval_to_name(keyval)
        if name in self.down:
            self.down.discard(name)
            self._add("-", name, now)


def events_from_text(text):
    """Multi-line text (blank lines and '#' comments ignored) -> list of event strings, validated."""
    items = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    parse_events(items)
    return items
