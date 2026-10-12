# Hardware testing guide

Buttons, macros, factory presets, sleep timers and key debounce are implemented from the vendor app's decoded behavior but have not been verified on a real mouse. If you own an Attack Shark X11, you can help confirm or correct them. This guide keeps the risk low.

## Risk

All settings live in the mouse's own memory. A wrong write is normally recoverable by writing the defaults again, but we cannot promise it. The main practical risk is **remapping every button so the mouse is hard to use**. The tool refuses a button map without at least one Left Click, and the steps below keep a way back.

By testing you accept that this is unofficial software. Do not test while the mouse is the only pointing device you can use for recovery: keep a second mouse or a keyboard-driven way to run a terminal.

## Before you start

1. Update to the latest version and run `attackshark-x11 --version`.
2. Wake the mouse and run `attackshark-x11 show` and `attackshark-x11 raw`. If these fail, fix that first ([troubleshooting](troubleshooting.md)).
3. Save a profile of the current state: `attackshark-x11 profile save before-test`.
4. Save the output of `raw` in a text file. It is the exact state to compare against.
5. Note `lsusb -d 1d57:` output.

## Recovery

- DPI, light, polling: `attackshark-x11 profile load before-test`.
- Buttons: `attackshark-x11 buttons-default` writes the default map (and forgets saved macros).
- If the mouse stops responding: unplug the dongle, power-cycle the mouse. The vendor Windows app can also restore factory settings.

## Test: buttons

Pick a harmless button first, such as the DPI button or a side button, not left click.

    attackshark-x11 button 4 key:f13        # or: key:ctrl+c
    attackshark-x11 button 4 0x34           # a function code, see `functions`

Check in a text editor or `xev`/`wev` (keyboard events) that the button does what you set. Then restore with `attackshark-x11 buttons-default` and check again. Record: button number, command, expected, observed.

Things worth recording especially:

- Which physical button is which slot number (1 to 18). This is a guess today.
- Whether the forward and back side buttons (slots 7 and 8) are right.
- What the unnamed function codes do. Try one at a time and write down the effect.

## Test: macros

Use a macro that is visible and cannot do damage, in a text editor:

    attackshark-x11 macro 4 +h:30 -h:30 +i:30 -i:30

Press the button. Expected: `hi` typed once. Then try `--loop 3`, `--mode 1`, `--mode 2`, a mouse button (`+lmb:30 -lmb:30` in a safe place), and a delay of more than 1270 ms. For each, record what happened. Do not put destructive key combos in test macros.

## Test: presets, sleep, debounce

- `attackshark-x11 defaults --preset ms4`, then `show` and check the DPI stages and polling rate against the table in [protocol.md](protocol.md). Repeat with `ms13`. Tell us which one matches a mouse fresh from the vendor app's "restore defaults".
- `attackshark-x11 sleep --min 1` and watch whether the mouse sleeps after about one minute of no use. Reset it afterwards.
- `attackshark-x11 sleep --debounce 4` versus `50`: only report subjective double-click behavior if you can reproduce it.

## Reporting

Open a "Hardware report" issue on GitHub. It asks for:

- Mouse model and connection (2.4G dongle, wired)
- `lsusb -d 1d57:` output
- `attackshark-x11 raw` output, before and after the test where relevant
- What you ran and what you observed
- Distro, kernel, tool version

Do not include screenshots of the vendor app's files or any vendor binary. Hex dumps from `raw` and `monitor` are fine.
