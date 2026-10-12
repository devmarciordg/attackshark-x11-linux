# Attack Shark X11 on Linux

Clone of `ATTACK SHARK X11 SOFT.exe` (an Inno Setup installer; the real app is `AttackShark.exe`, C++/DuiLib, model 4 = "X11 Mouse").

    python3 attackshark_gui.py            # GTK4 app
    python3 attackshark_x11.py show       # CLI: show | dpi N DPI | active N | color N RRGGBB | light --mode N --rgb RRGGBB [--brightness N --breath-speed N] | rate HZ | sleep --min N --deep N --debounce MS | raw

The mouse sleeps fast: move it while a command runs (the tool waits up to ~100 s).
Optional: `sudo cp 99-attackshark.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger` for non-root hidraw access.

## Protocol (from AttackShark.exe, checked on a 1d57:fa60 dongle)
Vendor HID interface (declares feature report 0xA0). All traffic = feature reports.
- Read report R: SET `A0 R len 00 01 00 00 00`, poll GET `A0` until byte1 == 1, GET `R`.
- Write: SET the full report. `[id, total_len, payload..., csum16 big-endian]`.
- Report 4 (56 B, DPI): b3 = lift-off<<4 | ripple, b4 = angle_snap<<4 | motion_sync, b5 = stage-enable mask,
  b6 = mask of stages in 100-DPI units (else 50), b8..15 / b16..23 = value lo / hi (DPI = (v+1)*unit),
  b24 = active stage (1-based), b25.. = RGB x 8, b49 = 02, b50..51 = sum(b3..b49).
- Report 5 (15 B, light/misc): b3 hi nibble = light mode (0 Off, 1 Static, 2 Breathing, 3 Neon, 4 Color Breathing, 5 Static DPI, 6 Breathing DPI),
  b4 lo = 9 - breathing speed (4..8), b5 lo = brightness (1..8), b4 hi + b5 hi = deep sleep seconds, b6..8 = RGB,
  b9 = sleep minutes (1..60), b10 = key debounce (ms = b10*2), b11..12 = sum(b3..b10). Writes need `0C 0A 01 FE 01 FE 00 00 00 00` first (sent automatically).
- Report 6 (9 B): `06 09 01 X ~X`; X low nibble = polling interval in ms (8/4/2/1 = 125/250/500/1000 Hz, measured), high nibble unknown.
- Battery: input report 3 on the config interface, `03 55 40 status percent` (status 1 discharging, 2 charging, 3 low).

## Not done / unverified
- Light modes 0, 3-6, brightness, breathing speed, sleep timers and debounce: decoded from the app's sliders, not all confirmed on the LED/mouse (mode 1 Static, 2 Breathing and polling rate were).
- Buttons (report 8, 59 B: 18 x [type,a,b] + csum16) and macros (report 9, 131 B sent as 3 feature reports: `09 40 slot 0|1` + 60 B, `09 0C slot 02` + 8 B) are decoded from AttackShark.exe (FUN_004a26c0 / FUN_004a2430) and exposed as CLI `button` / `macro`, but NOT tested on the mouse. Report 8 cannot be read back, so the map is kept in ~/.config/attackshark_buttons.json.
- The factory-defaults routine used for `defaults` (0x447d00) belongs to the MS_13 class; the MS_4 (X11) class reset (0x4a4670) gives 800/1600/2400/3200/5000/22000 DPI and 1000 Hz. Unresolved which class the dongle really uses.
- Report 6 byte 3 is one-hot (1/2/4/8 = 1000/500/250/125 Hz), byte 4 is its complement. Input events: 0x10 DPI stage, 0x20 polling, 0x40 battery, 0x50 write ack, 0x70 light mode.
- DPI values decode with the app's own formula; not cross-checked against real pointer speed.
