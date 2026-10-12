"""Command line for the Attack Shark X11 (2.4G dongle 1d57:fa60 or wired 1d57:2126).

Protocol recovered from ATTACK SHARK X11 SOFT.exe; see README.md. Needs read/write access to /dev/hidrawN
(udev rule in 99-attackshark.rules). Exit codes: 0 ok, 1 error, 2 usage, 3 device not found, 4 no permission, 5 timeout.
"""
import argparse
import json
import sys

from . import __version__, factory, profiles
from .buttons import MACRO_FUNC, function_names, parse_function, validate_codes
from .hid import Device, DeviceError, DeviceNotFound, DevicePermissionError, DeviceTimeout, battery, read_events
from .macros import load_macro_file, validate_macro
from .protocol import LIGHT_MODES, RATES, STAGES, ProtocolError, build_dpi, build_light, build_rate, parse_dpi

EXIT = {DeviceNotFound: 3, DevicePermissionError: 4, DeviceTimeout: 5}


def _rgb(text):
    try:
        v = bytes.fromhex(text.lstrip("#"))
    except ValueError:
        v = b""
    if len(v) != 3:
        raise argparse.ArgumentTypeError(f"color must be RRGGBB, got {text!r}")
    return tuple(v)


def _mode(s):
    if s in LIGHT_MODES:
        return LIGHT_MODES.index(s)
    try:
        m = int(s)
    except ValueError:
        m = -1
    if not 0 <= m < len(LIGHT_MODES):
        raise argparse.ArgumentTypeError("mode is 0-6 or one of: " + ", ".join(LIGHT_MODES))
    return m


def state(dev, with_battery=True):
    """Everything readable from the mouse, JSON friendly."""
    s = profiles.snapshot(dev)
    s.pop("buttons")
    if with_battery:
        b = battery(dev)
        s["battery"] = {"percent": b[0], "status": b[1]} if b else None
    return s


def show(dev, as_json=False):
    s = state(dev)
    if as_json:
        return print(json.dumps(s, indent=2))
    d, l = s["dpi"], s["light"]
    for i, st in enumerate(d["stages"]):
        if st["enabled"]:
            mark = "*" if i == d["active"] else " "
            print(f"{mark}stage {i + 1}: {st['dpi']:>6} DPI  #{bytes(st['rgb']).hex()}")
    print(f"lift-off {d['lift_off_mm']} mm, ripple {d['ripple']}, angle snap {d['angle_snap']}, "
          f"motion sync {d['motion_sync']}")
    name = LIGHT_MODES[l["mode"]] if l["mode"] < len(LIGHT_MODES) else "?"
    print(f"light mode {l['mode']} ({name}), color #{bytes(l['rgb']).hex()}, brightness {l['brightness']}/8, "
          f"breath speed {l['breath_speed']} (4-8)")
    print(f"sleep {l['sleep_min']} min, deep sleep {l['deep_sleep_s']} s, key debounce {l['debounce_ms']} ms")
    print(f"polling rate {s['rate_hz']} Hz" if s["rate_hz"] else "polling rate unknown")
    b = s["battery"]
    print("battery: " + (f"{b['percent']}% ({b['status']})" if b else "no report (mouse asleep)"))


def build_parser():
    ap = argparse.ArgumentParser(prog="attackshark-x11", description=__doc__.splitlines()[0])
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--device", help="hidraw path (default: autodetect)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    stage = dict(type=int, choices=range(1, STAGES + 1))
    p = sub.add_parser("show", help="print current settings")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("dpi", help="set DPI of a stage")
    p.add_argument("stage", **stage)
    p.add_argument("dpi", type=int)
    p = sub.add_parser("active", help="select active stage")
    p.add_argument("stage", **stage)
    p = sub.add_parser("color", help="set color of a DPI stage (RRGGBB)")
    p.add_argument("stage", **stage)
    p.add_argument("rgb", type=_rgb)
    p = sub.add_parser("light", help="set light mode and/or RGB color")
    p.add_argument("--mode", type=_mode, help="0-6 or name: " + ", ".join(LIGHT_MODES))
    p.add_argument("--rgb", type=_rgb)
    p.add_argument("--brightness", type=int, choices=range(1, 9))
    p.add_argument("--breath-speed", type=int, choices=range(4, 9))
    p = sub.add_parser("sleep", help="sleep minutes / deep-sleep seconds / key debounce ms")
    p.add_argument("--min", type=int, choices=range(1, 61))
    p.add_argument("--deep", type=int, choices=range(1, 61))
    p.add_argument("--debounce", type=int, choices=range(4, 51, 2))
    p = sub.add_parser("rate", help="polling rate")
    p.add_argument("hz", type=int, choices=sorted(RATES))
    p = sub.add_parser("defaults", help="write a factory DPI table + polling rate (light/sleep untouched)")
    p.add_argument("--preset", choices=sorted(factory.PRESETS), default=factory.DEFAULT_PRESET,
                   help="ms4 (default) or ms13; which one matches the X11 is unverified")
    sub.add_parser("buttons-default", help="write the vendor default button map")
    sub.add_parser("functions", help="list button function codes")
    p = sub.add_parser("button", help="assign a function to a button, e.g. button 4 0x34 | button 4 key:ctrl+c | button 4 'Left Click'")
    p.add_argument("slot", type=int, choices=range(1, 19))
    p.add_argument("function", help="hex code, function name, key:<combo> or macro (see `functions`)")
    p = sub.add_parser("macro", help="write a macro for a button and assign it, e.g. macro 4 --loop 3 +a:30 -a:30")
    p.add_argument("slot", type=int, choices=range(1, 19))
    p.add_argument("events", nargs="*", help="+key:delay_ms (press) or -key:delay_ms (release)")
    p.add_argument("--file", help="JSON macro file instead of events")
    p.add_argument("--mode", type=int, choices=range(3), default=0)
    p.add_argument("--loop", type=int, default=1)
    p = sub.add_parser("profile", help="whole-device profiles")
    ps = p.add_subparsers(dest="pcmd", required=True)
    for n, h in (("save", "read the mouse and store a profile"), ("load", "write a stored profile to the mouse"),
                 ("delete", "remove a stored profile")):
        ps.add_parser(n, help=h).add_argument("name")
    ps.add_parser("list", help="list stored profiles")
    q = ps.add_parser("export", help="copy a stored profile to a file")
    q.add_argument("name")
    q.add_argument("path")
    q = ps.add_parser("import", help="store a profile from a file")
    q.add_argument("path")
    q.add_argument("--name")
    sub.add_parser("raw", help="dump reports 4/5/6")
    p = sub.add_parser("monitor", help="print live input events (DPI stage, battery, polling, light); Ctrl+C to stop")
    p.add_argument("--json", action="store_true")
    return ap


