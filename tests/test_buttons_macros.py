import pytest

from attackshark_x11 import buttons, macros
from attackshark_x11.protocol import csum_buttons


def test_button_table_invariants():
    assert len(buttons.BUTTON_DEFAULTS) == buttons.SLOTS == 18
    assert all(c in buttons.BUTTON_FUNCS for c in buttons.BUTTON_DEFAULTS)
    assert all(len(v) == 3 and all(0 <= x < 256 for x in v) for v in buttons.BUTTON_FUNCS.values())
    assert set(buttons.function_names()) == set(buttons.BUTTON_FUNCS)
    assert len(set(buttons.function_names().values())) == len(buttons.BUTTON_FUNCS)
    buttons.validate_codes(buttons.BUTTON_DEFAULTS)


def test_build_buttons_default():
    r = buttons.build_buttons()
    assert len(r) == 59 and r[:3] == bytes([8, 0x3B, 1])
    assert (r[57], r[58]) == csum_buttons(r)
    assert r[3:6] == bytes([2, 0, 0])            # left click
    assert r[3 + 3 * 7:6 + 3 * 7] == bytes([5, 0, 0])  # slot 8 forced to Back
    assert r[3 + 3 * 6:6 + 3 * 6] == bytes([6, 0, 0])  # slot 7 forced to Forward


def test_key_and_macro_slots():
    codes = list(buttons.BUTTON_DEFAULTS)
    codes[3], codes[4] = buttons.KEY_FUNC, buttons.MACRO_FUNC
    r = buttons.build_buttons(codes, {3: buttons.parse_key_combo("ctrl+c")})
    assert r[12:15] == bytes([17, 1, 6])
    assert r[15:18] == bytes([18, 0, 5])  # macro: b = slot number


def test_key_helpers():
    assert buttons.key_usage("a") == 4 and buttons.key_usage("0") == 39 and buttons.key_usage("f1") == 58
    assert buttons.parse_key_combo("ctrl+shift+a") == (3, 4)
    assert buttons.format_key_combo(1, 6) == "Ctrl+C"
    assert buttons.parse_function("0x34") == (0x34, None)
    assert buttons.parse_function("key:alt+tab") == (0x10, (4, 43))
    with pytest.raises(ValueError):
        buttons.parse_function("0xff")
    with pytest.raises(ValueError):
        buttons.validate_codes([0] * 18)  # no left click


def test_build_macro_layout():
    reports = macros.build_macro(4, macros.parse_events(["+a:30", "-a:30"]), loop=3)
    assert [len(r) for r in reports] == [64, 64, 12]
    assert [r[:4] for r in reports] == [bytes([9, 0x40, 4, 0]), bytes([9, 0x40, 4, 1]), bytes([9, 0x0C, 4, 2])]
    body = b"".join(r[4:] for r in reports)
    assert len(body) == 128
    full = bytes([9, 0x83, 4]) + body
    assert len(full) == 131 and full[7] == 3 and full[28] == 2
    assert full[29:33] == bytes([3 | 1, 4, 3 | 0x81, 4])
    assert (full[0x81] << 8 | full[0x82]) == sum(full[3:0x81]) & 0xFFFF


def test_macro_limits_and_file(tmp_path):
    with pytest.raises(ValueError):
        macros.build_macro(1, [])
    with pytest.raises(ValueError):
        macros.parse_event("a:30")
    p = tmp_path / "m.json"
    m = {"mode": 1, "loop": 2, "events": ["+lmb:10", "-lmb:10"]}
    macros.save_macro_file(p, m)
    assert macros.load_macro_file(p) == m
