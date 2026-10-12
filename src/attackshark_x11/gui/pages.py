"""One Gtk page per feature group. Each page reads/writes the device only through win.run (worker thread)."""
import colorsys
import json
import os
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from .. import buttons, factory, profiles, protocol  # noqa: E402
from ..macros import load_macro_file, save_macro_file, validate_macro  # noqa: E402
from . import keys, worker  # noqa: E402
from .i18n import tr  # noqa: E402

RATES = sorted(protocol.RATES)
MODE_LABELS = ["The number of times to play", "Any key press stops playing", "Press and hold, release stops"]


def rgba(rgb):
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = *(v / 255 for v in rgb), 1
    return c


def to_rgb(c):
    return tuple(round(v * 255) for v in (c.red, c.green, c.blue))


def vivid(rgb):
    # RGB LEDs wash out pastel colors; the vendor palette is fully saturated, so max out S and V.
    h, sat, _ = colorsys.rgb_to_hsv(*(v / 255 for v in rgb))
    if sat < 0.1:
        return tuple(rgb)
    return tuple(round(v * 255) for v in colorsys.hsv_to_rgb(h, 1, 1))


def color_button():
    return Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())


class Page(Gtk.ScrolledWindow):
    def __init__(self, win):
        super().__init__(hexpand=True, vexpand=True)
        self.win = win
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_bottom=12,
                           margin_start=12, margin_end=12)
        self.set_child(self.box)

    def heading(self, text):
        self.box.append(Gtk.Label(label=tr(text), xalign=0, css_classes=["heading"]))

    def row(self, label, widget):
        r = Gtk.Box(spacing=8)
        r.append(Gtk.Label(label=tr(label), xalign=0, hexpand=True))
        r.append(widget)
        self.box.append(r)
        return widget

    def apply_button(self, cb):
        b = Gtk.Button(label=tr("Apply"), halign=Gtk.Align.END, css_classes=["suggested-action"])
        b.connect("clicked", lambda _: cb())
        self.box.append(b)
        return b

    def fill(self, state):  # overridden by pages that mirror device state
        pass


class DpiPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.heading("DPI stages")
        grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        for j, t in enumerate(("On", "DPI", "Color", "Active")):
            grid.attach(Gtk.Label(label=tr(t)), j, 0, 1, 1)
        self.rows, first = [], None
        for i in range(protocol.STAGES):
            en = Gtk.CheckButton()
            dpi = Gtk.SpinButton.new_with_range(50, 42000, 50)
            col = color_button()
            act = Gtk.CheckButton(group=first)
            first = first or act
            for j, w in enumerate((en, dpi, col, act)):
                grid.attach(w, j, i + 1, 1, 1)
            self.rows.append((en, dpi, col, act))
        self.box.append(grid)
        self.heading("Sensor")
        self.lod = self.row("Lift-off distance", Gtk.DropDown.new_from_strings(["1 mm", "2 mm"]))
        self.ripple = self.row("Ripple control", Gtk.Switch(valign=Gtk.Align.CENTER))
        self.snap = self.row("Angle snap", Gtk.Switch(valign=Gtk.Align.CENTER))
        self.sync = self.row("Motion sync", Gtk.Switch(valign=Gtk.Align.CENTER))
        self.vivid = Gtk.CheckButton(label=tr("Vivid colors (saturate before sending)"), active=True)
        self.box.append(self.vivid)
        self.heading("Factory preset")
        self.preset = Gtk.DropDown.new_from_strings(list(factory.PRESETS))
        self.row("Factory preset", self.preset)
        self.box.append(Gtk.Label(label=tr("Unverified: which preset the X11 really uses is not confirmed on hardware."),
                                  xalign=0, wrap=True, css_classes=["dim-label"]))
        b = Gtk.Button(label=tr("Load preset into form"), halign=Gtk.Align.START)
        b.connect("clicked", lambda _: self.fill({"dpi": factory.PRESETS[self.preset_name()]["dpi"]}))
        self.box.append(b)
        self.apply_button(self.apply)

    def preset_name(self):
        return list(factory.PRESETS)[self.preset.get_selected()]

    def fill(self, state):
        d = state["dpi"]
        for i, (en, dpi, col, act) in enumerate(self.rows):
            s = d["stages"][i]
            en.set_active(s["enabled"])
            dpi.set_value(min(max(s["dpi"], 50), 42000))
            col.set_rgba(rgba(s["rgb"]))
            act.set_active(i == d["active"])
        self.lod.set_selected(d["lift_off_mm"] - 1)
        for sw, k in ((self.ripple, "ripple"), (self.snap, "angle_snap"), (self.sync, "motion_sync")):
            sw.set_active(d[k])

    def collect(self):
        fix = vivid if self.vivid.get_active() else tuple
        stages, active = [], 0
        for i, (en, dpi, col, act) in enumerate(self.rows):
            stages.append({"enabled": en.get_active(), "dpi": int(dpi.get_value()), "rgb": fix(to_rgb(col.get_rgba()))})
            if act.get_active():
                active = i
        stages[active]["enabled"] = True
        return {"stages": stages, "active": active, "lift_off_mm": self.lod.get_selected() + 1,
                "ripple": self.ripple.get_active(), "angle_snap": self.snap.get_active(),
                "motion_sync": self.sync.get_active()}

    def apply(self):
        self.win.run(worker.apply_dpi, self.collect())


