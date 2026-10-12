import pytest

from attackshark_x11 import factory
from attackshark_x11.protocol import SIZES, build_dpi, csum_light


class FakeDevice:
    """In-memory stand-in for hid.Device: read(rid) returns stored reports, write() records / stores them."""

    def __init__(self):
        raw4 = bytearray(56)
        raw4[0], raw4[1], raw4[24], raw4[49] = 4, 0x38, 1, 2
        raw5 = bytearray(15)
        raw5[0], raw5[1], raw5[9], raw5[10] = 5, 0x0F, 5, 4
        raw5[11], raw5[12] = csum_light(raw5)
        self.reports = {4: build_dpi(raw4, factory.PRESETS["ms4"]["dpi"]), 5: bytes(raw5),
                        6: bytes([6, 9, 1, 1, 0xFE, 0, 0, 0, 0])}
        self.writes = []

    def read(self, rid, retries=0):
        return self.reports[rid]

    def write(self, buf, retries=0):
        buf = bytes(buf)
        self.writes.append(buf)
        if buf[0] in self.reports and len(buf) == SIZES[buf[0]]:
            self.reports[buf[0]] = buf


@pytest.fixture
def dev():
    return FakeDevice()


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("ATTACKSHARK_X11_CONFIG", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path))  # keep the legacy-file lookup off the real home
