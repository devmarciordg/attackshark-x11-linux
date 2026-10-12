#!/usr/bin/env python3
"""GTK4 front-end for attackshark_x11 (DPI stages, colors, light). Run: python3 attackshark_gui.py"""
import colorsys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

import attackshark_x11 as x11  # noqa: E402


def rgba(rgb):
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = *(v / 255 for v in rgb), 1
    return c


def to_rgb(c):
    return tuple(round(v * 255) for v in (c.red, c.green, c.blue))


def vivid(rgb):
    # RGB LEDs wash out pastel colors; the vendor palette is fully saturated, so max out S and V.
    h, sat, _ = colorsys.rgb_to_hsv(*(v / 255 for v in rgb))
    if sat < 0.1:  # white/grey: keep as is
        return rgb
    return tuple(round(v * 255) for v in colorsys.hsv_to_rgb(h, 1, 1))


class App(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Attack Shark X11")
        self.raw4 = self.raw5 = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for s in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{s}")(12)
        self.set_child(box)

        grid = Gtk.Grid(column_spacing=8, row_spacing=4)
        box.append(Gtk.Label(label="DPI stages", xalign=0))
        box.append(grid)
        for j, t in enumerate(("On", "DPI", "Color", "Active")):
            grid.attach(Gtk.Label(label=t), j, 0, 1, 1)
        self.rows = []
        first = None
        for i in range(x11.STAGES):
            en = Gtk.CheckButton()
            dpi = Gtk.SpinButton.new_with_range(50, 42000, 50)
            col = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
            act = Gtk.CheckButton(group=first)
            first = first or act
            for j, w in enumerate((en, dpi, col, act)):
                grid.attach(w, j, i + 1, 1, 1)
            self.rows.append((en, dpi, col, act))

        self.lod = Gtk.DropDown.new_from_strings(["1 mm", "2 mm"])
        self.ripple = Gtk.CheckButton(label="Ripple control")
        self.snap = Gtk.CheckButton(label="Angle snap")
        self.sync = Gtk.CheckButton(label="Motion sync")
        box.append(Gtk.Label(label="Sensor", xalign=0))
        lod_row = Gtk.Box(spacing=8)
        lod_row.append(Gtk.Label(label="Lift-off distance"))
        lod_row.append(self.lod)
        for w in (lod_row, self.ripple, self.snap, self.sync):
            box.append(w)

        box.append(Gtk.Label(label="Light", xalign=0))
        light = Gtk.Box(spacing=8)
        self.mode = Gtk.DropDown.new_from_strings(x11.LIGHT_MODES)
        self.lcolor = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
        for w in (Gtk.Label(label="Mode"), self.mode, Gtk.Label(label="Color"), self.lcolor):
            light.append(w)
        box.append(light)
        self.battery = Gtk.Label(label="Battery: n/a", xalign=0)
        box.append(self.battery)

        box.append(Gtk.Label(label="Performance", xalign=0))
        self.rate = Gtk.DropDown.new_from_strings([f"{hz} Hz" for hz in sorted(x11.RATES)])
        self.spins = {}
        perf = Gtk.Grid(column_spacing=8, row_spacing=4)
        fields = [("rate", "Polling rate", None), ("brightness", "Brightness (1-8)", (1, 8, 1)),
                  ("breath_speed", "Breathing speed (4-8)", (4, 8, 1)),
                  ("sleep_min", "Sleep after (min)", (1, 60, 1)),
                  ("deep_sleep_s", "Deep sleep after (s)", (1, 60, 1)),
                  ("debounce_ms", "Key debounce (ms)", (4, 50, 2))]
        for r, (key, label, rng) in enumerate(fields):
            perf.attach(Gtk.Label(label=label, xalign=0), 0, r, 1, 1)
            w = self.rate if rng is None else Gtk.SpinButton.new_with_range(*rng)
            self.spins[key] = w
            perf.attach(w, 1, r, 1, 1)
        box.append(perf)
        self.vivid = Gtk.CheckButton(label="Vivid colors (saturate before sending)", active=True)
        box.append(self.vivid)
        bar = Gtk.Box(spacing=8)
        self.btn_read = Gtk.Button(label="Read from mouse")
        self.btn_apply = Gtk.Button(label="Apply")
        self.btn_factory = Gtk.Button(label="Load factory DPI")
        self.btn_factory.connect("clicked", lambda _: self.load_factory())
        self.btn_read.connect("clicked", lambda _: self.run(self.do_read))
        self.btn_apply.connect("clicked", lambda _: self.run(self.do_apply))
        bar.append(self.btn_read)
        bar.append(self.btn_apply)
        bar.append(self.btn_factory)
        box.append(bar)
        self.status = Gtk.Label(label="", xalign=0, wrap=True)
        box.append(self.status)
        self.run(self.do_read)

    # -- threading: device calls may wait for the mouse to wake up
    def run(self, fn, *a):
        self.set_busy(True, "Talking to the mouse (move it to wake it up)...")
        args = a if fn != self.do_apply else (self.collect(),)

        def work():
            try:
                res = fn(*args)
                GLib.idle_add(self.done, res, None)
            except Exception as e:  # noqa: BLE001 - shown to the user
                GLib.idle_add(self.done, None, e)

        threading.Thread(target=work, daemon=True).start()

    def set_busy(self, busy, msg=""):
        self.btn_read.set_sensitive(not busy)
        self.btn_apply.set_sensitive(not busy)
        self.status.set_text(msg)

    def done(self, res, err):
        self.set_busy(False, f"Error: {err}" if err else "OK")
        if res:
            self.fill(*res)

    def do_read(self):
        dev = x11.Device()
        raw4, raw5, raw6 = dev.read(4), dev.read(5), dev.read(6)
        return raw4, raw5, raw6, x11.battery(dev, 3)

    def do_apply(self, cfg):
        dev = x11.Device()
        raw4, raw5 = dev.read(4), dev.read(5)
        dev.write(x11.build_dpi(raw4, cfg["dpi"]))
        dev.write(x11.build_light(raw5, cfg["mode"], cfg["lrgb"], **cfg["light"]))
        dev.write(x11.build_rate(dev.read(6), cfg["hz"]))
        return dev.read(4), dev.read(5), dev.read(6), x11.battery(dev, 3)

    def load_factory(self):
        if self.raw4 and self.raw5:  # fills the form only; nothing is sent until Apply
            self.fill(x11.build_dpi(self.raw4, x11.FACTORY_DPI), self.raw5)
            self.rate.set_selected(sorted(x11.RATES).index(x11.FACTORY_RATE_HZ))
            self.status.set_text("Factory DPI loaded in the form. Click Apply to send.")

    def fill(self, raw4, raw5, raw6=None, bat=None):
        self.raw4, self.raw5 = raw4, raw5
        d, l = x11.parse_dpi(raw4), x11.parse_light(raw5)
        for i, (en, dpi, col, act) in enumerate(self.rows):
            s = d["stages"][i]
            en.set_active(s["enabled"])
            dpi.set_value(min(max(s["dpi"], 50), 42000))
            col.set_rgba(rgba(s["rgb"]))
            act.set_active(i == d["active"])
        self.lod.set_selected(d["lift_off_mm"] - 1)
        self.ripple.set_active(d["ripple"])
        self.snap.set_active(d["angle_snap"])
        self.sync.set_active(d["motion_sync"])
        self.mode.set_selected(min(l["mode"], len(x11.LIGHT_MODES) - 1))
        self.battery.set_text("Battery: " + (f"{bat[0]}% ({bat[1]})" if bat else "n/a"))
        self.lcolor.set_rgba(rgba(l["rgb"]))
        for k, w in self.spins.items():
            if k != "rate":
                w.set_value(l[k])
        hz = x11.parse_rate(raw6) if raw6 else None
        if hz in x11.RATES:
            self.rate.set_selected(sorted(x11.RATES).index(hz))

    def fix(self, rgb):
        return vivid(rgb) if self.vivid.get_active() else rgb

    def collect(self):
        stages, active = [], 0
        for i, (en, dpi, col, act) in enumerate(self.rows):
            stages.append({"enabled": en.get_active(), "dpi": int(dpi.get_value()),
                           "rgb": self.fix(to_rgb(col.get_rgba()))})
            if act.get_active():
                active = i
        stages[active]["enabled"] = True
        return {
            "dpi": {"stages": stages, "active": active, "lift_off_mm": self.lod.get_selected() + 1,
                    "ripple": self.ripple.get_active(), "angle_snap": self.snap.get_active(),
                    "motion_sync": self.sync.get_active()},
            "mode": self.mode.get_selected(), "hz": sorted(x11.RATES)[self.rate.get_selected()],
            "light": {k: int(self.spins[k].get_value()) for k in self.spins if k != "rate"}, "lrgb": self.fix(to_rgb(self.lcolor.get_rgba())),
        }


def activate(app):
    App(app).present()


if __name__ == "__main__":
    a = Gtk.Application(application_id="local.attackshark.x11")
    a.connect("activate", activate)
    a.run()