class PerformancePage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.heading("Performance")
        self.rate = self.row("Polling rate", Gtk.DropDown.new_from_strings([f"{hz} Hz" for hz in RATES]))
        self.sleep = self.row("Sleep after (min)", Gtk.SpinButton.new_with_range(1, 60, 1))
        self.deep = self.row("Deep sleep after (s)", Gtk.SpinButton.new_with_range(1, 3600, 1))
        self.deb = self.row("Key debounce (ms)", Gtk.SpinButton.new_with_range(4, 50, 2))
        self.apply_button(self.apply)

    def fill(self, state):
        l = state["light"]
        if state["rate_hz"] in RATES:
            self.rate.set_selected(RATES.index(state["rate_hz"]))
        self.sleep.set_value(l["sleep_min"])
        self.deep.set_value(l["deep_sleep_s"])
        self.deb.set_value(l["debounce_ms"])

    def apply(self):
        hz, light = RATES[self.rate.get_selected()], dict(
            sleep_min=int(self.sleep.get_value()), deep_sleep_s=int(self.deep.get_value()),
            debounce_ms=int(self.deb.get_value()) // 2 * 2)

        def job(dev):
            dev.write(protocol.build_rate(dev.read(6), hz))
            return worker.apply_light(dev, **light)
        self.win.run(job)


class LightPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.heading("Lighting")
        self.mode = self.row("Mode", Gtk.DropDown.new_from_strings([tr(m) for m in protocol.LIGHT_MODES]))
        self.color = self.row("Color", color_button())
        self.bright = self.row("Brightness (1-8)", Gtk.SpinButton.new_with_range(1, 8, 1))
        self.speed = self.row("Breathing speed (4-8)", Gtk.SpinButton.new_with_range(4, 8, 1))
        self.vivid = Gtk.CheckButton(label=tr("Vivid colors (saturate before sending)"), active=True)
        self.box.append(self.vivid)
        self.apply_button(self.apply)

    def fill(self, state):
        l = state["light"]
        self.mode.set_selected(min(l["mode"], len(protocol.LIGHT_MODES) - 1))
        self.color.set_rgba(rgba(l["rgb"]))
        self.bright.set_value(min(max(l["brightness"], 1), 8))
        self.speed.set_value(min(max(l["breath_speed"], 4), 8))

    def apply(self):
        rgb = to_rgb(self.color.get_rgba())
        self.win.run(worker.apply_light, mode=self.mode.get_selected(), rgb=vivid(rgb) if self.vivid.get_active() else rgb,
                     brightness=int(self.bright.get_value()), breath_speed=int(self.speed.get_value()))


# -- buttons

def macro_dir():
    return os.path.join(profiles.config_dir(), "macros")


def list_macros():
    d = macro_dir()
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def macro_path(name):
    if not name or os.sep in name or name.startswith("."):
        raise ValueError(f"bad macro name {name!r}")
    os.makedirs(macro_dir(), exist_ok=True)
    return os.path.join(macro_dir(), name + ".json")


class ButtonRow:
    def __init__(self, page, slot, names):
        self.page, self.slot = page, slot
        self.box = Gtk.Box(spacing=8)
        self.box.append(Gtk.Label(label=tr("Button {n}", n=slot + 1), xalign=0, width_chars=10))
        self.func = Gtk.DropDown.new_from_strings([tr(n) if not n.startswith("Function") else n for n in names.values()])
        self.codes = list(names)
        self.func.connect("notify::selected", lambda *_: self.sync())
        self.box.append(self.func)
        self.key = Gtk.Button(label=tr("Click, then press a key combination"))
        self.key.connect("clicked", self.begin_capture)
        self.combo = None
        self.macro = Gtk.DropDown.new_from_strings([tr("(no macro)")])
        self.macro_names = [None]
        self.box.append(self.key)
        self.box.append(self.macro)
        ctl = Gtk.EventControllerKey()
        ctl.connect("key-pressed", self.on_key)
        self.key.add_controller(ctl)
        self.capturing = False

    @property
    def code(self):
        return self.codes[self.func.get_selected()]

    def sync(self):
        self.key.set_visible(self.code == buttons.KEY_FUNC)
        self.macro.set_visible(self.code == buttons.MACRO_FUNC)

    def begin_capture(self, _):
        self.capturing = True
        self.key.set_label(tr("Press keys..."))
        self.key.grab_focus()

    def on_key(self, ctl, keyval, keycode, state):
        if not self.capturing or keys.is_modifier(keyval):
            return False
        combo = keys.combo_from_event(keyval, state)
        if combo:  # unsupported keys keep the capture open
            self.set_combo(combo)
            self.capturing = False
        return True

    def set_combo(self, combo):
        self.combo = tuple(combo) if combo else None
        self.key.set_label(keys.combo_text(*self.combo) if self.combo else tr("Click, then press a key combination"))

    def set_macros(self, names, current):
        self.macro_names = [None] + names
        self.macro.set_model(Gtk.StringList.new([tr("(no macro)")] + names))
        if current in names:
            self.macro.set_selected(names.index(current) + 1)


class ButtonsPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.heading("Buttons")
        names = buttons.function_names()
        names[buttons.KEY_FUNC] = "Keyboard Key"
        names[buttons.MACRO_FUNC] = "Macro"
        names = dict(sorted(names.items(), key=lambda kv: (kv[0] not in (1, 2, 3), kv[1])))
        self.rows = [ButtonRow(self, i, names) for i in range(buttons.SLOTS)]
        for r in self.rows:
            self.box.append(r.box)
        bar = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        reset = Gtk.Button(label=tr("Reset buttons to default"))
        reset.connect("clicked", lambda _: self.load(profiles.default_buttons()))
        bar.append(reset)
        self.box.append(bar)
        self.apply_button(self.apply)
        self.load(profiles.load_buttons())

    def load(self, state):
        macros = list_macros()
        for i, r in enumerate(self.rows):
            r.func.set_selected(r.codes.index(state["codes"][i]) if state["codes"][i] in r.codes else 0)
            r.set_combo(state["keys"].get(str(i)))
            r.set_macros(macros, state["macros"].get(str(i + 1), {}).get("name"))
            r.sync()

    def refresh_macros(self):
        self.load(self.collect(strict=False))

    def collect(self, strict=True):
        state = {"codes": [r.code for r in self.rows], "keys": {}, "macros": {}}
        for i, r in enumerate(self.rows):
            if r.code == buttons.KEY_FUNC:
                if r.combo:
                    state["keys"][str(i)] = list(r.combo)
                elif strict:
                    raise ValueError(tr("Button {n}: pick a key combination first.", n=i + 1))
            if r.code == buttons.MACRO_FUNC:
                name = r.macro_names[r.macro.get_selected()]
                if name:
                    m = load_macro_file(macro_path(name))
                    state["macros"][str(i + 1)] = {**m, "name": name}
                elif strict:
                    raise ValueError(tr("Button {n}: pick a macro first.", n=i + 1))
        if strict and 1 not in state["codes"]:
            raise ValueError(tr("Refused: at least one button must be Left Click."))
        return state

    def apply(self):
        try:
            state = self.collect()
        except (ValueError, OSError) as e:
            return self.win.show_error(e)
        self.win.confirm(tr("Write the button map?"),
                         tr("A wrong button map can lock you out of the mouse. Keep at least one button as Left Click."),
                         lambda: self.win.run(worker.apply_buttons, state), tr("Write"))


# -- macros

class MacroPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.heading("Macros")
        bar = Gtk.Box(spacing=6)
        for label, cb in (("New", self.new), ("Rename", self.rename), ("Delete", self.delete),
                          ("Import", self.import_), ("Export", self.export)):
            b = Gtk.Button(label=tr(label))
            b.connect("clicked", lambda _, cb=cb: cb())
            bar.append(b)
        self.box.append(bar)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        self.list.connect("row-selected", lambda *_: self.load_selected())
        self.box.append(self.list)
        self.mode = self.row("Mode", Gtk.DropDown.new_from_strings([tr(m) for m in MODE_LABELS]))
        self.loop = self.row("Loop times", Gtk.SpinButton.new_with_range(1, 255, 1))
        self.box.append(Gtk.Label(label=tr("Events, one per line: +key:ms press, -key:ms release"), xalign=0))
        self.text = Gtk.TextView(monospace=True, height_request=180, css_classes=["card"])
        self.box.append(self.text)
        self.rec_btn = Gtk.ToggleButton(label=tr("Record"), halign=Gtk.Align.START)
        self.rec_btn.connect("toggled", self.toggle_record)
        self.box.append(self.rec_btn)
        self.rec = None
        ctl = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        ctl.connect("key-pressed", self.on_press)
        ctl.connect("key-released", self.on_release)
        win.add_controller(ctl)
        b = Gtk.Button(label=tr("Save"), halign=Gtk.Align.END, css_classes=["suggested-action"])
        b.connect("clicked", lambda _: self.save())
        self.box.append(b)
        self.current = None
        self.reload()

    # list
    def reload(self, select=None):
        self.names = list_macros()
        while (r := self.list.get_row_at_index(0)):
            self.list.remove(r)
        for n in self.names:
            self.list.append(Gtk.Label(label=n, xalign=0, margin_top=6, margin_bottom=6, margin_start=8))
        if select in self.names:
            self.list.select_row(self.list.get_row_at_index(self.names.index(select)))
        else:
            self.current = None
        self.win.pages["buttons"].refresh_macros()

    def selected(self):
        r = self.list.get_selected_row()
        return self.names[r.get_index()] if r else None

    def load_selected(self):
        self.current = self.selected()
        if not self.current:
            return
        try:
            m = load_macro_file(macro_path(self.current))
        except (OSError, ValueError) as e:
            return self.win.show_error(e)
        self.mode.set_selected(m["mode"])
        self.loop.set_value(m["loop"])
        self.text.get_buffer().set_text("\n".join(m["events"]))

    def text_value(self):
        b = self.text.get_buffer()
        return b.get_text(b.get_start_iter(), b.get_end_iter(), False)

    def macro(self):
        return validate_macro({"mode": self.mode.get_selected(), "loop": int(self.loop.get_value()),
                               "events": keys.events_from_text(self.text_value())})

    def need(self):
        if not self.current:
            self.win.say(tr("Select a macro first."))
        return self.current

    # actions
    def new(self):
        def create(name):
            try:
                save_macro_file(macro_path(name), {"mode": 0, "loop": 1, "events": ["+a:30", "-a:30"]})
            except (OSError, ValueError) as e:
                return self.win.show_error(e)
            self.reload(name)
        self.win.ask_text(tr("New"), "", create)

    def rename(self):
        if not self.need():
            return
        old = self.current

        def go(name):
            try:
                os.rename(macro_path(old), macro_path(name))
            except (OSError, ValueError) as e:
                return self.win.show_error(e)
            self.reload(name)
        self.win.ask_text(tr("Rename"), old, go)

    def delete(self):
        if not self.need():
            return

        def go():
            os.remove(macro_path(self.current))
            self.reload()
            self.win.say(tr("Macro deleted."))
        self.win.confirm(tr("Delete this macro?"), self.current, go, tr("Delete"))

    def save(self):
        if not self.need():
            return
        try:
            save_macro_file(macro_path(self.current), self.macro())
        except (OSError, ValueError) as e:
            return self.win.show_error(e)
        self.win.say(tr("Macro saved."))
        self.win.pages["buttons"].refresh_macros()

    def import_(self):
        def go(path):
            try:
                m = load_macro_file(path)
                name = os.path.splitext(os.path.basename(path))[0]
                save_macro_file(macro_path(name), m)
            except (OSError, ValueError) as e:
                return self.win.show_error(e)
            self.reload(name)
        self.win.pick_file(False, "", go)

    def export(self):
        if not self.need():
            return
        try:
            m = self.macro()
        except ValueError as e:
            return self.win.show_error(e)
        self.win.pick_file(True, self.current + ".json", lambda p: save_macro_file(p, m))

    # recording
    def toggle_record(self, btn):
        if btn.get_active():
            self.rec = keys.Recorder()
            btn.set_label(tr("Stop"))
            self.text.get_buffer().set_text("")
        else:
            self.rec = None
            btn.set_label(tr("Record"))

    def _sync_text(self):
        self.text.get_buffer().set_text("\n".join(self.rec.lines))

    def on_press(self, ctl, keyval, keycode, state):
        if self.rec is None:
            return False
        self.rec.press(keyval, time.monotonic())
        self._sync_text()
        return True

    def on_release(self, ctl, keyval, keycode, state):
        if self.rec is not None:
            self.rec.release(keyval, time.monotonic())
            self._sync_text()


# -- profiles

class ProfilesPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.heading("Profiles")
        bar = Gtk.Box(spacing=6)
        for label, cb in (("Save current", self.save), ("Load", self.load), ("Rename", self.rename),
                          ("Delete", self.delete), ("Import", self.import_), ("Export", self.export)):
            b = Gtk.Button(label=tr(label))
            b.connect("clicked", lambda _, cb=cb: cb())
            bar.append(b)
        self.box.append(bar)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        self.box.append(self.list)
        self.heading("Reset to factory")
        self.preset = Gtk.DropDown.new_from_strings(list(factory.PRESETS))
        self.row("Factory preset", self.preset)
        self.box.append(Gtk.Label(label=tr("Unverified: which preset the X11 really uses is not confirmed on hardware."),
                                  xalign=0, wrap=True, css_classes=["dim-label"]))
        b = Gtk.Button(label=tr("Reset to factory"), halign=Gtk.Align.START, css_classes=["destructive-action"])
        b.connect("clicked", lambda _: self.reset())
        self.box.append(b)
        self.reload()

    def reload(self):
        self.names = profiles.list_profiles()
        while (r := self.list.get_row_at_index(0)):
            self.list.remove(r)
        for n in self.names:
            self.list.append(Gtk.Label(label=n, xalign=0, margin_top=6, margin_bottom=6, margin_start=8))

    def selected(self):
        r = self.list.get_selected_row()
        if not r:
            self.win.say(tr("Select a profile first."))
            return None
        return self.names[r.get_index()]

    def save(self):
        def go(name):
            def after(res, err):
                if err:
                    return self.win.show_error(err)
                self.reload()
                self.win.say(tr("Profile saved."))
            try:
                profiles._profile_path(name)  # validate the name before touching the device
            except ValueError as e:
                return self.win.show_error(e)
            self.win.worker.submit(lambda dev: profiles.save(name, profiles.snapshot(dev)), after)
        self.win.ask_text(tr("Save current"), "", go)

    def load(self):
        name = self.selected()
        if name:
            self.win.confirm(tr("Load"), tr("Load this profile into the mouse? This also writes the button map and macros."),
                             lambda: self.win.run(lambda dev: (profiles.apply_profile(dev, profiles.load(name)), worker.read_all(dev))[1],
                                                  done=lambda _: self.win.say(tr("Profile loaded."))), tr("Load"))

    def rename(self):
        old = self.selected()
        if not old:
            return

        def go(new):
            try:
                profiles.save(new, profiles.load(old))
                if new != old:
                    profiles.delete(old)
            except (OSError, ValueError) as e:
                return self.win.show_error(e)
            self.reload()
        self.win.ask_text(tr("Rename"), old, go)

    def delete(self):
        name = self.selected()
        if name:
            def go():
                profiles.delete(name)
                self.reload()
                self.win.say(tr("Profile deleted."))
            self.win.confirm(tr("Delete this profile?"), name, go, tr("Delete"))

    def import_(self):
        def go(path):
            try:
                profiles.import_profile(path)
            except (OSError, ValueError, json.JSONDecodeError) as e:
                return self.win.show_error(e)
            self.reload()
        self.win.pick_file(False, "", go)

    def export(self):
        name = self.selected()
        if name:
            def go(path):
                try:
                    profiles.export_profile(name, path)
                except (OSError, ValueError) as e:
                    self.win.show_error(e)
            self.win.pick_file(True, name + ".json", go)

    def reset(self):
        preset = list(factory.PRESETS)[self.preset.get_selected()]
        self.win.confirm(tr("Reset to factory"), tr("Reset the mouse to the factory preset and default buttons?"),
                         lambda: self.win.run(lambda dev: (profiles.reset(dev, preset), worker.read_all(dev))[1]),
                         tr("Reset to factory"))
