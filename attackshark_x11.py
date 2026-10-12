#!/usr/bin/env python3
"""Linux driver/CLI for the Attack Shark X11 (2.4G dongle 1d57:fa60 or wired 1d57:2126).

Protocol recovered from ATTACK SHARK X11 SOFT.exe (AttackShark.exe, model 4).
Transport: HID feature reports on the vendor interface (the one that declares report 0xA0).
  read  report R: SET_FEATURE [A0, R, len, 00, 01, 00, 00, 00]; wait until GET_FEATURE(A0)[1]==1; GET_FEATURE(R)
  write report R: SET_FEATURE of the full report (id, total length, payload..., checksum)
Reports: 4 = DPI table (56 B), 5 = light/misc (15 B), 6 = active-stage echo (9 B).
Needs read/write access to /dev/hidrawN (udev rule in 99-attackshark.rules).
"""
import argparse
import fcntl
import glob
import json
import os
import sys
import time

VID = 0x1D57
PIDS = (0xFA60, 0x2126)
SIZES = {4: 56, 5: 15, 6: 9}
STAGES = 8


def _ioc(n, nr):  # _IOC(_IOC_READ|_IOC_WRITE, 'H', nr, n)
    return (3 << 30) | (n << 16) | (ord("H") << 8) | nr


def find_hidraw():
    """Return /dev/hidrawN of the vendor config interface (declares feature report 0xA0)."""
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(f"{path}/device/uevent").read()
            desc = open(f"{path}/device/report_descriptor", "rb").read()
        except OSError:
            continue
        ids = [l.split("=")[1] for l in uevent.splitlines() if l.startswith("HID_ID=")]
        if not ids:
            continue
        _, vid, pid = (int(x, 16) for x in ids[0].split(":"))
        if vid == VID and pid in PIDS and b"\x85\xa0" in desc:
            return "/dev/" + os.path.basename(path)
    raise SystemExit("X11 config interface not found (dongle plugged in? mouse awake?)")


class Device:
    def __init__(self, path=None):
        self.fd = os.open(path or find_hidraw(), os.O_RDWR)

    def set_feature(self, buf):
        fcntl.ioctl(self.fd, _ioc(len(buf), 0x06), bytes(buf))

    def get_feature(self, rid, n):
        b = bytearray(n)
        b[0] = rid
        fcntl.ioctl(self.fd, _ioc(n, 0x07), b)
        return bytes(b)

    def read(self, rid, retries=200):
        """Handshake + fetch. The mouse must be awake (move it) or the 0xA0 flag never goes to 1."""
        n = SIZES[rid]
        for i in range(retries):
            if i == 2:
                print("waiting for the mouse: move it to wake it up...", file=sys.stderr)
            self.set_feature([0xA0, rid, n, 0, 1, 0, 0, 0])
            for _ in range(10):
                time.sleep(0.05)
                if self.get_feature(0xA0, 8)[1] == 1:
                    return self.get_feature(rid, n)
        raise TimeoutError("mouse did not answer (asleep? move it and retry)")

    def write(self, buf, retries=5):
        if not getattr(self, "begun", False):  # the vendor app sends this before every apply; light writes are ignored without it
            self.begun = True
            self.write(bytes([0x0C, 0x0A, 0x01, 0xFE, 0x01, 0xFE, 0, 0, 0, 0]))
        for i in range(retries):
            try:
                self.set_feature(buf)
                time.sleep(0.2)
                return
            except OSError:
                if i == retries - 1:
                    raise
                time.sleep(0.2)


LIGHT_MODES = ["LED Off", "Static", "Breathing", "Neon", "Color Breathing", "Static DPI", "Breathing DPI"]
BATTERY_STATUS = {1: "discharging", 2: "charging", 3: "low battery"}


def battery(dev, timeout=5.0):
    """Wait for input report 3 [03 55 40 status percent] (sent while the mouse is awake)."""
    import select
    end = time.time() + timeout
    while time.time() < end:
        if select.select([dev.fd], [], [], 0.5)[0]:
            r = os.read(dev.fd, 64)
            if len(r) >= 5 and r[0] == 3 and r[2] == 0x40:
                return r[4], BATTERY_STATUS.get(r[3], f"status {r[3]}")
    return None


