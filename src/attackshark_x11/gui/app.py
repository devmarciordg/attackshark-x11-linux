#!/usr/bin/env python3
"""GTK4 front-end for attackshark_x11. Run: attackshark-x11-gui  (ATTACKSHARK_X11_FAKE=1 for a demo without hardware)."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

try:  # libadwaita is optional: it only gives the app the Adwaita look
    gi.require_version("Adw", "1")
    from gi.repository import Adw
    _Base = Adw.Application
except (ValueError, ImportError):
    _Base = Gtk.Application


def main():
    from .window import MainWindow
    app = _Base(application_id="io.github.attackshark_x11.AttackSharkX11")
    app.connect("activate", lambda a: MainWindow(a).present())
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
