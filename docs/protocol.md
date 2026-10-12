# Attack Shark X11 HID protocol

Recovered by static analysis of the vendor Windows app plus experiments on a `1d57:fa60` dongle. See [reverse-engineering.md](reverse-engineering.md) for method. Every statement is marked:

- **[hw]** confirmed on a real mouse
- **[static]** decoded from the vendor binary, not confirmed on hardware

The reference implementation is `src/attackshark_x11/protocol.py` (pure encode/decode), `hid.py` (transport), `buttons.py`, `macros.py`.

## Transport

- USB IDs: vendor `1d57`; product `fa60` (2.4G dongle) [hw], `2126` (wired) [static]. A 4K dongle PID is unknown.
- The dongle exposes several HID interfaces. The configuration interface is the one whose report descriptor declares feature report `0xA0` (descriptor contains bytes `85 A0`). `find_hidraw()` selects it.
- All configuration traffic uses **feature reports** (`HIDIOCSFEATURE` / `HIDIOCGFEATURE`). Reports are sent with the report ID as the first byte.
- Input reports (events) arrive on the same hidraw node and are read with `read()`.

### Reading a report R

1. SET feature `A0 R len 00 01 00 00 00` (8 bytes; `len` is the report size).
2. Poll GET feature `A0` (8 bytes) until byte 1 equals `01`. If the mouse is asleep this never happens; the reference code retries (roughly 100 s).
3. GET feature `R` (`len` bytes).

### Writing

1. Once per session, SET the handshake `0C 0A 01 FE 01 FE 00 00 00 00`. The vendor app sends it before every apply. [hw] Light writes are ignored without it.
2. SET the full report.

The reference code waits 0.2 s after each write. The mouse acknowledges writes with an input event type `0x50`.

### Common layout

`[report id, total length, payload..., csum16 big-endian]` where the checksum is a plain 16-bit sum of the stated byte range.

## Report summary

| ID | Size | Content | Checksum | Status |
|---|---|---|---|---|
| 0x04 | 56 | DPI table, sensor options | sum bytes 3..49 at 50..51 | [hw] |
| 0x05 | 15 | Light, sleep, debounce | sum bytes 3..10 at 11..12 | light [hw], sleep/debounce [static] |
| 0x06 | 9 | Polling rate | none (byte 4 is complement of byte 3) | [hw] |
| 0x08 | 59 | Button map | sum bytes 3..56 at 57..58 | [static] |
| 0x09 | 131 | Macro | sum bytes 3..128 at 129..130 | [static] |
| 0x0C | 10 | Handshake | none | [hw] |
| 0xA0 | 8 | Read handshake/flag | none | [hw] |

Reports 4, 5 and 6 are readable. Reports 8 and 9 are write-only (the mouse cannot return them), so software must remember what it wrote.

## Report 4: DPI (56 bytes)

| Byte | Meaning |
|---|---|
| 0 | `04` |
| 1 | `38` (56) |
| 3 | high nibble = lift-off option (0 = 1 mm, 1 = 2 mm); low nibble = ripple control (0/1) |
| 4 | high nibble = angle snap (0/1); low nibble = motion sync (0/1) |
| 5 | stage-enable mask, bit i = stage i+1 |
| 6 | bit i set = stage i uses 100-DPI units, else 50-DPI units |
| 8..15 | stage DPI value, low byte |
| 16..23 | stage DPI value, high byte |
| 24 | active stage, 1-based |
| 25..48 | RGB for stages 1..8 (3 bytes each) |
| 49 | `02` |
| 50..51 | csum16 BE of bytes 3..49 |

DPI = (value16 + 1) x unit, with `value16 = lo | hi << 8` and unit 50 or 100 per byte 6. The tool encodes with unit 50 up to 26000 DPI and unit 100 above. Bytes not listed are preserved from the last read when writing. DPI values were decoded with the vendor formula and not cross-checked against measured pointer speed. [hw]

## Report 5: light, sleep, debounce (15 bytes)

| Byte | Meaning |
|---|---|
| 0, 1 | `05`, `0F` |
| 3 | high nibble = light mode; low nibble preserved |
| 4 | low nibble = `9 - breathing speed` (speed 4..8); high nibble = deep-sleep seconds, high part |
| 5 | low nibble = brightness 1..8; high nibble = deep-sleep seconds, low part |
| 6..8 | RGB |
| 9 | sleep minutes 1..60 |
| 10 | key debounce, ms = byte x 2 (raw 2..25) |
| 11..12 | csum16 BE of bytes 3..10 |

Deep sleep seconds = `(b4 & 0xF0) | (b5 >> 4)`.

Light modes: 0 LED Off, 1 Static, 2 Breathing, 3 Neon, 4 Color Breathing, 5 Static DPI, 6 Breathing DPI. Static and Breathing [hw]; others see the status table in the README. Sleep and debounce are [static].

## Report 6: polling rate (9 bytes)

