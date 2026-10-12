# Attack Shark X11 for Linux

[English](README.md) | [Português (Brasil)](README.pt-BR.md)

An open-source, independent Linux configuration tool for the **Attack Shark X11** wireless mouse (2.4G dongle `1d57:fa60`, wired `1d57:2126`). It replaces the Windows-only vendor app for the settings that app exposes: DPI stages, lighting, polling rate, sleep and debounce, button remapping and macros. It ships a command line tool and a GTK4 GUI. The core has no dependencies beyond the Python standard library.

> **Not affiliated with Attack Shark.** This is an independent interoperability project. It contains no vendor code or assets. See [docs/reverse-engineering.md](docs/reverse-engineering.md#legal-note).

## Status

Only part of the protocol has been confirmed on a real mouse. Please read this table before trusting a feature.

| Feature | Status |
|---|---|
| DPI stages (value, enable, color, active stage) | Verified on hardware |
| Lighting: Static and Breathing, color | Verified on hardware |
| Lighting: other modes (Off, Neon, Color Breathing, Static DPI, Breathing DPI), brightness, breathing speed | Light writes work on hardware; per-mode visual results beyond Static and Breathing were not individually recorded, reports welcome |
| Polling rate (125/250/500/1000 Hz) | Verified on hardware |
| Battery readout | Verified on hardware |
| Button remapping | **Unverified.** Decoded from the vendor binary, never tested on a mouse |
| Macros | **Unverified.** Same as above |
| Factory presets (`defaults`, MS_4 vs MS_13) | **Unverified.** It is not known which preset the X11 uses |
| Sleep timers and key debounce | **Unverified.** Decoded from the vendor app's sliders |
| DPI value vs real pointer speed | Not cross-checked |
| Bluetooth connection, 4K dongle | Not supported or not tested |

"Unverified" features send the bytes the vendor app is believed to send. If you own the mouse, please test them and file a [hardware report](docs/hardware-testing.md). Reports are the fastest way to move rows in this table.

## Install

See [packaging/README.md](packaging/README.md) for distro packages, pipx and the Flatpak notes, and run `./install.sh` from a checkout for a guided install that also sets up the udev rule. The short version from a checkout:

    pip install .                 # CLI only, stdlib only
    attackshark-x11 --version

The GUI needs PyGObject and GTK 4 from your distribution (for example `python3-gobject` and `gtk4` on Fedora, `python3-gi` and `gir1.2-gtk-4.0` on Debian/Ubuntu). They are not installable usefully from PyPI.

Requires Python 3.9 or newer.

### udev rule (non-root access)

The tool talks to the mouse through `/dev/hidraw*`, which is root-only by default. The file `packaging/udev/70-attackshark.rules` grants the logged-in user access with the `uaccess` tag:

    SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1d57", ATTRS{idProduct}=="fa60|2126", TAG+="uaccess", MODE="0660"

Install it, then replug the dongle:

    sudo cp packaging/udev/70-attackshark.rules /etc/udev/rules.d/
    sudo udevadm control --reload && sudo udevadm trigger

`uaccess` must be tagged before `73-seat-late.rules`. It gives access to the user at the active local seat. It does not work over SSH or for users who are not logged in locally. The rule matches only vendor ID `1d57` and the two product IDs above. If `lsusb` shows a different product ID for your dongle, see [docs/troubleshooting.md](docs/troubleshooting.md).

## Quick start

    attackshark-x11 show                      # current settings
    attackshark-x11 dpi 2 1600                # stage 2 = 1600 DPI
    attackshark-x11 active 2
    attackshark-x11 light --mode Static --rgb 00ff88
    attackshark-x11 rate 1000
    attackshark-x11 raw                       # dump reports 4/5/6 (include this in bug reports)

**The mouse sleeps quickly.** Move it while a command runs; the tool waits up to about 100 seconds for it to answer.

## CLI reference

    attackshark-x11 [-h] [--version] [--device DEVICE] <command> ...

`--device` takes a hidraw path (default: autodetect the vendor config interface).

| Command | Purpose |
|---|---|
| `show [--json]` | Print current settings, including battery if the mouse reports it |
| `dpi STAGE DPI` | Set DPI of a stage (1-8). DPI must be a multiple of 50 in 50..22000 |
| `active STAGE` | Select the active stage (1-8) |
| `color STAGE RRGGBB` | Set the color of a DPI stage |
| `light [--mode M] [--rgb RRGGBB] [--brightness 1-8] [--breath-speed 4-8]` | Light mode and color. Mode is 0-6 or a name: `LED Off`, `Static`, `Breathing`, `Neon`, `Color Breathing`, `Static DPI`, `Breathing DPI` |
| `sleep [--min 1-60] [--deep 1-60] [--debounce 4-50 step 2]` | Sleep minutes, deep sleep seconds, key debounce in ms (unverified) |
| `rate {125,250,500,1000}` | Polling rate in Hz |
| `defaults [--preset {ms4,ms13}]` | Write a factory DPI table and polling rate; light and sleep untouched (unverified which preset matches) |
| `buttons-default` | Write the vendor default button map (unverified) |
| `functions` | List button function codes |
| `button SLOT FUNCTION` | Assign a function to a button 1-18. `FUNCTION` is a hex code, a name, or `key:<combo>`, e.g. `button 4 0x34`, `button 4 key:ctrl+c`, `button 4 'Left Click'` (unverified) |
| `macro SLOT [--file F] [--mode {0,1,2}] [--loop N] [events ...]` | Write a macro and assign it, e.g. `macro 4 --loop 3 +a:30 -a:30`. Events are `+key:delay_ms` (press) and `-key:delay_ms` (release); `lmb`, `rmb`, `mmb` are mouse buttons (unverified) |
| `profile save\|load\|delete NAME`, `profile list`, `profile export NAME PATH`, `profile import PATH [--name N]` | Whole-device profiles stored as JSON |
| `raw` | Dump reports 4, 5 and 6 as hex |
| `monitor [--json]` | Print live input events (DPI stage, battery, polling, light mode); Ctrl+C to stop |

Exit codes: 0 ok, 1 error, 2 usage, 3 device not found, 4 no permission, 5 timeout.

Report 8 (buttons) and report 9 (macros) cannot be read back from the mouse. The tool therefore remembers the button map and macros in `~/.config/attackshark-x11/buttons.json` (override with `ATTACKSHARK_X11_CONFIG` or `XDG_CONFIG_HOME`). Profiles live in `profiles/` in the same directory.

Run `attackshark-x11 <command> --help` for exact argument forms.

## GUI

`attackshark-x11-gui` opens a GTK4 window with the eight DPI stages (enable, DPI value, color, active stage), sensor options (lift-off distance, ripple control and similar), and lighting controls. It uses the same code paths as the CLI. Run it from a checkout with `PYTHONPATH=src python3 -m attackshark_x11.gui.app`.

## Documentation

- [docs/protocol.md](docs/protocol.md): full HID protocol specification
- [docs/reverse-engineering.md](docs/reverse-engineering.md): how the protocol was recovered, how to reproduce it, legal note
- [docs/hardware-testing.md](docs/hardware-testing.md): how to test unverified features safely and report results
- [docs/troubleshooting.md](docs/troubleshooting.md): sleeping mouse, permissions, hidraw, Flatpak
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md)

## Development

    pip install -e ".[test]"
    pytest
    ruff check .

The test suite runs against a fake device and needs no hardware.

## License

MIT, see [LICENSE](LICENSE). "Attack Shark" and related names are trademarks of their owners; they are used here only to identify the hardware this software works with.
