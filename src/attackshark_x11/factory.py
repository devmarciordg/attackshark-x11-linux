"""Factory presets. Which one the X11 really uses is UNVERIFIED: MS_4 is the model-4 reset (0x4a4670) of
AttackShark.exe, MS_13 the routine at 0x447d00 (a different mouse class, used by the first prototype)."""
import time

from .protocol import build_dpi, build_rate, parse_rate

_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255), (255, 64, 0), (255, 255, 255)]


def _preset(dpis, active, hz):
    # unused stages keep 50 DPI; stage 6 of MS_13 is 40000 DPI (> the 22000 sensor spec), kept as the vendor app has it
    dpis = list(dpis) + [50] * (8 - len(dpis))
    n = sum(d != 50 for d in dpis)
    return {"dpi": {"stages": [{"enabled": i < n, "dpi": d, "rgb": c} for i, (d, c) in enumerate(zip(dpis, _COLORS))],
                    "active": active, "lift_off_mm": 1, "ripple": True, "angle_snap": False, "motion_sync": True},
            "rate_hz": hz}


PRESETS = {
    "ms4": _preset([800, 1600, 2400, 3200, 5000, 22000], 1, 1000),
    "ms13": _preset([1200, 2400, 3200, 5600, 8000, 40000], 1, 250),
}
DEFAULT_PRESET = "ms4"


def apply_preset(dev, name=DEFAULT_PRESET):
    """Write the preset's DPI table + polling rate (light/sleep untouched)."""
    p = PRESETS[name]
    dev.write(build_dpi(dev.read(4), p["dpi"]))
    time.sleep(1)  # the mouse rewrites report 6 itself after a table change; a write right away is lost
    for _ in range(3):
        r6 = dev.read(6)
        if parse_rate(r6) == p["rate_hz"]:
            break
        dev.write(build_rate(r6, p["rate_hz"]))
