# Reverse engineering notes

How the protocol in [protocol.md](protocol.md) was recovered, and how to repeat it yourself. This repository does **not** contain the vendor installer, its binaries, decompiler output or extracted assets, and you must not add them (`.gitignore` blocks `*.exe`).

## Legal note

<a id="legal-note"></a>

- This is an independent implementation written for interoperability: letting hardware you own work on an operating system the vendor does not support.
- No vendor code, binaries, firmware, images, icons or other assets are included. Source files are original; the protocol facts (report layouts, checksums, byte values) are functional information needed to talk to the device.
- The project is not affiliated with, endorsed by, or sponsored by Attack Shark. "Attack Shark", "X11" and related names are trademarks of their respective owners and are used only to identify compatible hardware.
- Reverse engineering laws differ by country. Interoperability exceptions exist in several jurisdictions but are not universal, and the vendor's license terms may say otherwise. This is not legal advice. If you reproduce the work, do it on a copy you lawfully obtained, and do not publish vendor material.
- Contributors must not paste decompiled code, disassembly listings or vendor strings in bulk into issues or PRs. Describe the behavior and give addresses or short byte values only.

## What was analyzed

The vendor distributes `ATTACK SHARK X11 SOFT.exe`, an Inno Setup installer. The installed application is `AttackShark.exe`, a C++ program using the DuiLib UI toolkit. It supports several mouse "models"; model 4 is the X11. Function addresses cited in the code comments (for example `FUN_004a26c0` for the button report builder, `FUN_004a2430` for the macro builder, the default table at `0x4e78a0`, the MS_4 reset at `0x4a4670`, the MS_13 reset at `0x447d00`) refer to this build under Ghidra's default image base. They will differ for other versions.

## Method

1. **Unpack the installer** with `innoextract` (Linux package of the same name):

       mkdir re-work && cd re-work
       innoextract -d extracted "../ATTACK SHARK X11 SOFT.exe"

   Keep the output in an ignored directory (`re-work/` is in `.gitignore`).
2. **Static analysis** (adjust the path to wherever innoextract placed the executable; commands here are a sketch, not tested in CI) of `AttackShark.exe` and its HID helper libraries with Ghidra, in headless mode so it is scriptable and repeatable:

       analyzeHeadless ./ghidra-projects attackshark -import extracted/app/AttackShark.exe -overwrite

   Then open the project in the Ghidra GUI or run a headless `-postScript` that dumps decompiled functions to text for grepping.
3. **Locate the HID layer**: search for `HidD_SetFeature`, `HidD_GetFeature`, `HidD_GetPreportDescriptor` style imports and their callers. The writer functions build fixed-size buffers (`0x38`, `0x0F`, `0x09`, `0x3B`, `0x83` lengths are the giveaways) then add a 16-bit sum. Follow those buffers back to the UI controls that fill them.
4. **Map UI to bytes**: slider ranges in the UI code give value limits (brightness 1..8, breathing speed 4..8, sleep 1..60 minutes, debounce); the order of fields in the buffer gives byte offsets.
5. **Confirm on hardware** where possible. Wireshark with usbmon (`modprobe usbmon`) can capture traffic from the vendor app running in a Windows VM with USB passthrough; compare captured feature reports against what the code produces. The confirmed rows in the README status table were checked by writing from this tool and observing the mouse (LED, pointer behavior, `monitor` events).
6. **Capture a known state**: read reports 4, 5 and 6 with `attackshark-x11 raw` before and after changing one setting in a vendor app or tool, and diff. This is the quickest way to locate an unknown byte.

## Reproducing the button and macro decode

Everything in the "unverified" rows comes from static reading, so the notes below are what to check:

- Button function table: the vendor app maps its UI "function code" to a `(type, a, b)` triple through a table at `0x4e7368`. The default code per slot is a second table at `0x4e78a0`.
- Report 8 builder: sets header `08 3B 01`, writes 18 triples, appends a checksum over bytes 3..56. Macro function codes carry the button number in the third byte.
- Report 9 builder: header `09 83`, slot, mode, loop count, event count at offset 28, events from 29, checksum over bytes 3..128, then sends the buffer in three feature reports.
- The delay splitting for delays over 1270 ms is in the same builder.

Pull requests that fix this decode should include a hardware capture or a [hardware report](hardware-testing.md), not decompiled text.

## Tools

- `innoextract`
- Ghidra (headless analyzer)
- Wireshark with usbmon, `lsusb -v`, `usbhid-dump` for descriptors
- This repo: `attackshark-x11 raw`, `attackshark-x11 monitor`
