"""Button map (report 8, 59 B: 18 slots x (type, a, b) + csum16) and the HID key tables.

Report 8 cannot be read back from the mouse; callers keep the map themselves (see profiles.py).
Decoded statically from AttackShark.exe (table at 0x4e7368); NOT verified on hardware.
"""
from .protocol import csum_buttons

SLOTS = 18
KEY_FUNC = 0x10    # keyboard key / combo: keys[slot] = (modifier_mask, usage)
MACRO_FUNC = 0x11  # macro: one macro slot per button, see macros.py

# app function code -> (type, a, b) bytes of report 8
BUTTON_FUNCS = {
    0x00: (1, 0, 0),
    0x01: (2, 0, 0),
    0x02: (3, 0, 0),
    0x03: (4, 0, 0),
    0x04: (6, 0, 0),
    0x05: (5, 0, 0),
    0x09: (7, 0, 0),
    0x0a: (8, 0, 0),
    0x0b: (9, 0, 0),
    0x0c: (10, 0, 0),
    0x0d: (11, 0, 0),
    0x0e: (12, 0, 0),
    0x06: (13, 0, 0),
    0x07: (14, 0, 0),
    0x08: (15, 0, 0),
    0x10: (17, 0, 0),
    0x11: (18, 0, 0),
    0x13: (19, 0, 0),
    0x73: (20, 0, 0),
    0x15: (43, 0, 0),
    0x16: (16, 0, 3),
    0x17: (41, 0, 3),
    0x36: (52, 0, 0),
    0x37: (53, 0, 0),
    0x38: (54, 0, 0),
    0x34: (60, 0, 0),
    0x40: (21, 0, 0),
    0x43: (22, 0, 0),
    0x44: (23, 0, 0),
    0x41: (24, 0, 0),
    0x42: (25, 0, 0),
    0x47: (26, 0, 0),
    0x45: (27, 0, 0),
    0x46: (28, 0, 0),
    0x58: (29, 0, 0),
    0x57: (30, 0, 0),
    0x51: (17, 3, 18),
    0x52: (32, 0, 0),
    0x53: (33, 0, 0),
    0x54: (34, 0, 0),
    0x59: (35, 0, 0),
    0x55: (36, 0, 0),
    0x50: (37, 0, 0),
    0x56: (38, 0, 0),
    0x20: (17, 1, 27),
    0x21: (17, 1, 6),
    0x22: (17, 1, 25),
    0x23: (17, 1, 18),
    0x2f: (17, 1, 17),
    0x24: (17, 1, 22),
    0x29: (17, 1, 19),
    0x25: (17, 1, 9),
    0x26: (17, 1, 28),
    0x27: (17, 1, 29),
    0x30: (17, 1, 46),
    0x31: (17, 1, 45),
    0x28: (17, 1, 4),
    0x2b: (17, 4, 43),
    0x2c: (17, 8, 7),
    0x2a: (17, 4, 61),
    0x2d: (17, 8, 21),
    0x2e: (17, 8, 15),
}
# model 4 default code per slot (table 0x4e78a0); last two swapped: vendor order inverted the wheel on this mouse
BUTTON_DEFAULTS = [0x1, 0x2, 0x3, 0x6, 0x5, 0x4, 0x34, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0xb, 0xc]
# slot 8 = back side button (type 5), slot 7 = forward side button (type 6); the vendor default left slot 8 'off' (type 1)
X11_FIXES = {7: (5, 0, 0), 6: (6, 0, 0)}

MODIFIERS = {"ctrl": 1, "shift": 2, "alt": 4, "gui": 8, "win": 8, "super": 8, "meta": 8}
MOUSE_KEYS = {"lmb": 0xF1, "rmb": 0xF2, "mmb": 0xF3}  # macro-only pseudo usages

KEY_USAGES = {chr(97 + i): 4 + i for i in range(26)}
KEY_USAGES.update({str(d): 30 + (d - 1) % 10 for d in range(10)})
KEY_USAGES.update({"enter": 40, "esc": 41, "backspace": 42, "tab": 43, "space": 44, "minus": 45, "equal": 46,
                   "insert": 73, "home": 74, "pageup": 75, "delete": 76, "end": 77, "pagedown": 78,
                   "right": 79, "left": 80, "down": 81, "up": 82})
