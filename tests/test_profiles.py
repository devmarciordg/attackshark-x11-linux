import json

import pytest

from attackshark_x11 import buttons, factory, profiles
from attackshark_x11.protocol import parse_dpi, parse_rate


def test_snapshot_apply_roundtrip(dev):
    p = profiles.snapshot(dev)
    assert p["rate_hz"] == 1000 and p["buttons"]["codes"] == buttons.BUTTON_DEFAULTS
    json.dumps(p)  # must be serializable
    dev2 = type(dev)()
    p["dpi"]["stages"][0]["dpi"] = 1234 // 50 * 50
    p["rate_hz"] = 500
    profiles.apply_profile(dev2, p)
    assert parse_dpi(dev2.reports[4])["stages"][0]["dpi"] == 1200
    assert parse_rate(dev2.reports[6]) == 500
    assert any(len(w) == 59 for w in dev2.writes)


def test_store_list_export_import_delete(dev, tmp_path):
    p = profiles.snapshot(dev)
    profiles.save("work", p)
    assert profiles.list_profiles() == ["work"]
    out = tmp_path / "w.json"
    profiles.export_profile("work", out)
    assert profiles.import_profile(out, "copy") == "copy"
    assert profiles.load("copy") == json.loads(json.dumps(p))
    profiles.delete("work")
    assert profiles.list_profiles() == ["copy"]
    with pytest.raises(ValueError):
        profiles.load("work")
    with pytest.raises(ValueError):
        profiles.save("../evil", p)


def test_invalid_profile_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"version": 1, "dpi": {"stages": []}}')
    with pytest.raises(ValueError):
        profiles.import_profile(bad)


def test_button_state_and_macro_written(dev):
    st = profiles.default_buttons()
    st["codes"][3] = buttons.MACRO_FUNC
    st["macros"]["4"] = {"mode": 0, "loop": 1, "events": ["+a:30", "-a:30"]}
    profiles.write_buttons(dev, st)
    assert [len(w) for w in dev.writes if w[0] == 9] == [64, 64, 12]
    profiles.save_buttons(st)
    assert profiles.load_buttons() == st


def test_reset_and_preset(dev):
    factory.apply_preset(dev, "ms13")
    assert parse_rate(dev.reports[6]) == 250
    profiles.reset(dev, "ms4")
    d = parse_dpi(dev.reports[4])
    assert [s["dpi"] for s in d["stages"][:6]] == [800, 1600, 2400, 3200, 5000, 22000] and d["active"] == 1
    assert parse_rate(dev.reports[6]) == 1000
    assert profiles.load_buttons() == profiles.default_buttons()


def test_cli_errors_have_exit_codes(capsys):
    from attackshark_x11 import cli
    assert cli.main(["profile", "list"]) == 0
    assert cli.main(["profile", "delete", "nope"]) == 1
    assert "no profile named" in capsys.readouterr().err
    assert cli.main(["button", "4", "0xff"]) == 1
