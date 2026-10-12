# UNTESTED. Fedora: rpmbuild -ba packaging/rpm/attackshark-x11.spec (sdist in SOURCES)
Name:           attackshark-x11
Version:        0.1.0
Release:        1%{?dist}
Summary:        Open-source Linux configuration tool for the Attack Shark X11 mouse
License:        MIT
URL:            https://github.com/attackshark-x11/attackshark-x11
Source0:        attackshark_x11-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  systemd-rpm-macros
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
%{?systemd_requires}

%description
Configure DPI, buttons, macros and profiles of the Attack Shark X11 mouse,
from a GTK4 app or the command line.

%prep
%autosetup -n attackshark_x11-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files attackshark_x11
install -Dm644 packaging/udev/70-attackshark.rules %{buildroot}%{_udevrulesdir}/70-attackshark.rules
install -Dm644 packaging/desktop/attackshark-x11.desktop -t %{buildroot}%{_datadir}/applications/
install -Dm644 packaging/icons/io.github.attackshark_x11.AttackSharkX11.svg -t %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/
install -Dm644 packaging/metainfo/io.github.attackshark_x11.AttackSharkX11.metainfo.xml -t %{buildroot}%{_metainfodir}/

%post
udevadm control --reload-rules >/dev/null 2>&1 || :

%files -f %{pyproject_files}
%{_bindir}/attackshark-x11
%{_bindir}/attackshark-x11-gui
%{_udevrulesdir}/70-attackshark.rules
%{_datadir}/applications/attackshark-x11.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.attackshark_x11.AttackSharkX11.svg
%{_metainfodir}/io.github.attackshark_x11.AttackSharkX11.metainfo.xml

%changelog
* Mon Oct 12 2026 Maintainer <maintainer@example.invalid> - 0.1.0-1
- Initial package
