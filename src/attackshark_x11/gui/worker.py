"""Device I/O off the GTK main thread. One executor thread runs device jobs in order; one thread listens for events."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from .. import buttons, hid, profiles
from ..hid import DeviceError, DeviceNotFound, DevicePermissionError, DeviceTimeout
from ..protocol import build_dpi, build_light, build_rate, parse_dpi, parse_light, parse_rate

READ_RETRIES = 8  # ~4 s: hid.Device.read defaults to 200 tries (100 s), far too long for a UI


def classify(err):
    """-> 'notfound' | 'permission' | 'asleep' | 'other'"""
    for cls, kind in ((DeviceNotFound, "notfound"), (DevicePermissionError, "permission"), (DeviceTimeout, "asleep")):
        if isinstance(err, cls):
            return kind
    return "other"


class ShortDevice:
    """Wraps a device so read() gives up after READ_RETRIES instead of 200 (core code calls dev.read(rid))."""

    def __init__(self, dev):
        self._dev = dev

    def read(self, rid, retries=READ_RETRIES):
        return self._dev.read(rid, retries=retries)

    def __getattr__(self, name):
        return getattr(self._dev, name)


def default_factory():
    if os.environ.get("ATTACKSHARK_X11_FAKE"):
        from .fake import FakeDevice
        return FakeDevice()
    return hid.Device()


def _idle(fn, *a):
    from gi.repository import GLib
    GLib.idle_add(fn, *a)


# -- jobs: fn(dev) -> result, run on the worker thread

def read_all(dev):
    return {"dpi": parse_dpi(dev.read(4)), "light": parse_light(dev.read(5)), "rate_hz": parse_rate(dev.read(6))}


def apply_dpi(dev, cfg):
    dev.write(build_dpi(dev.read(4), cfg))
    return read_all(dev)


def apply_light(dev, **fields):
    dev.write(build_light(dev.read(5), **fields))
    return read_all(dev)


def apply_rate(dev, hz):
    dev.write(build_rate(dev.read(6), hz))
    return read_all(dev)


def apply_buttons(dev, state):
    buttons.validate_codes(state["codes"])  # before writing: a map without Left Click must never reach the mouse
    profiles.write_buttons(dev, state)
    profiles.save_buttons(state)


class Worker:
    def __init__(self, factory=None, dispatch=None):
        self.factory = factory or default_factory
        self.dispatch = dispatch or _idle  # tests pass a direct call
        self.dev = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="device")
        self.stop_event = threading.Event()
        self.monitor_thread = None

    def _device(self):
        if self.dev is None:
            self.dev = self.factory()
        return self.dev

    def _drop(self):
        d, self.dev = self.dev, None
        try:
            d and d.close()
        except Exception:  # noqa: BLE001 - already broken
            pass

    def submit(self, fn, on_done, *args, **kw):
        """Run fn(ShortDevice, *args) on the device thread; on_done(result, error) is called through `dispatch`."""
        def job():
            try:
                res, err = fn(ShortDevice(self._device()), *args, **kw), None
            except Exception as e:  # noqa: BLE001 - reported to the UI
                res, err = None, e
                if isinstance(e, (DeviceNotFound, DevicePermissionError, OSError)):
                    self._drop()
            self.dispatch(lambda: on_done(res, err) and False)
        self.pool.submit(job)

    def start_monitor(self, on_event):
        """Forward parsed input events (battery...) to on_event(ev) via dispatch. Quiet while the device is unavailable."""
        def loop():
            while not self.stop_event.is_set():
                try:
                    dev = self.dev
                    if dev is None:
                        self.stop_event.wait(1)
                        continue
                    for ev in hid.read_events(dev, 1.0):
                        self.dispatch(lambda ev=ev: on_event(ev) and False)
                except Exception:  # noqa: BLE001 - device unplugged mid-read; the next job reopens it
                    self.stop_event.wait(1)
        self.monitor_thread = threading.Thread(target=loop, daemon=True, name="monitor")
        self.monitor_thread.start()

    def stop(self):
        self.stop_event.set()
        self.pool.shutdown(wait=False)