def run(a):
    """Dispatch a parsed command. Raises on expected errors (handled by main)."""
    if a.cmd == "profile" and a.pcmd in ("list", "export", "import", "delete"):  # no hardware needed
        if a.pcmd == "list":
            return print("\n".join(profiles.list_profiles()))
        if a.pcmd == "export":
            return profiles.export_profile(a.name, a.path)
        if a.pcmd == "delete":
            return profiles.delete(a.name)
        return print(f"imported as {profiles.import_profile(a.path, a.name)}")
    if a.cmd == "functions":
        for c, n in sorted(function_names().items()):
            print(f"0x{c:02x}  {n}")
        return
    code = key = m = None
    if a.cmd == "button":
        code, key = parse_function(a.function)
        if code == MACRO_FUNC:
            raise ValueError("use the `macro` command to define and assign a macro")
    if a.cmd == "macro":
        if bool(a.events) == bool(a.file):
            raise ValueError("give either events or --file")
        m = load_macro_file(a.file) if a.file else validate_macro(
            {"mode": a.mode, "loop": a.loop, "events": a.events})

    dev = Device(a.device)
    try:
        _hw(dev, a, code, key, m)
    finally:
        dev.close()


def _hw(dev, a, code, key, macro):
    if a.cmd == "show":
        return show(dev, a.json)
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
                raise ValueError("DPI must be a multiple of 50 in 50..22000")
            s["dpi"], s["enabled"] = a.dpi, True
        elif a.cmd == "active":
            cfg["active"] = a.stage - 1
            s["enabled"] = True
        else:
            s["rgb"] = a.rgb
        dev.write(build_dpi(raw, cfg))
        return show(dev)
    if a.cmd == "light":
        dev.write(build_light(dev.read(5), a.mode, a.rgb, a.brightness, a.breath_speed))
        return show(dev)
    if a.cmd == "sleep":
        dev.write(build_light(dev.read(5), sleep_min=a.min, deep_sleep_s=a.deep, debounce_ms=a.debounce))
        return show(dev)
    if a.cmd == "rate":
        dev.write(build_rate(dev.read(6), a.hz))
        return show(dev)
    if a.cmd == "defaults":
        factory.apply_preset(dev, a.preset)
        return show(dev)
    if a.cmd == "buttons-default":
        profiles.reset_buttons(dev)
        return print("default button map written")
    if a.cmd in ("button", "macro"):
        st = profiles.load_buttons()  # report 8 cannot be read back, so the map is kept in the config dir
        if a.cmd == "macro":
            code, st["macros"][str(a.slot)] = MACRO_FUNC, macro
        st["codes"][a.slot - 1] = code
        if key:
            st["keys"][str(a.slot - 1)] = list(key)
        else:
            st["keys"].pop(str(a.slot - 1), None)
        validate_codes(st["codes"])
        profiles.write_buttons(dev, st)
        profiles.save_buttons(st)
        return print("written")
    if a.cmd == "profile":
        if a.pcmd == "save":
            profiles.save(a.name, profiles.snapshot(dev))
            return print(f"saved profile {a.name}")
        profiles.apply_profile(dev, profiles.load(a.name))
        return print(f"loaded profile {a.name}")
    if a.cmd == "monitor":
        try:
            for ev in read_events(dev):
                if a.json:
                    print(json.dumps(ev), flush=True)
                else:
                    print(" ".join(f"{k}={v}" for k, v in ev.items() if k != "raw"), flush=True)
        except KeyboardInterrupt:
            pass


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        run(a)
    except KeyboardInterrupt:
        return 130
    except (DeviceError, ProtocolError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return next((c for t, c in EXIT.items() if isinstance(e, t)), 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