`06 09 01 X ~X ...` with X one-hot: `01` = 1000 Hz, `02` = 500 Hz, `04` = 250 Hz, `08` = 125 Hz; byte 4 is the bitwise complement of X. [hw] The reference reader also treats the low nibble as the interval in ms. The high nibble of X is unknown; the tool preserves it. The mouse rewrites report 6 itself after a DPI-table change, so a rate write right after a DPI write can be lost (the `defaults` command waits and retries).

## Report 8: buttons (59 bytes) [static]

    08 3B 01  [type a b] x 18  csum16-BE

Bytes 3..56 hold 18 slots of 3 bytes; bytes 57..58 are the checksum of bytes 3..56. Slot i (1-based button number) occupies bytes `3+3(i-1) .. 5+3(i-1)`.

Default function code per slot (model 4 table, vendor app): `01 02 03 06 05 04 34 00 00 00 00 00 00 00 00 00 0B 0C`. The tool deviates in two slots: slots 7 and 8 (0-based 6 and 7) are forced to type 6 and type 5 (forward and back side buttons) because the vendor default leaves one of them off. This is a choice, not verified.

The vendor app speaks in "function codes"; each code maps to a `(type, a, b)` triple in the report. Types 17 (`0x11`) with `a` = modifier mask and `b` = HID usage encode fixed shortcuts. Code `0x10` (keyboard key) sends type 17 with a user-supplied modifier mask and usage. Code `0x11` (macro) sends type 18 with `b` = button number; the macro itself is sent in report 9 beforehand.

Modifier mask: 1 Ctrl, 2 Shift, 4 Alt, 8 GUI.

### Function code table

Names are only given where the meaning is certain (basic buttons and the shortcuts, which carry visible HID usages). Other codes are listed as in the vendor app's table; their function is unknown and was not tested.

| Code | Name | Type | a | b |
|---|---|---|---|---|
| 0x00 | Disabled | 1 | 0 | 0 |
| 0x01 | Left Click | 2 | 0 | 0 |
| 0x02 | Right Click | 3 | 0 | 0 |
| 0x03 | Middle Click | 4 | 0 | 0 |
| 0x04 | Forward | 6 | 0 | 0 |
| 0x05 | Back | 5 | 0 | 0 |
| 0x06 | unnamed | 13 | 0 | 0 |
| 0x07 | unnamed | 14 | 0 | 0 |
| 0x08 | unnamed | 15 | 0 | 0 |
| 0x09 | unnamed | 7 | 0 | 0 |
| 0x0a | unnamed | 8 | 0 | 0 |
| 0x0b | Wheel Up | 9 | 0 | 0 |
| 0x0c | Wheel Down | 10 | 0 | 0 |
| 0x0d | unnamed | 11 | 0 | 0 |
| 0x0e | unnamed | 12 | 0 | 0 |
| 0x10 | Keyboard Key (custom) | 17 | mods | usage |
| 0x11 | Macro | 18 | 0 | button number |
| 0x13 | unnamed | 19 | 0 | 0 |
| 0x15 | unnamed | 43 | 0 | 0 |
| 0x16 | unnamed | 16 | 0 | 3 |
| 0x17 | unnamed | 41 | 0 | 3 |
| 0x20 | Ctrl+X | 17 | 1 | 27 |
| 0x21 | Ctrl+C | 17 | 1 | 6 |
| 0x22 | Ctrl+V | 17 | 1 | 25 |
| 0x23 | Ctrl+O | 17 | 1 | 18 |
| 0x24 | Ctrl+S | 17 | 1 | 22 |
| 0x25 | Ctrl+F | 17 | 1 | 9 |
| 0x26 | Ctrl+Y | 17 | 1 | 28 |
| 0x27 | Ctrl+Z | 17 | 1 | 29 |
| 0x28 | Ctrl+A | 17 | 1 | 4 |
| 0x29 | Ctrl+P | 17 | 1 | 19 |
| 0x2a | Alt+F4 | 17 | 4 | 61 |
| 0x2b | Alt+Tab | 17 | 4 | 43 |
| 0x2c | Gui+D | 17 | 8 | 7 |
| 0x2d | Gui+R | 17 | 8 | 21 |
| 0x2e | Gui+L | 17 | 8 | 15 |
| 0x2f | Ctrl+N | 17 | 1 | 17 |
| 0x30 | Ctrl+= | 17 | 1 | 46 |
| 0x31 | Ctrl+- | 17 | 1 | 45 |
| 0x34 | unnamed (default of slot 7) | 60 | 0 | 0 |
| 0x36 | unnamed | 52 | 0 | 0 |
| 0x37 | unnamed | 53 | 0 | 0 |
| 0x38 | unnamed | 54 | 0 | 0 |
| 0x40 | unnamed | 21 | 0 | 0 |
| 0x41 | unnamed | 24 | 0 | 0 |
| 0x42 | unnamed | 25 | 0 | 0 |
| 0x43 | unnamed | 22 | 0 | 0 |
| 0x44 | unnamed | 23 | 0 | 0 |
| 0x45 | unnamed | 27 | 0 | 0 |
| 0x46 | unnamed | 28 | 0 | 0 |
| 0x47 | unnamed | 26 | 0 | 0 |
| 0x50 | unnamed | 37 | 0 | 0 |
| 0x51 | Ctrl+Shift+O | 17 | 3 | 18 |
| 0x52 | unnamed | 32 | 0 | 0 |
| 0x53 | unnamed | 33 | 0 | 0 |
| 0x54 | unnamed | 34 | 0 | 0 |
| 0x55 | unnamed | 36 | 0 | 0 |
| 0x56 | unnamed | 38 | 0 | 0 |
| 0x57 | unnamed | 30 | 0 | 0 |
| 0x58 | unnamed | 29 | 0 | 0 |
| 0x59 | unnamed | 35 | 0 | 0 |
| 0x73 | unnamed | 20 | 0 | 0 |

