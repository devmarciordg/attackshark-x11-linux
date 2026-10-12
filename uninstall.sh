#!/usr/bin/env bash
# Removes the user-level install. Flags: --user-only/--no-udev keep the udev rule.
set -euo pipefail

APP=attackshark-x11
ID=io.github.attackshark_x11.AttackSharkX11
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
RULE=/etc/udev/rules.d/70-attackshark.rules
udev=1
for a in "$@"; do
  case "$a" in
    --user-only|--no-udev) udev=0 ;;
    --uninstall) ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

rm -rf "${DATA:?}/$APP"
rm -f "$HOME/.local/bin/$APP" "$HOME/.local/bin/$APP-gui" \
  "$DATA/applications/$ID.desktop" \
  "$DATA/icons/hicolor/scalable/apps/$ID.svg" \
  "$DATA/metainfo/$ID.metainfo.xml"

if [ "$udev" = 1 ] && [ -e "$RULE" ]; then
  echo "About to run with elevated privileges: rm -f $RULE && udevadm control --reload-rules"
  if [ -t 0 ]; then read -r -p "Proceed? [y/N] " ans; else ans=y; fi
  case "$ans" in
    [yY]*)
      if [ "$(id -u)" = 0 ]; then s=""; elif command -v sudo >/dev/null; then s=sudo; else s=pkexec; fi
      $s rm -f "$RULE"; $s udevadm control --reload-rules ;;
  esac
fi
echo "Removed."
