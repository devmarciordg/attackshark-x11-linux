# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Documentation: README (English and Portuguese), protocol specification, reverse-engineering notes, hardware testing guide, troubleshooting.
- CI (pytest on Python 3.9 to 3.14, ruff), release workflow, issue and PR templates, `ruff.toml`.
- MIT license.

## [0.1.0]

### Added
- CLI and GTK4 GUI for DPI stages, lighting, polling rate, battery, profiles.
- Button remapping and macros (decoded from the vendor app; unverified on hardware).
- Factory presets MS_4 and MS_13 (unverified which one matches the X11).
- pytest suite using a fake device.
