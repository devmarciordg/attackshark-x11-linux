#!/usr/bin/env bash
# User-level installer for attackshark-x11. Flags: --user-only, --no-udev, --uninstall, -h
set -euo pipefail

APP=attackshark-x11
ID=io.github.attackshark_x11.AttackSharkX11
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA/$APP"
BIN="$HOME/.local/bin"
RULE=/etc/udev/rules.d/70-attackshark.rules
udev=1 uninstall=0

for a in "$@"; do
  case "$a" in
    --user-only|--no-udev) udev=0 ;;
    --uninstall) uninstall=1 ;;
    -h|--help) sed -n '2p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

if [ "$uninstall" = 1 ]; then
  exec "$SRC/uninstall.sh" "$@"
fi

as_root() {
  if [ "$(id -u)" = 0 ]; then "$@"
  elif command -v sudo >/dev/null 2>&1; then sudo "$@"
  elif command -v pkexec >/dev/null 2>&1; then pkexec "$@"
  else echo "need sudo or pkexec for: $*" >&2; return 1; fi
}

command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
if [ -e /run/ostree-booted ] || command -v rpm-ostree >/dev/null 2>&1; then
  echo "Immutable distro detected: user-level install only; /etc/udev/rules.d is still writable."
fi

echo "Installing to $PREFIX (venv, --system-site-packages so system PyGObject is visible)"
python3 -m venv --system-site-packages "$PREFIX/venv"
"$PREFIX/venv/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade "$SRC"

mkdir -p "$BIN" "$DATA/applications" "$DATA/icons/hicolor/scalable/apps" "$DATA/metainfo"
for c in "$APP" "$APP-gui"; do
  printf '#!/bin/sh\nexec "%s/venv/bin/%s" "$@"\n' "$PREFIX" "$c" > "$BIN/$c"
  chmod +x "$BIN/$c"
done
install -m 644 "$SRC/packaging/desktop/$APP.desktop" "$DATA/applications/"
install -m 644 "$SRC/packaging/icons/$ID.svg" "$DATA/icons/hicolor/scalable/apps/"
install -m 644 "$SRC/packaging/metainfo/$ID.metainfo.xml" "$DATA/metainfo/"
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$DATA/icons/hicolor" || true

if [ "$udev" = 1 ]; then
  echo "About to run with elevated privileges:"
  echo "  install -m 644 packaging/udev/70-attackshark.rules $RULE"
  echo "  udevadm control --reload-rules && udevadm trigger --subsystem-match=hidraw"
  if [ -t 0 ]; then read -r -p "Proceed? [y/N] " ans; else ans=y; fi
  case "$ans" in
    [yY]*)
      as_root install -m 644 "$SRC/packaging/udev/70-attackshark.rules" "$RULE"
      as_root udevadm control --reload-rules
      as_root udevadm trigger --subsystem-match=hidraw ;;
    *) echo "Skipped udev rule (re-run without --no-udev to install it)." ;;
  esac
fi

case ":$PATH:" in *":$BIN:"*) ;; *) echo "Note: add $BIN to your PATH." ;; esac
echo "Done. Replug the mouse dongle if it was already connected."