def csum_dpi(b):  # report 4: sum of bytes 3..49, big endian at 50..51
    s = sum(b[3:50]) & 0xFFFF
    return s >> 8, s & 0xFF


def csum_light(b):  # report 5: sum of bytes 3..10, big endian at 11..12
    s = sum(b[3:11]) & 0xFFFF
    return s >> 8, s & 0xFF


def dpi_decode(lo, hi, high_range):
    return ((lo | hi << 8) + 1) * (100 if high_range else 50)


def dpi_encode(dpi):
    """-> (value16, high_range). 50 DPI units up to 26000, 100 DPI units above (as the vendor app)."""
    if dpi <= 26000:
        return dpi // 50 - 1, False
    return dpi // 100 - 1, True


def parse_dpi(b):
    assert b[0] == 4 and b[1] == 0x38, b.hex()
    assert (b[50], b[51]) == csum_dpi(b), "bad checksum"
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
    assert b[0] == 5 and b[1] == 0x0F, b.hex()
    assert (b[11], b[12]) == csum_light(b), "bad checksum"
    return {
        "mode": b[3] >> 4,
        "rgb": tuple(b[6:9]),
        "brightness": b[5] & 0xF,  # 1..8
        "breath_speed": 9 - (b[4] & 0xF),  # 4..8 (stored inverted)
        "deep_sleep_s": (b[4] & 0xF0) | b[5] >> 4,  # seconds
        "sleep_min": b[9],  # 1..60
        "debounce_ms": b[10] * 2,  # raw 2..25
        "raw": b.hex(),
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


RATES = {125: 8, 250: 4, 500: 2, 1000: 1}  # report 6 byte 3 low nibble = interval in ms (measured)


def parse_rate(b):
    ms = b[3] & 0xF
    return 1000 // ms if ms in (1, 2, 4, 8) else None


def build_rate(raw, hz):
    b = bytearray(raw)
    b[3] = b[3] & 0xF0 | RATES[hz]
    b[4] = ~b[3] & 0xFF
    return bytes(b)


# Button functions: app code -> (type, a, b) bytes of report 8; from the table at 0x4e7368 of AttackShark.exe
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
BUTTON_DEFAULTS = [0x1, 0x2, 0x3, 0x6, 0x5, 0x4, 0x34, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0xb, 0xc]  # model 4 default code per slot (table 0x4e78a0); last two swapped: vendor order inverted the wheel on this mouse


# slot 8 = back side button (type 5), slot 7 = forward side button (type 6); the vendor default left slot 8 'off' (type 1)
X11_FIXES = {7: (5, 0, 0), 6: (6, 0, 0)}


def build_buttons(codes=None, keys=None, raw=None):
    """Report 8 (59 B): 18 slots x (type, a, b). codes = app function code per slot; keys = {slot: (mods, usage)} for code 0x10."""
    codes = codes or BUTTON_DEFAULTS
    raw = {**X11_FIXES, **(raw or {})}
    b = bytearray(59)
    b[0], b[1], b[2] = 8, 0x3B, 1
    for i, c in enumerate(codes):
        t, x, y = BUTTON_FUNCS[c]
        if c == 0x10:
            x, y = keys[i]
        if c == 0x11:  # macro: b2 = button number, one macro slot per button (FUN_004a26c0)
            y = i + 1
        if raw and i in raw:  # raw (type, a, b) override per 0-based slot
            t, x, y = raw[i]
        b[3 + 3 * i:6 + 3 * i] = bytes((t, x, y))
    s = sum(b[3:57]) & 0xFFFF
    b[57], b[58] = s >> 8, s & 0xFF
    return bytes(b)


# Report 9 (macro, FUN_004a2430): 131 B, sent as 3 feature reports. Decoded statically, not verified on hardware.
MOUSE_KEYS = {"lmb": 0xF1, "rmb": 0xF2, "mmb": 0xF3}


def key_usage(name):
    """HID usage code for a-z, 1-9, 0, enter, esc, space, tab, lmb/rmb/mmb."""
    if name in MOUSE_KEYS:
        return MOUSE_KEYS[name]
    if len(name) == 1 and name.isalpha():
        return 4 + ord(name.lower()) - 97
    if name in "1234567890" and len(name) == 1:
        return 30 + (int(name) - 1) % 10
    return {"enter": 40, "esc": 41, "space": 44, "tab": 43}[name]


def build_macro(slot, events, mode=0, loop=1, unknown=0):
    """events = [(key_usage, pressed, delay_ms)]; slot = button number 1..18. Returns the 3 reports to send."""
    if not 1 <= len(events) <= 46:
        raise ValueError("macro needs 1..46 events")
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


# Factory table of model 4, read from the reset routine of AttackShark.exe (0x447d00).
# Stage 6 is 40000 DPI there (> the 22000 sensor spec); kept as the vendor app has it.
FACTORY_DPI = {
    "stages": [{"enabled": i < 6, "dpi": d, "rgb": c} for i, (d, c) in enumerate([
        (1200, (255, 0, 0)), (2400, (0, 255, 0)), (3200, (0, 0, 255)), (5600, (255, 255, 0)),
        (8000, (0, 255, 255)), (40000, (255, 0, 255)), (50, (255, 64, 0)), (50, (255, 255, 255))])],
    "active": 1, "lift_off_mm": 1, "ripple": True, "angle_snap": False, "motion_sync": True,
}
FACTORY_RATE_HZ = 250


def show(dev):
    d = parse_dpi(dev.read(4))
    for i, s in enumerate(d["stages"]):
        if s["enabled"]:
            mark = "*" if i == d["active"] else " "
            print(f"{mark}stage {i + 1}: {s['dpi']:>6} DPI  #{bytes(s['rgb']).hex()}")
    print(f"lift-off {d['lift_off_mm']} mm, ripple {d['ripple']}, angle snap {d['angle_snap']}, "
          f"motion sync {d['motion_sync']}")
    l = parse_light(dev.read(5))
    name = LIGHT_MODES[l["mode"]] if l["mode"] < len(LIGHT_MODES) else "?"
    print(f"light mode {l['mode']} ({name}), color #{bytes(l['rgb']).hex()}, brightness {l['brightness']}/8, "
          f"breath speed {l['breath_speed']} (4-8)")
    print(f"sleep {l['sleep_min']} min, deep sleep {l['deep_sleep_s']} s, key debounce {l['debounce_ms']} ms")
    hz = parse_rate(dev.read(6))
    print(f"polling rate {hz} Hz" if hz else "polling rate unknown")
    b = battery(dev)
    print("battery: " + (f"{b[0]}% ({b[1]})" if b else "no report (mouse asleep)"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    p = sub.add_parser("dpi", help="set DPI of a stage")
    p.add_argument("stage", type=int, choices=range(1, STAGES + 1))
    p.add_argument("dpi", type=int)
    p = sub.add_parser("active", help="select active stage")
    p.add_argument("stage", type=int, choices=range(1, STAGES + 1))
    p = sub.add_parser("color", help="set color of a DPI stage (RRGGBB)")
    p.add_argument("stage", type=int, choices=range(1, STAGES + 1))
    p.add_argument("rgb")
    p = sub.add_parser("light", help="set light mode number and/or RGB color")
    p.add_argument("--mode", type=lambda s: LIGHT_MODES.index(s) if s in LIGHT_MODES else int(s),
                   help="0-6 or name: " + ", ".join(LIGHT_MODES))
    p.add_argument("--rgb")
    p.add_argument("--brightness", type=int, choices=range(1, 9))
    p.add_argument("--breath-speed", type=int, choices=range(4, 9))
    p = sub.add_parser("sleep", help="sleep minutes / deep-sleep seconds / key debounce ms")
    p.add_argument("--min", type=int, choices=range(1, 61))
    p.add_argument("--deep", type=int, choices=range(1, 61))
    p.add_argument("--debounce", type=int, choices=range(4, 51, 2))
    p = sub.add_parser("rate", help="polling rate")
    p.add_argument("hz", type=int, choices=sorted(RATES))
    sub.add_parser("defaults", help="write the vendor app factory DPI table + 250 Hz (light/sleep untouched)")
    sub.add_parser("buttons-default", help="write the vendor app default button map")
    p = sub.add_parser("button", help="assign a button (1-18) a function code (hex, see BUTTON_FUNCS); map kept in ~/.config/attackshark_buttons.json")
    p.add_argument("slot", type=int, choices=range(1, 19))
    p.add_argument("code", type=lambda s: int(s, 16))
    p = sub.add_parser("macro", help="write macro for a button and assign it, e.g. macro 4 --loop 3 +a:30 -a:30")
    p.add_argument("slot", type=int, choices=range(1, 19))
    p.add_argument("events", nargs="+", help="+key:delay_ms (press) or -key:delay_ms (release)")
    p.add_argument("--mode", type=int, choices=range(3), default=0)
    p.add_argument("--loop", type=int, default=1)
    sub.add_parser("raw", help="dump reports 4/5/6")
    a = ap.parse_args()

    dev = Device()
    if a.cmd == "show":
        return show(dev)
    if a.cmd == "raw":
        for r in (4, 5, 6):
            print(r, dev.read(r).hex())
        return
    if a.cmd in ("dpi", "active", "color"):
        raw = dev.read(4)
        cfg = parse_dpi(raw)
        s = cfg["stages"][a.stage - 1]
        if a.cmd == "dpi":
            if not 50 <= a.dpi <= 22000 or a.dpi % 50:
                sys.exit("DPI must be a multiple of 50 in 50..22000")
            s["dpi"], s["enabled"] = a.dpi, True
        elif a.cmd == "active":
            cfg["active"] = a.stage - 1
            s["enabled"] = True
        else:
            s["rgb"] = tuple(bytes.fromhex(a.rgb.lstrip("#")))
        dev.write(build_dpi(raw, cfg))
        return show(dev)
    if a.cmd == "light":
        raw = dev.read(5)
        rgb = tuple(bytes.fromhex(a.rgb.lstrip("#"))) if a.rgb else None
        dev.write(build_light(raw, a.mode, rgb, a.brightness, a.breath_speed))
        return show(dev)
    if a.cmd == "defaults":
        dev.write(build_dpi(dev.read(4), FACTORY_DPI))
        time.sleep(1)  # the mouse rewrites report 6 itself after a table change; a write right away is lost
        for _ in range(3):
            r6 = dev.read(6)
            if parse_rate(r6) == FACTORY_RATE_HZ:
                break
            dev.write(build_rate(r6, FACTORY_RATE_HZ))
        return show(dev)
    if a.cmd == "buttons-default":
        dev.write(build_buttons())
        return print("default button map written")
    if a.cmd in ("button", "macro"):
        cfg = os.path.expanduser("~/.config/attackshark_buttons.json")
        try:
            codes = json.load(open(cfg))
        except (OSError, ValueError):
            codes = list(BUTTON_DEFAULTS)  # report 8 cannot be read back, so the map is kept here
        code = a.code if a.cmd == "button" else 0x11
        if code not in BUTTON_FUNCS or code == 0x10:
            sys.exit("unknown function code")
        codes[a.slot - 1] = code
        if 0x1 not in codes:
            sys.exit("keep at least one button as Left Click (0x1)")
        if a.cmd == "macro":
            ev = [(key_usage(e[1:].split(":")[0]), e[0] == "+", int(e.split(":")[1])) for e in a.events]
            for r in build_macro(a.slot, ev, a.mode, a.loop):
                dev.write(r)
        dev.write(build_buttons(codes))
        os.makedirs(os.path.dirname(cfg), exist_ok=True)
        json.dump(codes, open(cfg, "w"))
        return print("written")
    if a.cmd == "rate":
        dev.write(build_rate(dev.read(6), a.hz))
        return show(dev)
    if a.cmd == "sleep":
        raw = dev.read(5)
        dev.write(build_light(raw, sleep_min=a.min, deep_sleep_s=a.deep, debounce_ms=a.debounce))
        return show(dev)


if __name__ == "__main__":
    main()
