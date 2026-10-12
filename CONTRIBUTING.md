# Contributing

Thanks for helping. The most valuable contribution right now is **testing on real hardware**: see [docs/hardware-testing.md](docs/hardware-testing.md).

## Setup

    git clone <your fork> && cd attackshark
    python3 -m venv --system-site-packages .venv && . .venv/bin/activate
    pip install -e ".[test]" ruff
    pytest
    ruff check .

`--system-site-packages` lets the GUI import PyGObject from the distribution. The core package is stdlib only; please do not add runtime dependencies.

## Layout

- `src/attackshark_x11/protocol.py`: pure encode/decode of reports, no I/O
- `hid.py`: hidraw transport
- `buttons.py`, `macros.py`, `factory.py`, `profiles.py`: features
- `cli.py`, `gui/`: front-ends
- `tests/`: pytest with a fake device, no hardware needed
- `docs/protocol.md`: the protocol spec; update it with any protocol change

## Rules

- Python 3.9 compatible code (CI runs 3.9 to 3.14).
- Add tests for protocol or CLI changes.
- Mark anything not verified on a real mouse as unverified in code comments, docs and the README status table. Do not upgrade a feature to "verified" without a hardware report.
- Do not include vendor binaries, decompiled code, disassembly dumps or vendor assets. See the legal note in [docs/reverse-engineering.md](docs/reverse-engineering.md).
- Never write secrets or personal data into issues. Hex dumps of reports are fine.

## Commits and PRs

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. Keep PRs focused and fill in the PR template, including whether the change was tested on hardware.

## Reporting results

Use the "Hardware report" issue template. Include `lsusb -d 1d57:` and `attackshark-x11 raw`.