KEY_USAGES.update({f"f{i}": 57 + i for i in range(1, 13)})
KEY_NAMES = {}
for _n, _u in KEY_USAGES.items():
    KEY_NAMES.setdefault(_u, _n)

# Names are best effort; codes without a name show as "Function 0xNN". Basic ones follow X11_FIXES / defaults.
_NAMES = {0x00: "Disabled", 0x01: "Left Click", 0x02: "Right Click", 0x03: "Middle Click", 0x04: "Forward",
          0x05: "Back", 0x0B: "Wheel Up", 0x0C: "Wheel Down", KEY_FUNC: "Keyboard Key", MACRO_FUNC: "Macro"}


def key_usage(name):
    """HID usage for a key name (a-z, 0-9, f1-f12, enter, esc, space, tab, arrows...), lmb/rmb/mmb, or a number."""
    n = str(name).lower()
    if n in MOUSE_KEYS:
        return MOUSE_KEYS[n]
    if n in KEY_USAGES:
        return KEY_USAGES[n]
    try:
        return int(n, 0)
    except ValueError:
        raise ValueError(f"unknown key {name!r}") from None


def parse_key_combo(text):
    """'ctrl+shift+a' -> (modifier_mask, usage)."""
    *mods, key = text.lower().split("+")
    mask = 0
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError(f"unknown modifier {m!r} (use ctrl, shift, alt, gui)")
        mask |= MODIFIERS[m]
    return mask, key_usage(key)


def format_key_combo(mods, usage):
    parts = [n.capitalize() for n, bit in (("ctrl", 1), ("shift", 2), ("alt", 4), ("gui", 8)) if mods & bit]
    return "+".join(parts + [KEY_NAMES.get(usage, f"0x{usage:02x}").upper()])


def func_name(code):
    if code in _NAMES:
        return _NAMES[code]
    t, a, b = BUTTON_FUNCS[code]
    if t == 17 and a:  # fixed modifier+key shortcuts
        return format_key_combo(a, b)
    return f"Function 0x{code:02x}"


def function_names():
    """{code: human name} for every code in BUTTON_FUNCS."""
    return {c: func_name(c) for c in BUTTON_FUNCS}


def parse_function(text):
    """CLI/profile spec -> (code, key) where key is (mods, usage) or None. Accepts '0x34', 'macro', 'key:ctrl+c' or a name."""
    t = text.strip().lower()
    if t.startswith("key:"):
        return KEY_FUNC, parse_key_combo(t[4:])
    if t == "macro":
        return MACRO_FUNC, None
    try:
        code = int(t, 16)
    except ValueError:
        by_name = {n.lower(): c for c, n in function_names().items()}
        if t not in by_name:
            raise ValueError(f"unknown button function {text!r}") from None
        code = by_name[t]
    if code not in BUTTON_FUNCS:
        raise ValueError(f"unknown function code 0x{code:02x}")
    if code == KEY_FUNC:
        raise ValueError("use key:<combo> for keyboard keys, e.g. key:ctrl+c")
    return code, None


def validate_codes(codes):
    if len(codes) != SLOTS or any(c not in BUTTON_FUNCS for c in codes):
        raise ValueError(f"need {SLOTS} known function codes")
    if 1 not in codes:
        raise ValueError("keep at least one button as Left Click (0x1)")


def build_buttons(codes=None, keys=None, raw=None):
    """Report 8 (59 B): 18 slots x (type, a, b). codes = app function code per slot; keys = {slot: (mods, usage)} for code 0x10."""
    codes = codes or BUTTON_DEFAULTS
    raw = {**X11_FIXES, **(raw or {})}
    b = bytearray(59)
    b[0], b[1], b[2] = 8, 0x3B, 1
    for i, c in enumerate(codes):
        t, x, y = BUTTON_FUNCS[c]
        if c == KEY_FUNC:
            x, y = keys[i]
        if c == MACRO_FUNC:  # b2 = button number, one macro slot per button (FUN_004a26c0)
            y = i + 1
        if raw and i in raw:  # raw (type, a, b) override per 0-based slot
            t, x, y = raw[i]
        b[3 + 3 * i:6 + 3 * i] = bytes((t, x, y))
    b[57], b[58] = csum_buttons(b)
    return bytes(b)
