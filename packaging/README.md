# Packaging

Package and file names use `attackshark-x11`. Udev rule: `udev/99-attackshark.rules`
(`TAG+="uaccess"` for 1d57:fa60 and 1d57:2126, so no root or groups are needed).

| Item | Status |
|---|---|
| `../install.sh` / `../uninstall.sh` (user-level venv) | Tested (temp HOME, idempotent re-run, uninstall); udev step not run |
| wheel + sdist (`make wheel sdist`) | Tested |
| desktop file, AppStream metainfo | Validated (`desktop-file-validate`, `appstreamcli`: only homepage/developer hints) |
| `flatpak/` manifest | UNTESTED (YAML parses; GNOME Sdk not installed here) |
| `arch/PKGBUILD` | UNTESTED. URL is a placeholder |
| `rpm/attackshark-x11.spec` | UNTESTED. URL and changelog are placeholders |
| `debian/` | UNTESTED. Maintainer is a placeholder. Copy to the source root as `debian/` before `dpkg-buildpackage` |

## Dependencies per distro (GUI; the CLI needs only Python 3.9+)

| Distro | Packages |
|---|---|
| Fedora / Atomic / Bazzite | `python3-gobject gtk4 libadwaita` (usually preinstalled) |
| Debian / Ubuntu | `python3-gi gir1.2-gtk-4.0 gir1.2-adw-1` |
| Arch | `python-gobject gtk4 libadwaita` |
| openSUSE | `python3-gobject-Gdk typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1` |

## Flatpak

The sandbox needs `--device=all` to reach `/dev/hidraw*`. The udev rule must still be installed on the host
(`sudo install -m644 packaging/udev/99-attackshark.rules /etc/udev/rules.d/`), because the sandbox cannot
change device permissions. Build: `flatpak-builder --user --install --force-clean build packaging/flatpak/*.yml`.