HID usages used in the shortcuts are the standard keyboard usages (A = 4, ... Z = 29, F4 = 61, Tab = 43, `=` = 46, `-` = 45). The `functions` CLI command prints the same table from the code.

## Report 9: macro (131 bytes) [static]

Logical layout:

    09 83 slot mode rep rep rep loop 00x20 count events... padding csum16-BE

| Byte | Meaning |
|---|---|
| 0, 1 | `09`, `83` |
| 2 | slot = button number 1..18 |
| 3 | mode 0, 1 or 2 (meaning of each mode unknown) |
| 4..6 | three bytes the vendor app fills with the same value; meaning unknown (the tool writes 0) |
| 7 | loop count (at least 1) |
| 8..27 | zero |
| 28 | event count (1..46) |
| 29.. | events, 2 bytes each |
| 129..130 | csum16 BE of bytes 3..128 |

Event: `[delay_byte, usage]`. `delay_byte = (round(delay_ms / 10) | 1)` for a press, `| 0x81` for a release. The delay therefore has 10 ms resolution and 7 bits, so at most about 1270 ms. For longer delays the vendor app splits the delay into two events: `[rem/10 | flag, key]` followed by `[delay/200, 0x03]`. The reference tool does not split; it clamps to 1270 ms. The exact semantics of the `0x03` pseudo-event are not verified.

Usage is a standard HID keyboard usage, or a pseudo usage for mouse buttons: `F1` = left, `F2` = right, `F3` = middle.

### Wire format

The 131-byte logical report is sent as three feature reports. Let `body = logical[3:131]` (128 bytes):

| Report | Bytes |
|---|---|
| 1 | `09 40 slot 00` + `body[0:60]` |
| 2 | `09 40 slot 01` + `body[60:120]` |
| 3 | `09 0C slot 02` + `body[120:128]` |

After the macro is written, the button is assigned function `0x11` in report 8 with `b` = button number. Macros must be sent before the button map that references them (`profiles.write_buttons` does this).

## Report 0C: handshake

`0C 0A 01 FE 01 FE 00 00 00 00`, sent before writes. [hw]

## Input events

Input report on the config interface: `03 55 T lo hi`. [hw] means observed.

| T | Event | Payload | Status |
|---|---|---|---|
| 0x10 | DPI stage changed | stage number; 0- or 1-based unverified | [hw] type seen |
| 0x20 | Polling rate changed | one-hot rate value | [hw] type seen |
| 0x40 | Battery | byte 3 = status (1 discharging, 2 charging, 3 low), byte 4 = percent | [hw] |
| 0x50 | Write acknowledged | unknown | [hw] type seen |
| 0x70 | Light mode changed | mode number | [hw] type seen |

Payload layouts other than battery are best guesses in `protocol.parse_event`. `attackshark-x11 monitor` prints events, including the raw hex, which is useful for refining this table.

## Factory presets (unverified)

The vendor binary has two reset routines for different mouse classes:

| Preset | DPI stages | Active | Rate |
|---|---|---|---|
| MS_4 (X11 class, `0x4a4670`) | 800, 1600, 2400, 3200, 5000, 22000 | 1 | 1000 Hz |
| MS_13 (`0x447d00`) | 1200, 2400, 3200, 5600, 8000, 40000 | 1 | 250 Hz |

It is not known which one the real X11 firmware uses. MS_4 is the default of the `defaults` command. MS_13's 40000 DPI exceeds the 22000 DPI limit enforced for manual input.

## Known unknowns

- Meaning of report 6 high nibble, report 4 byte 49 (`02`), report 5 byte 3 low nibble, report 9 bytes 4..6 and mode values.
- Whether the X11 is MS_4 or MS_13 class for presets.
- Payload encoding of input events other than battery.
- Behavior of delays above 1270 ms and of the `0x03` pseudo event.
- Semantics of most unnamed button function codes.
- Whether report 8 and 9 writes are accepted exactly as decoded.
- PID of the 4K dongle and any Bluetooth/wired differences.
- Sleep and debounce effect on real behavior.
