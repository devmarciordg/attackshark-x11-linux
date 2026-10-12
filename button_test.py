#!/usr/bin/env python3
"""Visual button-to-slot test. Maps slots 1-7 to keypad usages 0xB0-0xB6, asks for one physical button at a time, restores the default map at the end."""
import glob
import os
import select
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import attackshark_x11 as x  # noqa: E402

PHASES = ["Botão ESQUERDO", "Botão DIREITO", "SCROLL (apertar)", "Lateral de TRÁS", "Lateral da FRENTE", "Botão de DPI"]
SECS = 20


def keyboard_fd():
    for p in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        if "00001D57" in open(p + "/device/uevent").read() and open(p + "/device/report_descriptor", "rb").read()[:4] == bytes.fromhex("05010906"):
            return os.open("/dev/" + os.path.basename(p), os.O_RDONLY | os.O_NONBLOCK)  # first keyboard interface (hidraw2)


class Win(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Teste de botões X11", default_width=640, default_height=420)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=20, margin_bottom=20, margin_start=20, margin_end=20)
        self.set_child(box)
        self.step = Gtk.Label(label="Preparando...")
        self.big = Gtk.Label(label="...")
        self.count = Gtk.Label(label="")
        self.log = Gtk.Label(label="", xalign=0)
        for w, css in ((self.step, "title-4"), (self.big, "title-1"), (self.count, "title-2")):
            w.add_css_class(css)
            box.append(w)
        box.append(self.log)
        self.results = []
        threading.Thread(target=self.work, daemon=True).start()

    def ui(self, step=None, big=None, count=None, log=None):
        def f():
            if step is not None: self.step.set_text(step)
            if big is not None: self.big.set_markup(big)
            if count is not None: self.count.set_text(count)
            if log is not None: self.log.set_text(log)
        GLib.idle_add(f)

    def work(self):
        fd = keyboard_fd()
        try:
            self.ui(big="Acordando o mouse...", count="mexa o mouse")
            dev = x.Device()
            dev.read(6)
            codes, keys = list(x.BUTTON_DEFAULTS), {}
            for i in range(7):
                codes[i] = 0x10
                keys[i] = (0, 0xB0 + i)  # keypad 00/000/...: unbound on desktops
            dev.write(x.build_buttons(codes, keys))
            for n, name in enumerate(PHASES, 1):
                while select.select([fd], [], [], 0)[0]:
                    os.read(fd, 64)
                os.system(f'notify-send -u critical "X11 teste: FASE {n}/{len(PHASES)}" "Aperte UMA vez: {name}" 2>/dev/null')
                self.ui(step=f"FASE {n} de {len(PHASES)}", big=f"<span size='xx-large' weight='bold'>Aperte UMA vez:\n{name}</span>")
                end, got = time.time() + SECS, None
                while time.time() < end and got is None:
                    self.ui(count=f"{int(end - time.time())} s")
                    if select.select([fd], [], [], 0.3)[0]:
                        r = os.read(fd, 64)
                        if r[2]:
                            got = r[2] - 0xB0 + 1
                text = f"{name}: slot {got}" if got else f"{name}: nada detectado"
                self.results.append(text)
                os.system(f'notify-send "X11 teste" "{text}" 2>/dev/null')
                self.ui(big=f"<span size='xx-large' foreground='{'#2ec27e' if got else '#e01b24'}' weight='bold'>{text}</span>", log="\n".join(self.results))
                time.sleep(2.5)
            self.ui(step="Fim", big="<span size='xx-large' weight='bold'>Restaurando mapa padrão...</span>", count="")
        except Exception as e:  # noqa: BLE001
            self.results.append(f"erro: {e}")
            self.ui(big=f"erro: {e}")
        finally:
            try:
                x.Device().write(x.build_buttons())
                self.results.append("mapa padrão restaurado")
            except Exception as e:  # noqa: BLE001
                self.results.append(f"FALHA ao restaurar: {e}  (rode: python3 attackshark_x11.py buttons-default)")
            print("\n".join(self.results), flush=True)
            self.ui(big="<span size='xx-large' weight='bold'>Pronto. Pode fechar.</span>", log="\n".join(self.results))
            GLib.timeout_add_seconds(6, self.get_application().quit)


app = Gtk.Application(application_id="local.attackshark.buttontest")
app.connect("activate", lambda a: Win(a).present())
app.run()
