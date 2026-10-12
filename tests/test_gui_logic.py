"""GUI logic that needs no display: key conversion, macro recorder, i18n, worker."""
import pathlib
import re
import threading

import pytest

from attackshark_x11 import buttons, hid
from attackshark_x11.gui import i18n, keys, worker


def test_keys_combo():
    assert keys.combo_from_event(ord("a"), 0) == (0, 4)
    assert keys.combo_from_event(ord("C"), keys.CTRL | keys.SHIFT) == (3, 6)
    assert keys.combo_from_event(ord("!"), keys.SHIFT) == (2, buttons.KEY_USAGES["1"])
    assert keys.combo_from_event(0xFFBE, keys.ALT) == (4, buttons.KEY_USAGES["f1"])
    assert keys.combo_from_event(0xFF0D, keys.SUPER) == (8, 40)
    assert keys.combo_from_event(0xFFE1, 0) is None  # Shift_L alone
    assert keys.is_modifier(0xFFE1) and not keys.is_modifier(ord("a"))
    assert keys.combo_from_event(0x1000000, 0) is None


def test_recorder_and_text():
    r = keys.Recorder()
    r.press(ord("a"), 1.0)
    r.press(ord("a"), 1.01)  # auto-repeat ignored
    r.release(ord("a"), 1.05)
    r.release(ord("b"), 1.06)  # never pressed
    assert r.lines == ["+a:10", "-a:50"]
    assert keys.events_from_text("# c\n+a:30\n\n-a:30\n") == ["+a:30", "-a:30"]
    with pytest.raises(ValueError):
        keys.events_from_text("a:30")


def test_i18n():
    i18n.set_language("pt_BR.UTF-8")
    assert i18n.tr("Apply") == "Aplicar"
    assert i18n.tr("Button {n}", n=3) == "Botão 3"
    i18n.set_language("en_US.UTF-8")
    assert i18n.tr("Apply") == "Apply" and i18n.tr("unknown text") == "unknown text"
    i18n.set_language("pt")


def test_i18n_covers_every_literal():
    src = pathlib.Path(worker.__file__).parent
    used = set()
    for f in src.glob("*.py"):
        used |= set(re.findall(r'\btr\(\s*"((?:[^"\\]|\\.)*)"', f.read_text()))
    used |= set(re.findall(r'\(\s*"([A-Z][^"]*)",\s*(?:self\.\w+|\w+)\)', (src / "pages.py").read_text()))
    from attackshark_x11.protocol import LIGHT_MODES
    used |= set(LIGHT_MODES) | {"On", "DPI", "Color", "Active", "Performance", "Lighting", "Buttons", "Macros", "Profiles"}
    missing = sorted(s for s in used if s not in i18n.PT_BR)
    assert not missing, missing


def run_job(w, fn, *a, **kw):
    out = []
    done = threading.Event()
    w.submit(fn, lambda res, err: (out.append((res, err)), done.set()), *a, **kw)
    assert done.wait(5)
    return out[0]


def test_worker_read_and_apply(dev):
    w = worker.Worker(factory=lambda: dev, dispatch=lambda f: f())
    res, err = run_job(w, worker.read_all)
    assert err is None and res["rate_hz"] == 1000 and len(res["dpi"]["stages"]) == 8
    cfg = res["dpi"]
    cfg["stages"][0]["dpi"] = 1234 // 50 * 50
    res, err = run_job(w, worker.apply_dpi, cfg)
    assert err is None and res["dpi"]["stages"][0]["dpi"] == 1200
    res, err = run_job(w, worker.apply_light, mode=2, brightness=3)
    assert res["light"]["mode"] == 2 and res["light"]["brightness"] == 3
    res, err = run_job(w, worker.apply_rate, 500)
    assert res["rate_hz"] == 500
    w.stop()


def test_worker_errors_and_classification(dev):
    def boom():
        raise hid.DevicePermissionError("udev")
    w = worker.Worker(factory=boom, dispatch=lambda f: f())
    res, err = run_job(w, worker.read_all)
    assert worker.classify(err) == "permission"
    assert worker.classify(hid.DeviceNotFound("x")) == "notfound"
    assert worker.classify(hid.DeviceTimeout("x")) == "asleep"
    assert worker.classify(ValueError()) == "other"
    w.stop()


def test_worker_buttons_saved(dev):
    from attackshark_x11 import profiles
    w = worker.Worker(factory=lambda: dev, dispatch=lambda f: f())
    state = profiles.default_buttons()
    _, err = run_job(w, worker.apply_buttons, state)
    assert err is None and dev.writes[-1][0] == 8
    state["codes"] = [0 if c == 1 else c for c in state["codes"]]  # no Left Click: core refuses to save it
    _, err = run_job(w, worker.apply_buttons, state)
    assert isinstance(err, ValueError) and profiles.load_buttons()["codes"] != state["codes"]
    w.stop()


def test_monitor_forwards_battery():
    class Mouse:
        n = 0
        def read_input(self, timeout=0.5):
            return bytes([3, 0x55, 0x40, 2, 55]) if not Mouse.n else None
        def close(self): pass
    m, got, ev = Mouse(), [], threading.Event()
    w = worker.Worker(factory=lambda: m, dispatch=lambda f: f())
    run_job(w, lambda d: None)  # opens the device
    w.start_monitor(lambda e: (got.append(e), setattr(Mouse, "n", 1), ev.set()))
    assert ev.wait(5) and got[0]["percent"] == 55 and got[0]["status"] == "charging"
    w.stop()


def test_button_function_names_have_pt_br():
    from attackshark_x11 import buttons
    missing = sorted(n for n in buttons._NAMES.values() if n not in i18n.PT_BR)
    assert not missing, missing
