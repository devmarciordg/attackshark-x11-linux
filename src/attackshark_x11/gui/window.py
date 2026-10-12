"""Main window: sidebar of pages, error/asleep banner, battery, status line."""
import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .. import __version__, hid  # noqa: E402
from . import pages, worker as workermod  # noqa: E402
from .i18n import tr  # noqa: E402

BATTERY = "Battery: {pct}% ({status})"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app, worker=None):
        super().__init__(application=app, title=tr("Attack Shark X11"), default_width=860, default_height=700)
        self.worker = worker or workermod.Worker()
        self.busy = 0
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)
        self.build_header()

        self.banner = Gtk.Box(spacing=8, css_classes=["toolbar"], visible=False)
        self.banner_label = Gtk.Label(xalign=0, wrap=True, hexpand=True, selectable=True)
        retry = Gtk.Button(label=tr("Retry"))
        retry.connect("clicked", lambda _: self.refresh())
        self.banner.append(self.banner_label)
        self.banner.append(retry)
        outer.append(self.banner)

        body = Gtk.Box(vexpand=True)
        self.stack = Gtk.Stack(hexpand=True)
        self.pages = {}
        for key, title, cls in (("dpi", "DPI", pages.DpiPage), ("performance", "Performance", pages.PerformancePage),
                                ("light", "Lighting", pages.LightPage), ("buttons", "Buttons", pages.ButtonsPage),
                                ("macros", "Macros", pages.MacroPage), ("profiles", "Profiles", pages.ProfilesPage)):
            self.pages[key] = cls(self)
            self.stack.add_titled(self.pages[key], key, tr(title))
        side = Gtk.StackSidebar(stack=self.stack, width_request=170)
        body.append(side)
        body.append(Gtk.Separator())
        body.append(self.stack)
        outer.append(body)
        self.status = Gtk.Label(xalign=0, margin_start=12, margin_bottom=6, wrap=True)
        outer.append(self.status)
        if os.environ.get("ATTACKSHARK_X11_FAKE"):
            self.say(tr("Demo mode: no real mouse is used."))
        self.worker.start_monitor(self.on_event)
        self.connect("close-request", lambda _: self.worker.stop())
        self.refresh()

    def build_header(self):
        hb = Gtk.HeaderBar()
        self.battery = Gtk.Label(label=tr("Battery: n/a"))
        self.spinner = Gtk.Spinner()
        read = Gtk.Button(label=tr("Read from mouse"))
        read.connect("clicked", lambda _: self.refresh())
        about = Gtk.Button(icon_name="help-about-symbolic", tooltip_text=tr("About"))
        about.connect("clicked", lambda _: self.show_about())
        hb.pack_start(read)
        hb.pack_start(self.spinner)
        hb.pack_end(about)
        hb.pack_end(self.battery)
        self.set_titlebar(hb)

    # -- services for pages
    def say(self, msg):
        self.status.set_text(msg)

    def run(self, fn, *args, done=None):
        """Run fn(dev, *args) off the main thread. A dict result with 'dpi' refreshes the device-backed pages."""
        self.busy += 1
        self.spinner.start()
        self.say(tr("Working... (move the mouse if it is asleep)"))

        def finished(res, err):
            self.busy -= 1
            if not self.busy:
                self.spinner.stop()
            if err:
                return self.show_error(err)
            self.banner.set_visible(False)
            self.say(tr("Done."))
            if isinstance(res, dict) and "dpi" in res:
                for p in self.pages.values():
                    p.fill(res)
            if done:
                done(res)
        self.worker.submit(fn, finished, *args)

    def refresh(self):
        self.run(workermod.read_all)

    def show_error(self, err):
        kind = workermod.classify(err)
        msg = {"notfound": tr("Mouse not found. Plug in the dongle and move the mouse."),
               "permission": tr("No permission to open the device. Install the udev rule, then replug the dongle:") + "\n" + str(err),
               "asleep": tr("The mouse is asleep. Move the mouse, then press Retry.")}.get(kind)
        if kind == "asleep":
            self.battery.set_text(tr("Asleep"))
        self.banner_label.set_text(msg or tr("Error: {err}", err=err))
        self.banner.set_visible(True)
        self.say(tr("Error: {err}", err=err))

    def on_event(self, ev):
        if ev["event"] == "battery":
            self.battery.set_text(tr(BATTERY, pct=ev["percent"], status=tr(ev["status"])))

    def confirm(self, heading, body, on_yes, yes_label=None):
        d = Gtk.AlertDialog(message=heading, detail=body, buttons=[tr("Cancel"), yes_label or tr("OK")],
                            cancel_button=0, default_button=0)
        d.choose(self, None, lambda dlg, res: on_yes() if _choice(dlg, res) == 1 else None)

    def ask_text(self, title, default, cb):
        w = Gtk.Window(title=title, transient_for=self, modal=True, default_width=320)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_bottom=12,
                      margin_start=12, margin_end=12)
        entry = Gtk.Entry(text=default, activates_default=True)
        ok = Gtk.Button(label=tr("OK"), css_classes=["suggested-action"])
        box.append(Gtk.Label(label=tr("Name"), xalign=0))
        box.append(entry)
        box.append(ok)
        w.set_child(box)
        w.set_default_widget(ok)

        def go(*_):
            name = entry.get_text().strip()
            w.close()
            if name:
                cb(name)
        ok.connect("clicked", go)
        w.present()

    def pick_file(self, save, name, cb):
        d = Gtk.FileDialog()
        if save:
            d.set_initial_name(name)
        fn = d.save if save else d.open

        def done(dlg, res):
            try:
                f = (dlg.save_finish if save else dlg.open_finish)(res)
            except Exception:  # noqa: BLE001 - dialog cancelled
                return
            cb(f.get_path())
        fn(self, None, done)

    def show_about(self):
        a = Gtk.AboutDialog(transient_for=self, modal=True, program_name=tr("Attack Shark X11"), version=__version__,
                            comments=tr("Open source Linux configuration tool for the Attack Shark X11 mouse. Not affiliated with Attack Shark."),
                            license_type=Gtk.License.MIT_X11, logo_icon_name="input-mouse")
        a.present()


def _choice(dlg, res):
    try:
        return dlg.choose_finish(res)
    except Exception:  # noqa: BLE001 - dismissed
        return 0
