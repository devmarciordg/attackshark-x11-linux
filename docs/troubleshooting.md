# Troubleshooting

## "waiting for the mouse: move it to wake it up..." or timeout (exit code 5)

The mouse goes to sleep within seconds of inactivity and does not answer configuration reads while asleep. Move the mouse during the command; the tool retries for roughly 100 seconds. Check that the mouse is switched on and has charge. Battery events only arrive while the mouse is awake, so `show` may print "no report (mouse asleep)" for battery.

## "X11 config interface not found" (exit code 3)

- Check the dongle: `lsusb -d 1d57:` should list `1d57:fa60` (2.4G dongle) or `1d57:2126` (wired).
- If you see a different product ID (for example a 4K dongle), the ID is not in the supported list yet. Open a hardware report with the `lsusb` line and `ls /sys/class/hidraw/`.
- The tool picks the hidraw interface whose report descriptor declares feature report `0xA0`. To inspect it: `for d in /sys/class/hidraw/hidraw*; do echo $d; xxd $d/device/report_descriptor | grep -i "85a0"; done`.
- Pass the node explicitly with `--device /dev/hidrawN` to test.
- Try another USB port, avoid unpowered hubs, replug the dongle.

## Permission denied (exit code 4)

Install the udev rule from the README, reload, and replug the dongle:

    sudo cp 99-attackshark.rules /etc/udev/rules.d/
    sudo udevadm control --reload && sudo udevadm trigger

Check the result: `ls -l /dev/hidraw*`. With `uaccess`, the device gets an ACL for your user (`getfacl /dev/hidrawN`). If it still fails:

- You must be logged in on a local seat (not only SSH). `loginctl show-session self -p Active -p Remote`.
- The `uaccess` tag must be set before `73-seat-late.rules` runs (see `man systemd-udevd`/`uaccess`). A file named `99-attackshark.rules` sorts after it, so the tag may have no effect on some systems. If access still fails, install the same content as `70-attackshark.rules`.
- Your distro may ship a rule that already matches; check `udevadm info /dev/hidrawN`.
- As a last resort for testing only: `sudo attackshark-x11 show`. Do not leave the GUI running as root.

## Settings do not apply

Writes are ignored if the handshake is skipped; the tool sends it automatically. If a write seems lost, run `attackshark-x11 show` again, which re-reads from the mouse. After a DPI-table change the mouse rewrites the polling rate itself, so set the polling rate after DPI.

## Button or macro changes have no effect

These are unverified features. Run `attackshark-x11 raw` and check the tool's remembered map in `~/.config/attackshark-x11/buttons.json`. Report 8 and 9 cannot be read back, so `show` cannot confirm them. Please file a hardware report with details.

## Flatpak and containers

The hidraw nodes are not exposed to most sandboxes by default. A Flatpak build needs `--device=all` (or a `--device=all` style override such as `flatpak override --user --device=all <app-id>`) to open `/dev/hidraw*`, and the host udev rule still has to be installed on the host, not inside the sandbox. For a packaged app, see [packaging/README.md](../packaging/README.md). For Toolbx/Distrobox, install the udev rule on the host; hidraw nodes are visible in the container but permissions come from the host rule. In Docker use `--device /dev/hidrawN`.

## GUI does not start

The GUI needs GTK 4 and PyGObject from the distribution. `python3 -c "import gi; gi.require_version('Gtk','4.0')"` should succeed. In a virtualenv, create it with `--system-site-packages`, or use `pipx install --system-site-packages`.

## Mouse behaves strangely after a test

`attackshark-x11 profile load <name>` if you saved one, then `attackshark-x11 buttons-default`. If it persists, power-cycle the mouse and reconnect the dongle.
