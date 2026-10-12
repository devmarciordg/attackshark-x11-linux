import pytest

from attackshark_x11 import factory
from attackshark_x11.protocol import (ProtocolError, build_dpi, build_light, build_rate, csum_dpi, csum_light,
                                      dpi_decode, dpi_encode, parse_dpi, parse_event, parse_light, parse_rate)


def test_dpi_encode_decode_roundtrip():
    for dpi in (50, 400, 800, 26000, 26100, 40000):
        v, high = dpi_encode(dpi)
        assert dpi_decode(v & 0xFF, v >> 8, high) == dpi


def test_dpi_report_roundtrip_and_checksum(dev):
    cfg = factory.PRESETS["ms13"]["dpi"]
    raw = build_dpi(dev.read(4), cfg)
    assert len(raw) == 56 and (raw[50], raw[51]) == csum_dpi(raw)
    got = parse_dpi(raw)
    assert [s["dpi"] for s in got["stages"][:6]] == [1200, 2400, 3200, 5600, 8000, 40000]
    assert got["active"] == 1 and got["stages"][5]["enabled"] and not got["stages"][6]["enabled"]
    assert build_dpi(raw, got) == raw


def test_bad_checksum_rejected(dev):
    raw = bytearray(dev.read(4))
    raw[50] ^= 1
    with pytest.raises(ProtocolError):
        parse_dpi(bytes(raw))
    with pytest.raises(ProtocolError):
        parse_light(b"\x00" * 15)


def test_light_roundtrip(dev):
    raw = build_light(dev.read(5), mode=2, rgb=(1, 2, 3), brightness=5, breath_speed=6,
                      deep_sleep_s=30, sleep_min=10, debounce_ms=8)
    assert (raw[11], raw[12]) == csum_light(raw)
    l = parse_light(raw)
    assert (l["mode"], l["rgb"], l["brightness"], l["breath_speed"], l["deep_sleep_s"], l["sleep_min"],
            l["debounce_ms"]) == (2, (1, 2, 3), 5, 6, 30, 10, 8)


def test_rate_roundtrip(dev):
    for hz in (125, 250, 500, 1000):
        r = build_rate(dev.read(6), hz)
        assert parse_rate(r) == hz and r[4] == ~r[3] & 0xFF


def test_events():
    assert parse_event(bytes([3, 0x55, 0x40, 2, 87])) == {"event": "battery", "raw": "03554002" + "57",
                                                          "status": "charging", "percent": 87}
    assert parse_event(bytes([3, 0x55, 0x20, 4, 0]))["hz"] == 250
    assert parse_event(bytes([3, 0x55, 0x70, 2, 0]))["mode_name"] == "Breathing"
    assert parse_event(bytes([3, 0x55, 0x10, 3, 0]))["event"] == "dpi_stage"
    assert parse_event(bytes([3, 0x55, 0x50, 0, 0]))["event"] == "write_ack"
    assert parse_event(bytes([1, 0, 0, 0, 0])) is None
