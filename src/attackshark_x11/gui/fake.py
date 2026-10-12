"""In-memory device for demo mode (ATTACKSHARK_X11_FAKE=1): no hardware, handy for screenshots."""
import time

from .. import factory
from ..protocol import SIZES, build_dpi, csum_light


class FakeDevice:
    def __init__(self):
        raw4 = bytearray(56)
        raw4[0], raw4[1], raw4[24], raw4[49] = 4, 0x38, 1, 2
        raw5 = bytearray(15)
        raw5[0], raw5[1], raw5[9], raw5[10] = 5, 0x0F, 5, 4
        raw5[11], raw5[12] = csum_light(raw5)
        self.reports = {4: build_dpi(raw4, factory.PRESETS["ms4"]["dpi"]), 5: bytes(raw5),
                        6: bytes([6, 9, 1, 1, 0xFE, 0, 0, 0, 0])}
        self.pct = 80

    def read(self, rid, retries=0):
        return self.reports[rid]

    def write(self, buf, retries=0):
        buf = bytes(buf)
        if buf[0] in self.reports and len(buf) == SIZES[buf[0]]:
            self.reports[buf[0]] = buf

    def read_input(self, timeout=0.5):
        time.sleep(min(timeout, 1.0))
        return bytes([3, 0x55, 0x40, 1, self.pct])

    def close(self):
        pass
