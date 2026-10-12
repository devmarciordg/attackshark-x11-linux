"""Pure report encode/decode for the X11 (no I/O). Reports: 4 = DPI (56 B), 5 = light/misc (15 B), 6 = rate (9 B)."""

SIZES = {4: 56, 5: 15, 6: 9}
STAGES = 8
LIGHT_MODES = ["LED Off", "Static", "Breathing", "Neon", "Color Breathing", "Static DPI", "Breathing DPI"]
BATTERY_STATUS = {1: "discharging", 2: "charging", 3: "low battery"}
RATES = {125: 8, 250: 4, 500: 2, 1000: 1}  # report 6 byte 3 low nibble = interval in ms (measured)


class ProtocolError(ValueError):
    """Malformed report (wrong id/length/checksum)."""


def csum_dpi(b):  # report 4: sum of bytes 3..49, big endian at 50..51
    s = sum(b[3:50]) & 0xFFFF
    return s >> 8, s & 0xFF


def csum_light(b):  # report 5: sum of bytes 3..10, big endian at 11..12
    s = sum(b[3:11]) & 0xFFFF
    return s >> 8, s & 0xFF


def csum_buttons(b):  # report 8: sum of bytes 3..56, big endian at 57..58
    s = sum(b[3:57]) & 0xFFFF
    return s >> 8, s & 0xFF


def dpi_decode(lo, hi, high_range):
    return ((lo | hi << 8) + 1) * (100 if high_range else 50)


def dpi_encode(dpi):
    """-> (value16, high_range). 50 DPI units up to 26000, 100 DPI units above (as the vendor app)."""
    if dpi <= 26000:
        return dpi // 50 - 1, False
    return dpi // 100 - 1, True


def parse_dpi(b):
    if len(b) != 56 or b[0] != 4 or b[1] != 0x38:
        raise ProtocolError(f"bad DPI report: {bytes(b).hex()}")
    if (b[50], b[51]) != csum_dpi(b):
        raise ProtocolError("bad DPI report checksum")
    stages = []
    for i in range(STAGES):
        stages.append({
            "enabled": bool(b[5] >> i & 1),
            "dpi": dpi_decode(b[8 + i], b[16 + i], b[6] >> i & 1),
            "rgb": tuple(b[25 + 3 * i:28 + 3 * i]),
        })
    return {
        "stages": stages,
        "active": b[24] - 1,
        "lift_off_mm": (b[3] >> 4) + 1,  # option 0 = 1 mm, 1 = 2 mm
        "ripple": bool(b[3] & 0xF),
        "angle_snap": bool(b[4] >> 4),
        "motion_sync": bool(b[4] & 0xF),
    }


def build_dpi(raw, cfg):
    """Rewrite a raw report 4 (as read) from cfg, keeping the bytes we do not understand."""
    b = bytearray(raw)
    mask = flags = 0
    for i, s in enumerate(cfg["stages"]):
        if s["enabled"]:
            mask |= 1 << i
            v, high = dpi_encode(s["dpi"])
            flags |= high << i
            b[8 + i], b[16 + i] = v & 0xFF, v >> 8
        b[25 + 3 * i:28 + 3 * i] = bytes(s["rgb"])
    b[5], b[6] = mask, flags
    b[24] = cfg["active"] + 1
    b[3] = (cfg["lift_off_mm"] - 1) << 4 | int(cfg["ripple"])
    b[4] = int(cfg["angle_snap"]) << 4 | int(cfg["motion_sync"])
    b[50], b[51] = csum_dpi(b)
    return bytes(b)


def parse_light(b):
    if len(b) != 15 or b[0] != 5 or b[1] != 0x0F:
        raise ProtocolError(f"bad light report: {bytes(b).hex()}")
    if (b[11], b[12]) != csum_light(b):
        raise ProtocolError("bad light report checksum")
    return {
        "mode": b[3] >> 4,
        "rgb": tuple(b[6:9]),
        "brightness": b[5] & 0xF,  # 1..8
        "breath_speed": 9 - (b[4] & 0xF),  # 4..8 (stored inverted)
        "deep_sleep_s": (b[4] & 0xF0) | b[5] >> 4,  # seconds
        "sleep_min": b[9],  # 1..60
        "debounce_ms": b[10] * 2,  # raw 2..25
        "raw": bytes(b).hex(),
    }


def build_light(raw, mode=None, rgb=None, brightness=None, breath_speed=None,
                deep_sleep_s=None, sleep_min=None, debounce_ms=None):
    b = bytearray(raw)
    if mode is not None:
        b[3] = mode << 4 | (b[3] & 0xF)
    if rgb is not None:
        b[6:9] = bytes(rgb)
    if brightness is not None:
        b[5] = b[5] & 0xF0 | brightness
    if breath_speed is not None:
        b[4] = b[4] & 0xF0 | 9 - breath_speed
    if deep_sleep_s is not None:
        b[4] = deep_sleep_s & 0xF0 | b[4] & 0xF
        b[5] = (deep_sleep_s & 0xF) << 4 | b[5] & 0xF
    if sleep_min is not None:
        b[9] = sleep_min
    if debounce_ms is not None:
        b[10] = debounce_ms // 2
    b[11], b[12] = csum_light(b)
    return bytes(b)


def parse_rate(b):
    ms = b[3] & 0xF
    return 1000 // ms if ms in (1, 2, 4, 8) else None


def build_rate(raw, hz):
    b = bytearray(raw)
    b[3] = b[3] & 0xF0 | RATES[hz]
    b[4] = ~b[3] & 0xFF
    return bytes(b)


# Input reports on the config interface: `03 55 <type> <value> <value2>`.
# Types 0x10/0x20/0x50/0x70 payload layout is a best guess (README: only 0x40 battery was seen on hardware).
_EVENT_NAMES = {0x10: "dpi_stage", 0x20: "polling", 0x40: "battery", 0x50: "write_ack", 0x70: "light"}


def parse_event(r):
    """Parse an input report. Returns a dict with 'event' (+ fields) or None if it is not a config event."""
    r = bytes(r)
    if len(r) < 5 or r[0] != 3 or r[1] != 0x55:
        return None
    t, v, w = r[2], r[3], r[4]
    name = _EVENT_NAMES.get(t)
    ev = {"event": name or f"unknown_0x{t:02x}", "raw": r.hex()}
    if t == 0x40:
        ev.update(status=BATTERY_STATUS.get(v, f"status {v}"), percent=w)
    elif t == 0x10:
        ev["stage"] = v  # shortcut: 1-based vs 0-based unverified, check against `show` on hardware
    elif t == 0x20:
        ev["hz"] = parse_rate(bytes([0, 0, 0, v]))
    elif t == 0x70:
        ev.update(mode=v, mode_name=LIGHT_MODES[v] if v < len(LIGHT_MODES) else "?")
    return ev
