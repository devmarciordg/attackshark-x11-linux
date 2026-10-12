# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability reporting ("Security" tab, "Report a vulnerability") on this repository. Include the version, what you observed and steps to reproduce. We aim to acknowledge reports within 7 days. This is a volunteer project, so no fixed fix time can be promised.

## Scope

The tool runs as the logged-in user and writes only to the mouse's hidraw node and to `~/.config/attackshark-x11/`. Relevant areas: the udev rule (grants device access to the local seat user), parsing of profile and macro JSON files, and path handling in `profile export/import`.

Please do not run the tool or GUI as root; the udev rule exists so that it is not needed.

## Supported versions

Only the latest release.
