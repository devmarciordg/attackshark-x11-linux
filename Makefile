PY ?= python3
.PHONY: install uninstall wheel sdist lint test clean
install:
	./install.sh
uninstall:
	./uninstall.sh
wheel sdist:
	$(PY) -m build --$@ .
lint:
	$(PY) -m compileall -q src
	-shellcheck install.sh uninstall.sh
	desktop-file-validate packaging/desktop/attackshark-x11.desktop
	-appstreamcli validate --no-net packaging/metainfo/*.xml
test:
	$(PY) -m pytest
clean:
	rm -rf build dist src/*.egg-info .pytest_cache
