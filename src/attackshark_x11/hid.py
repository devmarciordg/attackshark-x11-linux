"""hidraw transport. Feature-report handshake as the vendor app does it; no protocol knowledge beyond report sizes."""
import fcntl
import glob
import os
import select
import sys
import time

from .protocol import SIZES, parse_event

VID = 0x1D57
# 1d57:fa60 = 2.4G dongle, 1d57:2126 = wired. Verified on hardware: fa60 only.
# TODO: 4K dongle PID. Not in the installer strings available here (hiddriver strings not extracted);
#       get it from `lsusb` with the 4K dongle plugged in and append it here and in the udev rule.
PIDS = (0xFA60, 0x2126)

UDEV_HINT = ("no permission on {path}. Install the udev rule: "
             "sudo cp packaging/udev/70-attackshark.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger "
             "(then replug the dongle)")


class DeviceError(Exception):
    """Base for expected hardware problems (CLI prints them without traceback)."""


class DeviceNotFound(DeviceError):
    pass


class DevicePermissionError(DeviceError):
    pass


class DeviceTimeout(DeviceError, TimeoutError):
    pass


def _ioc(n, nr):  # _IOC(_IOC_READ|_IOC_WRITE, 'H', nr, n)
    return (3 << 30) | (n << 16) | (ord("H") << 8) | nr


def find_hidraw():
    """Return /dev/hidrawN of the vendor config interface (declares feature report 0xA0)."""
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(f"{path}/device/uevent") as f:
                uevent = f.read()
            with open(f"{path}/device/report_descriptor", "rb") as f:
                desc = f.read()
        except OSError:
            continue
        ids = [l.split("=")[1] for l in uevent.splitlines() if l.startswith("HID_ID=")]
        if not ids:
            continue
        _, vid, pid = (int(x, 16) for x in ids[0].split(":"))
        if vid == VID and pid in PIDS and b"\x85\xa0" in desc:
            return "/dev/" + os.path.basename(path)
    raise DeviceNotFound("X11 config interface not found (dongle plugged in? mouse awake?)")


class Device:
    def __init__(self, path=None):
        path = path or find_hidraw()
        try:
            self.fd = os.open(path, os.O_RDWR)
        except PermissionError:
            raise DevicePermissionError(UDEV_HINT.format(path=path)) from None
        except OSError as e:
            raise DeviceNotFound(f"cannot open {path}: {e.strerror}") from None
        self.path = path

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

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
        raise DeviceTimeout("mouse did not answer (asleep? move it and retry)")

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

    def read_input(self, timeout=0.5):
        """One raw input report or None on timeout."""
        if select.select([self.fd], [], [], timeout)[0]:
            return os.read(self.fd, 64)
        return None


def read_events(dev, timeout=None):
    """Yield parsed input events (dicts from protocol.parse_event) until `timeout` seconds pass (None = forever)."""
    end = None if timeout is None else time.time() + timeout
    while end is None or time.time() < end:
        r = dev.read_input(0.5)
        ev = parse_event(r) if r else None
        if ev:
            yield ev


def battery(dev, timeout=5.0):
    """Wait for a battery event (sent while the mouse is awake). -> (percent, status) or None."""
    for ev in read_events(dev, timeout):
        if ev["event"] == "battery":
            return ev["percent"], ev["status"]
    return None
